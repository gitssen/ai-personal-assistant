# AI Personal Assistant: Project Plan

## Original User Request
"Come up with a detailed plan on how to create an AI chatbot that can do the following: 1. Answer questions about my email and search based on what I am looking for. Look at my google photos and provide photos by searching through them based on what I am asking. Extend this functionality to my google drive as well. What would it take to build such a bot. What are the technical details of interacting with the llm (use gemini as the llm). Guide me step by step on how would one build this. Front end can be a next js app. Backend would be python or rust based (help me choose one which one would be preferable). Also the chatbot will slowly learn over time about what I like or dislike and would be able to provide me with general recommendations about food to eat, movies or tv shows to watch, books to read etc."

## 1. High-Level Architecture
- **Frontend:** Next.js (TypeScript, Tailwind CSS).
- **Backend:** Python (FastAPI).
- **LLM:** Google Gemini 2.5 Flash utilizing **Function Calling**.
- **Database (Memory Layer):** 
  - **ChromaDB (Vector Store):** Stores semantic memories, preferences, and interaction summaries as "knowledge nuggets."
- **Auth:** OAuth 2.0 via Google Cloud.

## 2. Technical Implementation Details
### LLM Interaction (Gemini)
- Uses **Function Calling** via `search_gmail`, `search_drive`, and `find_photos`.
- System instructions are dynamically updated with the **current date and time**.

### Long-term Memory & Personalization (NEW)
1.  **Preference Extraction:** After a conversation, a background task asks Gemini to summarize the user's likes/dislikes (e.g., "The user loves sci-fi movies but hates horror").
2.  **Vector Storage:** These summaries are stored in **ChromaDB** as embeddings.
3.  **Memory Retrieval:** For every new message, the backend searches ChromaDB for "relevant memories."
4.  **Context Injection:** These memories are injected into Gemini's prompt (e.g., "Context: You know the user likes Italian food and Christopher Nolan movies").

## 3. Step-by-Step Roadmap
1.  **[DONE] Environment Setup:** Google Cloud Project, OAuth credentials, and API keys.
2.  **[DONE] Backend Scaffolding:** FastAPI server with robust OAuth2 flow.
3.  **[DONE] Google Service Integration:** Email, Drive, and Photos search tools.
4.  **[DONE] AI Orchestration:** Gemini 2.5 Function Calling loop with session history.
5.  **[DONE] Frontend Implementation:** High-contrast, responsive chat UI.
6.  **[IN PROGRESS] Long-term Memory Layer:** 
    - Install `chromadb`.
    - Implement `memory.py` for storage and retrieval.
    - Update `chat.py` to incorporate retrieved context.
7.  **Recommendation Engine:** Fine-tuning the bot to provide personalized food/movie/book suggestions.

## 4. Current Status
- End-to-end functionality (Chat -> Tool Call -> Google API -> Response) is working.
- Backend is running Gemini 2.5 Flash.
- UI is highly readable.

## 5. Next Steps
- Implement ChromaDB integration for cross-session preference tracking.
