import os
from dotenv import load_dotenv
# Load environment variables first
load_dotenv()

from app.logger import logger
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from typing import List, Optional
from app.auth import router as auth_router
from app.chat import chat_with_assistant
from app.logger import logger

app = FastAPI(title="AI Personal Assistant API")

class ChatMessage(BaseModel):
    message: str
    history: Optional[List[dict]] = None

# Configure CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

def serialize_history(history):
    """Converts the new google.genai history objects into a JSON-friendly format for persistent multi-turn tool use."""
    serialized = []
    if not history: return []
    
    for content in history:
        role = content.role
        parts = []
        for part in content.parts:
            # Handle text parts
            if hasattr(part, 'text') and part.text:
                parts.append({"text": part.text})
            # Handle tool calls
            elif hasattr(part, 'function_call') and part.function_call:
                parts.append({
                    "function_call": {
                        "name": part.function_call.name,
                        "args": part.function_call.args
                    }
                })
            # Handle tool responses
            elif hasattr(part, 'function_response') and part.function_response:
                parts.append({
                    "function_response": {
                        "name": part.function_response.name,
                        "response": part.function_response.response
                    }
                })
        if parts:
            serialized.append({"role": role, "parts": parts})
    return serialized

@app.post("/chat")
async def chat(msg: ChatMessage):
    try:
        response_text, updated_history, last_tool = chat_with_assistant(msg.message, history=msg.history)
        return {
            "response": response_text, 
            "history": serialize_history(updated_history),
            "task": last_tool
        }
    except Exception as e:
        logger.exception(f"CHAT ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "AI Personal Assistant API is running (Google-GenAI SDK)"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
