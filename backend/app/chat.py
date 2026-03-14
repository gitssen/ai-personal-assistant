from google import genai
from google.genai import types
import os
from datetime import datetime
from app.tools import (
    search_gmail, read_gmail_message, list_gmail_attachments, read_gmail_attachment,
    search_drive, read_drive_file, save_personal_fact, delete_personal_fact, search_memory
)
from app.memory import get_relevant_memories

MODEL_ID = "gemini-2.5-flash"

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def chat_with_assistant(user_message: str, history=None):
    client = get_client()
    
    # 1. Retrieve all relevant context (Home, School names, etc.)
    identity_memories = get_relevant_memories("My address, home, children's schools, and workplace", n_results=10)
    topic_memories = get_relevant_memories(user_message, n_results=5)
    memory_context = "\n".join(list(set(identity_memories + topic_memories)))
    current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")

    # 2. CONVERT HISTORY
    formatted_history = []
    if history:
        for entry in history:
            role = "model" if entry.get("role") == "assistant" else "user"
            parts = [types.Part(text=p["text"]) for p in entry.get("parts", []) if "text" in p]
            if parts: formatted_history.append(types.Content(role=role, parts=parts))

    # 3. ENHANCED ROUTER
    router_prompt = (
        f"User Memories: {memory_context}\n"
        f"User message: '{user_message}'\n"
        f"Goal: Route to PERSONAL or WEB.\n"
        f"DISTANCE RULE: If the user asks for distance, travel time, or directions between two places "
        f"mentioned in memory (e.g., house to school), choose WEB and re-write the query to include both full addresses.\n"
        f"Response format: ROUTE: [PERSONAL/WEB] | QUERY: [Rewritten specific search query]"
    )
    route_res = client.models.generate_content(
        model=MODEL_ID, 
        contents=formatted_history + [types.Content(role="user", parts=[types.Part(text=router_prompt)])]
    )
    decision = route_res.text.strip()
    print(f"DEBUG: ROUTER -> {decision}")
    
    is_web = "WEB" in decision
    search_terms = user_message
    if "QUERY:" in decision: search_terms = decision.split("QUERY:")[1].strip()

    last_tool = None
    if is_web:
        # --- WEB SPECIALIST (Maps/Distance) ---
        print(f"DEBUG: Distance Search for: {search_terms}")
        config = types.GenerateContentConfig(
            system_instruction=(
                f"You are a web-connected assistant. Current time: {current_time}.\n"
                f"Use Google Search to find distances, travel times, or maps. "
                f"The user has these details in memory: {memory_context}\n"
                f"If they ask 'how far', provide the driving distance and approximate time."
            ),
            tools=[{"google_search": {}}]
        )
        response = client.models.generate_content(model=MODEL_ID, contents=search_terms, config=config)
        return response.text, [], "google_search"
    else:
        # --- PERSONAL DATA SPECIALIST ---
        config = types.GenerateContentConfig(
            system_instruction=f"Personal assistant. Time: {current_time}. {memory_context}",
            tools=[search_gmail, read_gmail_message, list_gmail_attachments, read_gmail_attachment, search_drive, read_drive_file, save_personal_fact, delete_personal_fact, search_memory]
        )
        chat = client.chats.create(model=MODEL_ID, config=config, history=formatted_history)
        response = chat.send_message(user_message)
        
        while response.candidates[0].content.parts and response.candidates[0].content.parts[0].function_call:
            call = response.candidates[0].content.parts[0].function_call
            tool_name = call.name
            last_tool = tool_name
            if tool_name == "save_personal_fact": result = save_personal_fact(**call.args)
            elif tool_name == "delete_personal_fact": result = delete_personal_fact(**call.args)
            elif tool_name == "search_memory": result = search_memory(**call.args)
            elif tool_name == "search_gmail": result = search_gmail(**call.args)
            elif tool_name == "read_gmail_message": result = read_gmail_message(**call.args)
            elif tool_name == "list_gmail_attachments": result = list_gmail_attachments(**call.args)
            elif tool_name == "read_gmail_attachment": result = read_gmail_attachment(**call.args)
            elif tool_name == "search_drive": result = search_drive(**call.args)
            elif tool_name == "read_drive_file": result = read_drive_file(**call.args)
            else: break
            response = chat.send_message(types.Part(function_response=types.FunctionResponse(name=tool_name, response={"result": result})))
        
        return response.text, getattr(chat, "_curated_history", []), last_tool
