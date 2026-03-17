from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google import genai
from google.genai import types
from google.cloud import storage
import os
import json
import requests
from app.logger import logger
from app.memory import check_onboarding_status, complete_onboarding, save_preference, get_relevant_memories

router = APIRouter(prefix="/auth", tags=["auth"])
auth_state_store = {}

SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/forms.body.readonly',
    'https://www.googleapis.com/auth/photospicker.mediaitems.readonly'
]

TOKEN_PATH = "tokens.json"

def get_client_config():
    return {
        "web": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI")]
        }
    }

@router.get("/login")
def login():
    config = get_client_config()
    flow = Flow.from_client_config(config, scopes=SCOPES, redirect_uri=config["web"]["redirect_uris"][0])
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='select_account consent')
    auth_state_store[state] = flow.code_verifier
    return {"url": authorization_url}

@router.get("/callback")
def callback(request: Request):
    state = request.query_params.get("state")
    code = request.query_params.get("code")
    code_verifier = auth_state_store.get(state)
    if not code or not code_verifier: raise HTTPException(status_code=400, detail="Expired")
    
    try:
        config = get_client_config()
        flow = Flow.from_client_config(config, scopes=SCOPES, redirect_uri=config["web"]["redirect_uris"][0], state=state)
        flow.code_verifier = code_verifier
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Get user email
        res = requests.get(f"https://www.googleapis.com/oauth2/v1/userinfo?access_token={credentials.token}")
        email = res.json().get("email")

        with open(TOKEN_PATH, 'w') as f:
            json.dump({
                'token': credentials.token, 'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri, 'client_id': credentials.client_id,
                'client_secret': credentials.client_secret, 'scopes': credentials.scopes,
                'email': email
            }, f)
            
        del auth_state_store[state]
        return RedirectResponse("http://localhost:3000") # Redirect back to frontend
    except Exception as e:
        logger.error(f"OAuth failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/status")
def auth_status():
    if not os.path.exists(TOKEN_PATH): return {"authenticated": False}
    with open(TOKEN_PATH, 'r') as f:
        email = json.load(f).get('email')
    onboarded = check_onboarding_status(email)
    logger.info(f"STATUS CHECK: {email} | Onboarded: {onboarded}")
    return {"authenticated": True, "onboarded": onboarded, "email": email}

@router.get("/memories/raw")
def get_raw_memories(offset: int = 0, limit: int = 50):
    """Reads extracted_personal_facts.json with pagination support."""
    if not os.path.exists(TOKEN_PATH): raise HTTPException(status_code=401)
    with open(TOKEN_PATH, 'r') as f: email = json.load(f).get('email')

    file_path = "extracted_personal_facts.json"
    gcs_bucket = os.getenv("GCS_MEMORIES_BUCKET")

    # 1. Sync from GCS (only on first page to be efficient)
    if offset == 0 and gcs_bucket:
        try:
            storage_client = storage.Client()
            bucket = storage_client.bucket(gcs_bucket)
            blob = bucket.blob(f"raw_facts_{email}.json")
            if blob.exists():
                blob.download_to_filename(file_path)
                logger.info(f"Synced {file_path} from GCS")
        except Exception as e:
            logger.error(f"GCS Sync failed: {e}")

    if not os.path.exists(file_path):
        return {"categories": {}, "total": 0, "has_more": False}

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if not data: return {"categories": {}, "total": 0, "has_more": False}
        
        raw_facts = [item['fact'] for item in data]
        total_count = len(raw_facts)
        
        # SLICE FOR PAGINATION
        chunk = raw_facts[offset : offset + limit]
        has_more = (offset + limit) < total_count
        
        if not chunk:
            return {"categories": {}, "total": total_count, "has_more": has_more}

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        prompt = f"""
        Analyze these personal facts extracted from emails and return a JSON object.
        1. Remove exact duplicates and merge overlapping facts.
        2. Categorize into: Identity, Family, Home, Preferences, Work, Miscellaneous.
        3. The response MUST be a valid JSON object where keys are the category names and values are lists of strings.
        
        FACTS TO PROCESS:
        {json.dumps(chunk)}
        """
        
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    response_schema={
                        'type': 'OBJECT',
                        'properties': {
                            'Identity': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
                            'Family': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
                            'Home': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
                            'Preferences': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
                            'Work': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
                            'Miscellaneous': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
                        }
                    }
                )
            )
            
            # Use .parsed if available in the new SDK, otherwise cleanup text
            if hasattr(response, 'parsed') and response.parsed:
                categories = response.parsed
            else:
                clean_text = response.text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text.split("```json")[1].split("```")[0].strip()
                categories = json.loads(clean_text)
        except Exception as parse_err:
            logger.error(f"JSON Parsing failed: {parse_err}. Raw text: {response.text}")
            # Fallback: Just put everything in Miscellaneous if AI fails to categorize properly
            categories = {"Miscellaneous": chunk}

        from concurrent.futures import ThreadPoolExecutor
        
        def check_if_known(fact):
            try:
                # Check if this fact is already known semantically
                existing = get_relevant_memories(email, fact, n_results=1)
                return (fact, False if existing else True)
            except:
                return (fact, True) # Fallback: show it if check fails

        # Flatten all facts to check them in one single parallel batch
        all_candidate_facts = []
        for cat_facts in categories.values():
            all_candidate_facts.extend(cat_facts)
        
        # Remove exact duplicates from the Gemini output before checking cloud memory
        all_candidate_facts = list(set(all_candidate_facts))

        fact_status = {}
        with ThreadPoolExecutor(max_workers=15) as executor:
            results = list(executor.map(check_if_known, all_candidate_facts))
            for fact, is_new in results:
                fact_status[fact] = is_new

        # Filter the original categorized structure
        filtered_categories = {}
        for category, facts in categories.items():
            new_facts = [f for f in facts if fact_status.get(f)]
            if new_facts:
                filtered_categories[category] = new_facts

        return {
            "categories": filtered_categories, 
            "total": total_count,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None
        }
        
    except Exception as e:
        logger.error(f"Failed to process raw memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/memories/import")
def import_memories(data: dict):
    """Saves a list of user-approved facts into long-term cloud memory."""
    facts = data.get("facts", [])
    if not facts: return {"success": True, "count": 0}
    
    if not os.path.exists(TOKEN_PATH):
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    with open(TOKEN_PATH, 'r') as f:
        email = json.load(f).get('email')
        
    from concurrent.futures import ThreadPoolExecutor
    
    def save_single(fact):
        try:
            save_preference(email, fact)
            return True
        except:
            return False

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(save_single, facts))
        
    success_count = sum(1 for r in results if r)
    return {"success": True, "count": success_count}

@router.post("/logout")
async def logout():
    if os.path.exists(TOKEN_PATH):
        os.remove(TOKEN_PATH)
    return {"success": True}

@router.post("/onboard")
async def onboard(data: dict):
    with open(TOKEN_PATH, 'r') as f:
        email = json.load(f).get('email')
    complete_onboarding(email, data)
    return {"success": True}
