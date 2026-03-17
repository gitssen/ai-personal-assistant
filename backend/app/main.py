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

from fastapi.responses import StreamingResponse
from app.chat import chat_with_assistant, serialize_history

@app.post("/chat")
async def chat(msg: ChatMessage):
    try:
        return StreamingResponse(
            chat_with_assistant(msg.message, history=msg.history),
            media_type="application/x-ndjson"
        )
    except Exception as e:
        logger.exception(f"CHAT ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def root():
    return {"message": "AI Personal Assistant API is running (Google-GenAI SDK)"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
