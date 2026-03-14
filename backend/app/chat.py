import google.generativeai as genai
import os
from datetime import datetime
from app.tools import search_gmail, search_drive, read_drive_file, find_photos
from app.memory import get_relevant_memories, save_preference

def get_chat_model(memories=None):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    custom_tools = [search_gmail, search_drive, read_drive_file, find_photos]
    
    current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
    memory_context = ""
    if memories:
        memory_context = "\nRELEVANT INFORMATION ABOUT THE USER:\n- " + "\n- ".join(memories)
        
    system_instruction = (
        f"You are a helpful personal assistant with access to the user's Google data and internal knowledge. "
        f"The current date and time is {current_time}. {memory_context}\n"
        f"Use the memory context to personalize your recommendations (food, movies, books). "
        f"If the user tells you about a new like or dislike, confirm it and say 'I'll remember that!'"
    )
    
    model = genai.GenerativeModel(
        model_name="models/gemini-2.5-flash",
        tools=custom_tools,
        system_instruction=system_instruction
    )
    return model

def chat_with_assistant(user_message: str, history=None):
    # 1. Retrieve relevant memories before starting
    memories = get_relevant_memories(user_message)
    
    formatted_history = []
    if history:
        for entry in history:
            formatted_history.append({"role": entry.get("role"), "parts": entry.get("parts")})

    model = get_chat_model(memories=memories)
    chat = model.start_chat(history=formatted_history)
    
    response = chat.send_message(user_message)
    
    # Tool call loop
    while True:
        has_function_call = False
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    has_function_call = True
                    call = part.function_call
                    tool_name = call.name
                    tool_args = {k: v for k, v in call.args.items()}
                    
                    if tool_name == "search_gmail": result = search_gmail(**tool_args)
                    elif tool_name == "search_drive": result = search_drive(**tool_args)
                    elif tool_name == "read_drive_file": result = read_drive_file(**tool_args)
                    elif tool_name == "find_photos": result = find_photos(**tool_args)
                    else: break
                    
                    response = chat.send_message(
                        genai.protos.Content(
                            parts=[genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=tool_name,
                                    response={'result': result}
                                )
                            )]
                        )
                    )
                    break
        if not has_function_call: break

    # 3. Post-conversation memory extraction
    # We ask Gemini to summarize any NEW preferences from this exchange
    try:
        extraction_model = genai.GenerativeModel("models/gemini-2.5-flash")
        extraction_prompt = (
            f"Extract any NEW personal preferences (likes, dislikes, hobbies) from this exchange. "
            f"User: '{user_message}'\nAssistant: '{response.text}'\n"
            f"Only return the facts as a list or 'None' if nothing new was learned."
        )
        fact_response = extraction_model.generate_content(extraction_prompt)
        if "None" not in fact_response.text:
            for fact in fact_response.text.strip().split("\n"):
                if fact.strip():
                    save_preference(fact.strip("- "))
    except Exception as e:
        print(f"DEBUG: Memory extraction failed: {e}")

    try:
        return response.text, chat.history
    except ValueError:
        return "I found the info but can't display it.", chat.history
