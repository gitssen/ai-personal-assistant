from google import genai
from google.genai import types
import os
import json
import time
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

# IN-MEMORY CACHE for Identity Retrieval
IDENTITY_CACHE = {}
CACHE_TTL = 600 # 10 minutes

def get_cached_identity(email):
    """Retrieve identity from cache if not expired."""
    entry = IDENTITY_CACHE.get(email)
    if entry and time.time() < entry["expires"]:
        return entry["identity"]
    return None

def set_cached_identity(email, identity):
    """Store identity in cache."""
    IDENTITY_CACHE[email] = {
        "identity": identity,
        "expires": time.time() + CACHE_TTL
    }

def clear_identity_cache(email):
    """Clear cache for a user (called when new facts are saved)."""
    if email in IDENTITY_CACHE:
        del IDENTITY_CACHE[email]

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_user_email():
    if not os.path.exists(TOKEN_PATH): return None
    with open(TOKEN_PATH, 'r') as f:
        return json.load(f).get('email')

def serialize_history(history):
    """Converts the new google.genai history objects into a JSON-friendly format for persistent multi-turn tool use."""
    serialized = []
    if not history: return []
    for content in history:
        role = content.role
        parts = []
        for part in content.parts:
            if hasattr(part, 'text') and part.text:
                parts.append({"text": part.text})
            elif hasattr(part, 'function_call') and part.function_call:
                parts.append({"function_call": {"name": part.function_call.name, "args": part.function_call.args}})
            elif hasattr(part, 'function_response') and part.function_response:
                parts.append({"function_response": {"name": part.function_response.name, "response": part.function_response.response}})
        if parts: serialized.append({"role": role, "parts": parts})
    return serialized

async def chat_with_assistant(user_message: str, history=None):
    client = get_client()
    email = get_user_email()
    if not email:
        yield json.dumps({"error": "Please log in first."})
        return
    
    # 1. BROAD IDENTITY RETRIEVAL
    cached_identity = get_cached_identity(email)
    if cached_identity:
        identity_context = cached_identity
    else:
        core_queries = [
            "My full name, address, and home details",
            "My family members, wife, spouse, kids, and children's details",
            "My pets, dogs, and their health/veterinary information",
            "My food, movie, and lifestyle preferences"
        ]
        from concurrent.futures import ThreadPoolExecutor
        def search_worker(query): return get_relevant_memories(email, query, n_results=5)
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(search_worker, core_queries))
            flat_results = []
            for r in results: flat_results.extend(r)
            identity_context = "\n".join(list(set(flat_results)))
            set_cached_identity(email, identity_context)
    
    topic_memories = get_relevant_memories(email, user_message, n_results=5)
    memory_context = f"{identity_context}\n" + "\n".join(topic_memories)
    current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")

    # 2. CONVERT HISTORY
    formatted_history = []
    text_only_history = []
    if history:
        for entry in history:
            role = "model" if entry.get("role") == "assistant" else "user"
            parts = []
            text_parts = []
            for p in entry.get("parts", []):
                if "text" in p:
                    parts.append(types.Part(text=p["text"]))
                    text_parts.append(types.Part(text=p["text"]))
                elif "function_call" in p:
                    fc = p["function_call"]
                    parts.append(types.Part(function_call=types.FunctionCall(name=fc["name"], args=fc["args"])))
                elif "function_response" in p:
                    fr = p["function_response"]
                    parts.append(types.Part(function_response=types.FunctionResponse(name=fr["name"], response=fr["response"])))
            if parts: formatted_history.append(types.Content(role=role, parts=parts))
            if text_parts: text_only_history.append(types.Content(role=role, parts=text_parts))

    # 3. ROUTER
    router_prompt = (
        f"User Memories: {memory_context}\n"
        f"User message: '{user_message}'\n"
        f"Decide ROUTE (PERSONAL/WEB) and SEARCH_TERMS.\n"
    )
    route_res = client.models.generate_content(
        model=MODEL_ID, 
        contents=text_only_history + [types.Content(role="user", parts=[types.Part(text=router_prompt)])]
    )
    
    decision = route_res.text.strip() if route_res.text else "PERSONAL"
    is_personal = "PERSONAL" in decision
    
    safety_settings = [
        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
    ]

    last_tool = None
    if not is_personal:
        last_tool = "google_search"
        yield json.dumps({"task": last_tool}) + "\n"
        config = types.GenerateContentConfig(
            system_instruction=f"Web assistant. Time: {current_time}. Context: {memory_context}. ALWAYS use Markdown (bolding, lists, tables) for your response.",
            tools=[{"google_search": {}}],
            safety_settings=safety_settings
        )
        for chunk in client.models.generate_content_stream(model=MODEL_ID, contents=user_message, config=config):
            if chunk.text:
                yield json.dumps({"text": chunk.text}) + "\n"
        return

    # PERSONAL ROUTE (with potential tool use)
    config = types.GenerateContentConfig(
        system_instruction=(
            f"You are a proactive personal detective assistant for {email}. Time: {current_time}. {memory_context}\n"
            f"1. SEARCH FIRST: If you do not find the answer in the provided 'User Memories', you MUST proactively use tools (Gmail, Drive, Calendar) to find the answer.\n"
            f"2. VERIFY: Cross-verify memory with Gmail/Drive/Calendar if possible.\n"
            f"3. THOROUGH: Search all relevant tools.\n"
            f"4. RICH TEXT: ALWAYS use Markdown to format your response (bolding, bullet points, and tables for lists)."
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
        yield json.dumps({"task": last_tool}) + "\n"
        
        # Mapping tool results
        if tool_name == "save_personal_fact": 
            result = save_personal_fact(**call.args)
            clear_identity_cache(email)
        elif tool_name == "delete_personal_fact": 
            result = delete_personal_fact(**call.args)
            clear_identity_cache(email)
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
        
        # For the very last turn (after tools are exhausted), we want to stream.
        # But we don't know if it's the last turn yet.
        # If the NEXT response also has tool calls, we shouldn't stream it as text.
        
        response = chat.send_message(types.Part(function_response=types.FunctionResponse(name=tool_name, response={"result": result})))

    # Stream the final response text
    # Since we already have 'response' from the last tool turn, we can't 'stream' that exact one.
    # However, if 'response' has text, we yield it.
    if response.text:
        yield json.dumps({"text": response.text}) + "\n"

    
    # Send final metadata
    yield json.dumps({
        "history": serialize_history(getattr(chat, "_curated_history", [])),
        "done": True
    }) + "\n"


