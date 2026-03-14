from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
from dotenv import load_dotenv
from app.auth import router as auth_router
from app.chat import chat_with_assistant

load_dotenv()

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
    """Converts Gemini history into a serializable list of dicts."""
    serialized = []
    for content in history:
        parts = []
        for part in content.parts:
            # Check for different part types (text vs function_call)
            if hasattr(part, 'text') and part.text:
                parts.append({"text": part.text})
            elif hasattr(part, 'function_call') and part.function_call:
                parts.append({
                    "function_call": {
                        "name": part.function_call.name,
                        "args": {k: v for k, v in part.function_call.args.items()}
                    }
                })
            elif hasattr(part, 'function_response') and part.function_response:
                parts.append({
                    "function_response": {
                        "name": part.function_response.name,
                        "response": part.function_response.response
                    }
                })
        serialized.append({"role": content.role, "parts": parts})
    return serialized

@app.post("/chat")
async def chat(msg: ChatMessage):
    try:
        response_text, updated_history = chat_with_assistant(msg.message, history=msg.history)
        return {
            "response": response_text, 
            "history": serialize_history(updated_history)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "AI Personal Assistant API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
