from google import genai
from google.genai import types
import os
from datetime import datetime
from app.tools import (
    search_gmail, read_gmail_message, list_gmail_attachments, read_gmail_attachment,
    search_drive, read_drive_file
)
from app.memory import get_relevant_memories, save_preference

MODEL_ID = "gemini-2.5-flash"

def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def chat_with_assistant(user_message: str, history=None):
    client = get_client()
    identity_memories = get_relevant_memories("Who is the user and what do they own?", n_results=5)
    topic_memories = get_relevant_memories(user_message, n_results=3)
    memory_context = "\n".join(list(set(identity_memories + topic_memories)))
    current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")

    # 1. ROUTER turn
    router_prompt = (
        f"User Memories: {memory_context}\n"
        f"User message: '{user_message}'\n"
        f"Determine the route (PERSONAL/WEB) and brainstorm search terms.\n"
        f"Response format: ROUTE: [PERSONAL/WEB] | SEARCH_TERMS: [term1, term2, ...]"
    )
    route_res = client.models.generate_content(model=MODEL_ID, contents=router_prompt)
    decision = route_res.text.strip()
    
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
        # --- PERSONAL DATA SPECIALIST (With Attachment Support) ---
        config = types.GenerateContentConfig(
            system_instruction=(
                f"You are a detective assistant. Current time: {current_time}. {memory_context}\n"
                f"INVESTIGATION RULES:\n"
                f"1. GMAIL DEEP DIVE: If you find a relevant email, check if it has attachments. "
                f"   Use 'list_gmail_attachments' to see them and 'read_gmail_attachment' to parse them (PDFs, images, etc.).\n"
                f"2. DRIVE: Use 'read_drive_file' for documents.\n"
                f"3. GOAL: Exhaustively search and read until you find the specific answer requested."
            ),
            tools=[search_gmail, read_gmail_message, list_gmail_attachments, read_gmail_attachment, search_drive, read_drive_file]
        )
        chat = client.chats.create(model=MODEL_ID, config=config)
        response = chat.send_message(f"Investigate using terms '{search_terms}' to answer: '{user_message}'")
        
        while response.candidates[0].content.parts and response.candidates[0].content.parts[0].function_call:
            call = response.candidates[0].content.parts[0].function_call
            tool_name = call.name
            last_tool = tool_name
            print(f"DEBUG: EXECUTION - '{tool_name}'")
            
            if tool_name == "search_gmail": result = search_gmail(**call.args)
            elif tool_name == "read_gmail_message": result = read_gmail_message(**call.args)
            elif tool_name == "list_gmail_attachments": result = list_gmail_attachments(**call.args)
            elif tool_name == "read_gmail_attachment": result = read_gmail_attachment(**call.args)
            elif tool_name == "search_drive": result = search_drive(**call.args)
            elif tool_name == "read_drive_file": result = read_drive_file(**call.args)
            else: break
            
            response = chat.send_message(types.Content(parts=[types.Part(function_response=types.FunctionResponse(name=tool_name, response={"result": result}))]))
        
        return response.text, getattr(chat, "_curated_history", []), last_tool
