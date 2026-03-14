import google.generativeai as genai
import os
from datetime import datetime
from app.tools import search_gmail, search_drive, read_drive_file, find_photos

def get_chat_model():
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    
    # Custom Python Tools for your data
    custom_tools = [search_gmail, search_drive, read_drive_file, find_photos]
    
    # We REMOVE the built-in google_search tool here.
    # This forces Gemini to use its internal LLM knowledge for general questions.
    
    current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
    
    system_instruction = (
        f"You are a highly capable personal assistant. The current date and time is {current_time}. "
        f"1. For personal data (emails, files, photos), use the provided tools. "
        f"2. For general questions, recommendations (movies, food, books), or news, use your internal knowledge. "
        f"3. If a user asks for a recommendation, base it on what you know about the current year ({datetime.now().year}) "
        f"and your extensive training data."
    )
    
    model = genai.GenerativeModel(
        model_name="models/gemini-2.5-flash",
        tools=custom_tools,
        system_instruction=system_instruction
    )
    return model

def chat_with_assistant(user_message: str, history=None):
    formatted_history = []
    if history:
        for entry in history:
            formatted_history.append({"role": entry.get("role"), "parts": entry.get("parts")})

    model = get_chat_model()
    chat = model.start_chat(history=formatted_history)
    
    response = chat.send_message(user_message)
    
    # Handle custom tool calls
    while True:
        has_function_call = False
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    has_function_call = True
                    call = part.function_call
                    tool_name = call.name
                    tool_args = {k: v for k, v in call.args.items()}
                    
                    print(f"DEBUG: Executing personal data tool '{tool_name}'")
                    
                    if tool_name == "search_gmail": result = search_gmail(**tool_args)
                    elif tool_name == "search_drive": result = search_drive(**tool_args)
                    elif tool_name == "read_drive_file": result = read_drive_file(**tool_args)
                    elif tool_name == "find_photos": result = find_photos(**tool_args)
                    else:
                        result = f"Error: Tool '{tool_name}' not found."
                    
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
        
        if not has_function_call:
            break

    try:
        return response.text, chat.history
    except ValueError:
        return "I found the information but I'm having trouble displaying it. Please try again.", chat.history
