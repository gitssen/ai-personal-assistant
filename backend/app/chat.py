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
    
    # 1. Retrieve all family/identity context to help the search
    family_memories = get_relevant_memories("Who are the user's children, family members, and kids?", n_results=5)
    identity_memories = get_relevant_memories("My address and important contacts", n_results=5)
    topic_memories = get_relevant_memories(user_message, n_results=5)
    
    all_memories = list(set(family_memories + identity_memories + topic_memories))
    memory_context = "\n".join(all_memories) if all_memories else ""
    current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")

    # 2. ROUTER turn
    router_prompt = (
        f"User Memories (includes family info): {memory_context}\n"
        f"User message: '{user_message}'\n"
        f"If this is about a family member or kid, use their names from memory to create better search terms.\n"
        f"Goal: Route to PERSONAL or WEB.\n"
        f"Response format: ROUTE: [PERSONAL/WEB] | SEARCH_TERMS: [term1, term2, ...]"
    )
    route_res = client.models.generate_content(model=MODEL_ID, contents=router_prompt)
    decision = route_res.text.strip()
    print(f"DEBUG: ROUTER -> {decision}")
    
    is_personal = "PERSONAL" in decision
    search_terms = user_message
    if "SEARCH_TERMS:" in decision: search_terms = decision.split("SEARCH_TERMS:")[1].strip()

    last_tool = None
    if not is_personal:
        config = types.GenerateContentConfig(
            system_instruction=f"Web assistant. Time: {current_time}. Context: {memory_context}",
            tools=[{"google_search": {}}]
        )
        response = client.models.generate_content(model=MODEL_ID, contents=user_message, config=config)
        return response.text, [], "google_search"
    else:
        # --- PERSONAL DATA SPECIALIST (Aggressive Searcher) ---
        config = types.GenerateContentConfig(
            system_instruction=(
                f"You are a highly thorough personal assistant. Current time: {current_time}. {memory_context}\n"
                f"RULES:\n"
                f"1. AGGRESSIVE SEARCH: If searching for an appointment (dentist, doctor, school), try multiple variations. "
                f"   Search for 'appointment', 'confirmation', 'dentist', and the specific names of family members: {memory_context}\n"
                f"2. DEPTH: If you see an email that mentions a child's name, read the full message.\n"
                f"3. NO GIVING UP: Search both Gmail and Drive before saying you can't find it."
            ),
            tools=[search_gmail, read_gmail_message, list_gmail_attachments, read_gmail_attachment, search_drive, read_drive_file, save_personal_fact, delete_personal_fact, search_memory]
        )
        chat = client.chats.create(model=MODEL_ID, config=config)
        response = chat.send_message(f"Answer this: '{user_message}' using search terms '{search_terms}'")
        
        while response.candidates[0].content.parts and response.candidates[0].content.parts[0].function_call:
            call = response.candidates[0].content.parts[0].function_call
            tool_name = call.name
            last_tool = tool_name
            print(f"DEBUG: EXECUTION - '{tool_name}' with args {call.args}")
            
            if tool_name == "search_memory": result = search_memory(**call.args)
            elif tool_name == "save_personal_fact": result = save_personal_fact(**call.args)
            elif tool_name == "delete_personal_fact": result = delete_personal_fact(**call.args)
            elif tool_name == "search_gmail": result = search_gmail(**call.args)
            elif tool_name == "read_gmail_message": result = read_gmail_message(**call.args)
            elif tool_name == "list_gmail_attachments": result = list_gmail_attachments(**call.args)
            elif tool_name == "read_gmail_attachment": result = read_gmail_attachment(**call.args)
            elif tool_name == "search_drive": result = search_drive(**call.args)
            elif tool_name == "read_drive_file": result = read_drive_file(**call.args)
            else: break
            
            response = chat.send_message(types.Part(function_response=types.FunctionResponse(name=tool_name, response={"result": result})))
        
        return response.text, getattr(chat, "_curated_history", []), last_tool
