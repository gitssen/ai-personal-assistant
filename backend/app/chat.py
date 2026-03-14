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
    identity_memories = get_relevant_memories("My address and identity information", n_results=3)
    topic_memories = get_relevant_memories(user_message, n_results=3)
    all_memories = list(set(identity_memories + topic_memories))
    memory_context = "\n".join(all_memories) if all_memories else "No specific preferences saved yet."

    current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")

    # 1. ROUTER Decision
    router_prompt = (
        f"User Memories: {memory_context}\n"
        f"User message: '{user_message}'\n"
        f"If this is a local request (trails, food, weather), choose 'WEB' and include the user's address in the query.\n"
        f"Format: ROUTE: [PERSONAL/WEB] | QUERY: [Specific search query]"
    )
    route_res = client.models.generate_content(model=MODEL_ID, contents=router_prompt)
    decision = route_res.text.strip()
    print(f"DEBUG: ROUTER DECISION -> {decision}")
    
    is_web = "WEB" in decision
    rewritten_query = user_message
    if "QUERY:" in decision:
        rewritten_query = decision.split("QUERY:")[1].strip()

    last_tool = None
    if is_web:
        # --- WEB SEARCH ---
        print(f"DEBUG: Performing Google Search for: {rewritten_query}")
        config = types.GenerateContentConfig(
            system_instruction=(
                f"You are a helpful assistant with LIVE GOOGLE SEARCH ACCESS. "
                f"Current time: {current_time}. User Location: {memory_context}\n"
                f"RULES:\n"
                f"1. You MUST use Google Search to find real-time info (trails, maps, news).\n"
                f"2. NEVER apologize or say you cannot provide maps or recommendations. You have the tool to do it!\n"
                f"3. Provide exactly what the user asked for (e.g., 5 trails with links)."
            ),
            tools=[{"google_search": {}}]
        )
        response = client.models.generate_content(model=MODEL_ID, contents=rewritten_query, config=config)
        return response.text, [], "google_search"
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
            else: break
            response = chat.send_message(types.Content(parts=[types.Part(function_response=types.FunctionResponse(name=tool_name, response={"result": result}))]))
        return response.text, getattr(chat, "_curated_history", []), last_tool
