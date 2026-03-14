import google.generativeai as genai
import os
from datetime import datetime
from app.tools import search_gmail, read_gmail_message, search_drive, read_drive_file
from app.memory import get_relevant_memories, save_preference

def get_chat_model(memories=None):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    custom_tools = [search_gmail, read_gmail_message, search_drive, read_drive_file]
    
    current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
    memory_context = ""
    if memories:
        memory_context = "\nRELEVANT INFORMATION ABOUT THE USER:\n- " + "\n- ".join(memories)
        
    system_instruction = (
        f"You are a helpful personal assistant with access to the user's Gmail and Google Drive. "
        f"The current date and time is {current_time}. {memory_context}\n"
        f"MANDATORY BEHAVIOR:\n"
        f"1. SYNTHESIZE: Never show raw tool output, file IDs, or JSON-like structures to the user. "
        f"   Instead, read the data and explain it in natural, friendly language.\n"
        f"2. DATA-FIRST: Always search Gmail and Drive before answering general questions.\n"
        f"3. NO LEAKS: If you find a file ID or message ID, use it internally. Never show IDs to the user unless they ask for a technical detail.\n"
        f"4. GMAIL & DRIVE: Use the tools to find and read content. Summarize what you find clearly."
    )
    
    model = genai.GenerativeModel(
        model_name="models/gemini-2.5-flash",
        tools=custom_tools,
        system_instruction=system_instruction
    )
    return model

def chat_with_assistant(user_message: str, history=None):
    memories = get_relevant_memories(user_message)
    formatted_history = []
    if history:
        for entry in history:
            formatted_history.append({"role": entry.get("role"), "parts": entry.get("parts")})

    model = get_chat_model(memories=memories)
    chat = model.start_chat(history=formatted_history)
    
    # Send the user message
    try:
        response = chat.send_message(user_message)
    except Exception as e:
        print(f"DEBUG: Initial send error: {e}")
        return "I encountered an error starting the conversation. Could you try rephrasing your request?", chat.history
    
    # Process potential chain of tool calls
    max_turns = 10
    for _ in range(max_turns):
        try:
            # Check if the last response contains a function call
            if not response.candidates or not response.candidates[0].content.parts:
                break
                
            function_calls = [p.function_call for p in response.candidates[0].content.parts if p.function_call]
            
            if not function_calls:
                break 
                
            function_responses = []
            for call in function_calls:
                tool_name = call.name
                tool_args = {k: v for k, v in call.args.items()}
                
                print(f"DEBUG: EXECUTION - Gemini calling '{tool_name}'")
                
                # Sanitize numeric args for all tools
                if "max_results" in tool_args:
                    tool_args["max_results"] = int(float(tool_args["max_results"]))
                
                if tool_name == "search_gmail": result = search_gmail(**tool_args)
                elif tool_name == "read_gmail_message": result = read_gmail_message(**tool_args)
                elif tool_name == "search_drive": result = search_drive(**tool_args)
                elif tool_name == "read_drive_file": result = read_drive_file(**tool_args)
                else: result = f"Error: Tool '{tool_name}' not found."
                
                function_responses.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=tool_name,
                            response={'result': result}
                        )
                    )
                )
                
            response = chat.send_message(genai.protos.Content(parts=function_responses))
        except Exception as e:
            print(f"DEBUG: Tool execution error: {e}")
            return "I had trouble processing that request. Could you try asking in a different way?", chat.history

    # After the loop, the final 'response' should contain synthesized text
    try:
        return response.text, chat.history
    except ValueError:
        # Fallback if the model is still stuck in a function turn
        return "I've gathered the information from your files. What specific detail would you like to know?", chat.history
