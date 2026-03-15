# AI Personal Assistant: Project Plan

## Original User Request
"Come up with a detailed plan on how to create an AI chatbot that can do the following: 1. Answer questions about my email and search based on what I am looking for. Look at my google photos and provide photos by searching through them based on what I am asking. Extend this functionality to my google drive as well. What would it take to build such a bot. What are the technical details of interacting with the llm (use gemini as the llm). Guide me step by step on how would one build this. Front end can be a next js app. Backend would be python or rust based (help me choose one which one would be preferable). Also the chatbot will slowly learn over time about what I like or dislike and would be able to provide me with general recommendations about food to eat, movies or tv shows to watch, books to read etc."

## 1. Final Architecture (Cloud-Native)
- **Frontend:** Next.js (TypeScript, Tailwind CSS) with dynamic task-status indicators.
- **Backend:** Python (FastAPI) using the modern `google-genai` SDK.
- **LLM:** Google Gemini 2.5 Flash.
- **Database (Cloud Memory):** 
  - **Google Cloud Firestore (Native Mode):** Stores long-term user preferences and identity (e.g., address).
  - **Vertex AI Embeddings (`text-embedding-004`):** Powers semantic vector search within Firestore.
- **Search:** Official **Google Search Grounding** for real-time web information.
- **Auth:** OAuth 2.0 via Google Cloud for Gmail and Drive access.

## 2. Advanced Technical Details
### Smart Routing Logic
The assistant uses a "Router" pattern to bypass Gemini API restrictions:
1. **The Router:** Analyzes the user query and decides if it needs **PERSONAL** data (Gmail/Drive) or **WEB** info (Google Search).
2. **Context Injection:** The user's address and identity are retrieved from **Firestore** and injected into the Router turn.
3. **Query Augmentation:** If a local search is needed, the Router automatically rewrites the user's query to include their address.
4. **Specialist Execution:** The appropriate toolset is called, and the results are synthesized into a natural response.

### Automated Learning
- After every interaction, a background task extracts new factual preferences.
- These facts are vectorized and saved to Firestore.
- Every new session starts by retrieving these "Identity" and "Topic" memories to provide a personalized experience.

## 3. Implementation Status
- [x] **Step 1: Environment Setup:** GCP Project, OAuth, and SDKs.
- [x] **Step 2: Backend Scaffolding:** FastAPI with modern `google-genai`.
- [x] **Step 3: Google Service Integration:** Gmail (Search/Read), Drive (Search/Read), and Calendar (List/Create).
- [x] **Step 4: Cloud Memory Layer:** Firestore Vector Search + Vertex AI.
- [x] **Step 5: Frontend Implementation:** High-contrast chat UI with "Thinking" task indicators.
- [x] **Step 6: Smart Routing:** Context-aware switching between Personal Data and Web Search.

## 4. Maintenance & Security
- `.gitignore` configured to exclude `.env`, `tokens.json`, and credentials.
- Firestore Security Rules set to manage access.
- Cloud Quota Project forced in code to ensure reliable GCP billing/access.

## 5. Next Steps
- Implement **Voice Input/Output** for a hands-free experience.
- Add **Email Drafting** capabilities (allowing the AI to write and stage emails).
- Enhance UI with **Source Citations** for Google Search results.
