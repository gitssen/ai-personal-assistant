from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
import os
import json

router = APIRouter(prefix="/auth", tags=["auth"])

# Global dictionary to store code_verifiers by state
# (Works perfectly for local, single-user apps)
auth_state_store = {}

SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/photoslibrary.readonly'
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
    flow = Flow.from_client_config(
        config,
        scopes=SCOPES,
        redirect_uri=config["web"]["redirect_uris"][0]
    )
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    # Store the verifier globally keyed by the state
    auth_state_store[state] = flow.code_verifier
    
    # Redirect the browser directly to Google
    return RedirectResponse(authorization_url)

@router.get("/callback")
async def callback(request: Request):
    state = request.query_params.get("state")
    code = request.query_params.get("code")
    
    # Retrieve the code verifier from our global store
    code_verifier = auth_state_store.get(state)
    
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    
    if not code_verifier:
        print(f"ERROR: No verifier found for state: {state}")
        print(f"Current Store Keys: {list(auth_state_store.keys())}")
        raise HTTPException(status_code=400, detail="State mismatch or session expired")
        
    config = get_client_config()
    flow = Flow.from_client_config(
        config,
        scopes=SCOPES,
        redirect_uri=config["web"]["redirect_uris"][0],
        state=state
    )
    
    flow.code_verifier = code_verifier
    flow.fetch_token(code=code)
    credentials = flow.credentials
    
    creds_data = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    with open(TOKEN_PATH, 'w') as f:
        json.dump(creds_data, f)
        
    # Clean up
    del auth_state_store[state]
    
    return {"message": "Successfully authenticated! You can close this tab and return to the app."}

@router.get("/status")
async def auth_status():
    if os.path.exists(TOKEN_PATH):
        return {"authenticated": True}
    return {"authenticated": False}
