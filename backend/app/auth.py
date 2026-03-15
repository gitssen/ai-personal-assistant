from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
import os
import json
from app.logger import logger

router = APIRouter(prefix="/auth", tags=["auth"])
auth_state_store = {}

SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
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
    # We use prompt='select_account consent' to ensure a totally fresh login
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='select_account consent'
    )
    auth_state_store[state] = flow.code_verifier
    return RedirectResponse(authorization_url)

@router.get("/callback")
async def callback(request: Request):
    state = request.query_params.get("state")
    code = request.query_params.get("code")
    code_verifier = auth_state_store.get(state)
    
    if not code or not code_verifier:
        raise HTTPException(status_code=400, detail="OAuth state missing. Try logging in again.")
        
    try:
        config = get_client_config()
        flow = Flow.from_client_config(config, scopes=SCOPES, redirect_uri=config["web"]["redirect_uris"][0], state=state)
        flow.code_verifier = code_verifier
        
        # This is where the error happens. We catch it to see the REAL reason.
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        with open(TOKEN_PATH, 'w') as f:
            json.dump({
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }, f)
            
        del auth_state_store[state]
        return {"message": "Success! You are logged in."}
        
    except Exception as e:
        logger.error(f"DEBUG: OAUTH FETCH TOKEN ERROR: {str(e)}")
        # If redirect_uri_mismatch or invalid_client, it will show up here
        raise HTTPException(status_code=400, detail=f"Google Login Failed: {str(e)}")

@router.get("/status")
async def auth_status():
    return {"authenticated": os.path.exists(TOKEN_PATH)}
