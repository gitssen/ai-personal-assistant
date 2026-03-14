from google import genai
from google.genai import types
import os
from datetime import datetime
from app.tools import search_gmail, read_gmail_message, search_drive, read_drive_file
from app.memory import get_relevant_memories, save_preference

MODEL_ID = "gemini-2.5-flash"

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def chat_with_assistant(user_message: str, history=None):
    client = get_client()
    
    # 1. ENHANCED MEMORY RETRIEVAL
    # We query for 'identity' specifically to ensure the address is ALWAYS found.
    identity_memories = get_relevant_memories("My address and identity information", n_results=3)
    # We also query for the user's actual question
    topic_memories = get_relevant_memories(user_message, n_results=3)
    
    all_memories = list(set(identity_memories + topic_memories))
    
    memory_context = ""
    if all_memories:
        memory_context = "\nUSER CONTEXT (MEMORIES):\n- " + "\n- ".join(all_memories)

    current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")

    # 2. DECISION LOGIC
    router_prompt = (
        f"You are a routing agent. User Memories: {memory_context}\n"
        f"User message: '{user_message}'\n"
        f"Goal: re-write the user's request into a highly specific search query.\n"
        f"If the user says 'local' or 'near me', you MUST include their address from Memory in the query.\n"
        f"Response format: ROUTE: [PERSONAL/WEB] | QUERY: [Specific search query]"
    )
    route_res = client.models.generate_content(model=MODEL_ID, contents=router_prompt)
    decision_text = route_res.text.strip()
    print(f"DEBUG: DECISION -> {decision_text}")
    
    is_web = "WEB" in decision_text
    rewritten_query = user_message
    if "QUERY:" in decision_text:
        rewritten_query = decision_text.split("QUERY:")[1].strip()

    last_tool = None
    final_text = ""
    final_history = []

    if is_web:
        # --- WEB SEARCH (Strict Instruction) ---
        print(f"DEBUG: Searching Web for: {rewritten_query}")
        config = types.GenerateContentConfig(
            system_instruction=(
                f"You are a web-connected assistant. Current time: {current_time}.\n"
                f"USER MEMORY: {memory_context}\n"
                f"INSTRUCTION: Use Google Search to answer. The user's location is in the memory above. "
                f"NEVER ask for their location if it is mentioned in the memory. Just perform the search."
            ),
            tools=[{"google_search": {}}]
        )
        response = client.models.generate_content(model=MODEL_ID, contents=rewritten_query, config=config)
        final_text = response.text
        last_tool = "google_search"
    else:
        # --- PERSONAL DATA ---
        config = types.GenerateContentConfig(
            system_instruction=f"Personal assistant. Time: {current_time}. {memory_context}",
            tools=[search_gmail, read_gmail_message, search_drive, read_drive_file]
        )
        chat = client.chats.create(model=MODEL_ID, config=config)
        response = chat.send_message(user_message)
        
        while response.candidates[0].content.parts and response.candidates[0].content.parts[0].function_call:
            call = response.candidates[0].content.parts[0].function_call
            tool_name = call.name
            last_tool = tool_name
            if tool_name == "search_gmail": result = search_gmail(**call.args)
            elif tool_name == "read_gmail_message": result = read_gmail_message(**call.args)
            elif tool_name == "search_drive": result = search_drive(**call.args)
            elif tool_name == "read_drive_file": result = read_drive_file(**call.args)
            else: result = "Error"
            response = chat.send_message(types.Content(parts=[types.Part(function_response=types.FunctionResponse(name=tool_name, response={"result": result}))]))
        
        final_text = response.text
        final_history = getattr(chat, "_curated_history", [])

    return final_text, final_history, last_tool
