from google import genai
from google.genai import types
import os
import json
from datetime import datetime
from app.tools import (
    search_gmail, read_gmail_message, list_gmail_attachments, read_gmail_attachment,
    search_drive, read_drive_file, list_calendar_events, create_calendar_event,
    update_calendar_event, delete_calendar_event,
    save_personal_fact, delete_personal_fact, search_memory
)
from app.memory import get_relevant_memories
from app.logger import logger

MODEL_ID = "gemini-2.5-flash"
TOKEN_PATH = "tokens.json"

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_user_email():
    if not os.path.exists(TOKEN_PATH): return None
    with open(TOKEN_PATH, 'r') as f:
        return json.load(f).get('email')

def chat_with_assistant(user_message: str, history=None):
    client = get_client()
    email = get_user_email()
    if not email: return "Please log in first.", [], None
    
    # 1. BROAD IDENTITY RETRIEVAL (The "Who am I?" check)
    # We run 4 specific queries to ensure ALL core life facts are loaded.
    core_queries = [
        "My full name, address, and home details",
        "My family members, wife, spouse, kids, and children's details",
        "My pets, dogs, and their health/veterinary information",
        "My food, movie, and lifestyle preferences"
    ]
    
    all_core_memories = []
    for q in core_queries:
        all_core_memories.extend(get_relevant_memories(email, q, n_results=5))
    
    # Also search for the user's current question specifically
    topic_memories = get_relevant_memories(email, user_message, n_results=5)
    
    # Unique set of all found memories
    memory_context = "\n".join(list(set(all_core_memories + topic_memories)))
    current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")

    # 2. CONVERT HISTORY
    formatted_history = []
    if history:
        for entry in history:
            role = "model" if entry.get("role") == "assistant" else "user"
            parts = []
            for p in entry.get("parts", []):
                if "text" in p:
                    parts.append(types.Part(text=p["text"]))
                elif "function_call" in p:
                    fc = p["function_call"]
                    parts.append(types.Part(function_call=types.FunctionCall(name=fc["name"], args=fc["args"])))
                elif "function_response" in p:
                    fr = p["function_response"]
                    parts.append(types.Part(function_response=types.FunctionResponse(name=fr["name"], response=fr["response"])))
            
            if parts: formatted_history.append(types.Content(role=role, parts=parts))

    # 3. ROUTER
    router_prompt = (
        f"User Memories: {memory_context}\n"
        f"User message: '{user_message}'\n"
        f"Decide ROUTE (PERSONAL/WEB) and SEARCH_TERMS.\n"
        f"Note: Use the memories above to identify people/pets mentioned."
    )
    route_res = client.models.generate_content(
        model=MODEL_ID, 
        contents=formatted_history + [types.Content(role="user", parts=[types.Part(text=router_prompt)])]
    )
    
    if not route_res.text:
        logger.warning(f"Router failed to return text. Response: {route_res}")
        decision = "PERSONAL" # Default to personal if router fails
    else:
        decision = route_res.text.strip()
        
    logger.info(f"ROUTER -> {decision}")
    
    is_personal = "PERSONAL" in decision
    search_terms = user_message
    if "QUERY:" in decision: search_terms = decision.split("QUERY:")[1].strip()

    last_tool = None
    safety_settings = [
        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
    ]

    if not is_personal:
        config = types.GenerateContentConfig(
            system_instruction=f"Web assistant. Time: {current_time}. Context: {memory_context}",
            tools=[{"google_search": {}}],
            safety_settings=safety_settings
        )
        response = client.models.generate_content(model=MODEL_ID, contents=user_message, config=config)
        final_text = response.text or "I'm sorry, I encountered a safety filter or an error while searching the web."
        return final_text, [], "google_search"
    else:
        config = types.GenerateContentConfig(
            system_instruction=(
                f"You are a personal detective assistant for {email}. Time: {current_time}. {memory_context}\n"
                f"1. VERIFY: Always cross-verify memory with Gmail/Drive/Calendar if possible.\n"
                f"2. THOROUGH: Search all tools. Answer using names and facts from memory.\n"
                f"3. CALENDAR: When creating/updating events, ask for the timezone if unsure, or default to the user's local timezone if known."
            ),
            tools=[search_gmail, read_gmail_message, list_gmail_attachments, read_gmail_attachment, search_drive, read_drive_file, list_calendar_events, create_calendar_event, update_calendar_event, delete_calendar_event, save_personal_fact, delete_personal_fact, search_memory],
            safety_settings=safety_settings
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
            elif tool_name == "list_calendar_events": result = list_calendar_events(**call.args)
            elif tool_name == "create_calendar_event": result = create_calendar_event(**call.args)
            elif tool_name == "update_calendar_event": result = update_calendar_event(**call.args)
            elif tool_name == "delete_calendar_event": result = delete_calendar_event(**call.args)
            else: break
            response = chat.send_message(types.Part(function_response=types.FunctionResponse(name=tool_name, response={"result": result})))
        
        final_text = response.text or "I'm sorry, I encountered a safety filter or an error while processing your request."
        return final_text, getattr(chat, "_curated_history", []), last_tool
