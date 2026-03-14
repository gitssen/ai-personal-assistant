import os
import json
import base64
import io
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload

TOKEN_PATH = "tokens.json"

def get_google_creds():
    if not os.path.exists(TOKEN_PATH):
        return None
    
    with open(TOKEN_PATH, 'r') as f:
        creds_data = json.load(f)
    
    creds = Credentials(
        token=creds_data['token'],
        refresh_token=creds_data.get('refresh_token'),
        token_uri=creds_data['token_uri'],
        client_id=creds_data['client_id'],
        client_secret=creds_data['client_secret'],
        scopes=creds_data['scopes']
    )
    
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        creds_data['token'] = creds.token
        with open(TOKEN_PATH, 'w') as f:
            json.dump(creds_data, f)
            
    return creds

def get_email_body(payload):
    if 'parts' in payload:
        for part in payload['parts']:
            body = get_email_body(part)
            if body:
                return body
    if payload.get('mimeType') == 'text/plain':
        data = payload.get('body', {}).get('data')
        if data:
            return base64.urlsafe_b64decode(data).decode('utf-8')
    return None

def search_gmail(query: str, max_results: int = 5):
    """Search for emails. Returns subject, sender, and full body text."""
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
    messages = results.get('messages', [])
    output = []
    for msg in messages:
        m = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        headers = m['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        body = get_email_body(m['payload'])
        content = body if body else m.get('snippet', '')
        if len(content) > 2000:
            content = content[:2000] + "... [truncated]"
        output.append(f"From: {sender}\nSubject: {subject}\nContent: {content}\n---")
    return "\n".join(output) if output else "No emails found."

def search_drive(query: str, max_results: int = 5):
    """Find files in Google Drive. Returns a list of filenames and their IDs. USE THIS FIRST TO FIND THE ID OF A FILE."""
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    service = build('drive', 'v3', credentials=creds)
    results = service.files().list(
        q=f"name contains '{query}' or fullText contains '{query}'",
        pageSize=max_results, 
        fields="files(id, name, mimeType, webViewLink)"
    ).execute()
    files = results.get('files', [])
    output = []
    for f in files:
        output.append(f"ID: {f['id']}\nName: {f['name']}\nType: {f['mimeType']}\n---")
    return "\n".join(output) if output else "No files found."

def read_drive_file(file_id: str):
    """READ the content (text/data) inside a specific Google Drive file using its ID. Use this for Google Sheets, Docs, and Text files."""
    print(f"DEBUG: Tool read_drive_file called for ID: {file_id}")
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    service = build('drive', 'v3', credentials=creds)
    
    file_metadata = service.files().get(fileId=file_id, fields="name, mimeType").execute()
    mime_type = file_metadata.get('mimeType')
    name = file_metadata.get('name')
    
    try:
        if mime_type == 'application/vnd.google-apps.spreadsheet':
            # Export first sheet as CSV
            request = service.files().export_media(fileId=file_id, mimeType='text/csv')
        elif mime_type == 'application/vnd.google-apps.document':
            request = service.files().export_media(fileId=file_id, mimeType='text/plain')
        elif 'text/' in mime_type or mime_type == 'application/json':
            request = service.files().get_media(fileId=file_id)
        else:
            return f"Cannot read {mime_type} files. I can only read Docs, Sheets, and Text."

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        
        content = fh.getvalue().decode('utf-8')
        return f"CONTENT OF '{name}':\n{content[:5000]}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

def find_photos(description: str, max_results: int = 5):
    """List recent photos from Google Photos."""
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    import requests
    headers = {"Authorization": f"Bearer {creds.token}"}
    response = requests.get("https://photoslibrary.googleapis.com/v1/mediaItems", headers=headers, params={"pageSize": max_results})
    if response.status_code != 200: return f"Error: {response.text}"
    items = response.json().get('mediaItems', [])
    output = []
    for item in items:
        output.append(f"Photo: {item.get('filename')}\nURL: {item.get('productUrl')}\n---")
    return "\n".join(output) if output else "No photos found."
