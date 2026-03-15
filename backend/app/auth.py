from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
import os
import json
from app.logger import logger
from app.memory import check_onboarding_status, complete_onboarding

router = APIRouter(prefix="/auth", tags=["auth"])
auth_state_store = {}

SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.readonly',
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
async def login():
    config = get_client_config()
    flow = Flow.from_client_config(config, scopes=SCOPES, redirect_uri=config["web"]["redirect_uris"][0])
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='select_account consent')
    auth_state_store[state] = flow.code_verifier
    return {"url": authorization_url}

@router.get("/callback")
async def callback(request: Request):
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
        import requests
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
async def auth_status():
    if not os.path.exists(TOKEN_PATH): return {"authenticated": False}
    with open(TOKEN_PATH, 'r') as f:
        email = json.load(f).get('email')
    onboarded = check_onboarding_status(email)
    logger.info(f"STATUS CHECK: {email} | Onboarded: {onboarded}")
    return {"authenticated": True, "onboarded": onboarded, "email": email}

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
