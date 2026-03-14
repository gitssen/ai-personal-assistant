import os
import json
import base64
import io
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload
from duckduckgo_search import DDGS

TOKEN_PATH = "tokens.json"

def get_google_creds():
    if not os.path.exists(TOKEN_PATH): return None
    with open(TOKEN_PATH, 'r') as f:
        creds_data = json.load(f)
    creds = Credentials(
        token=creds_data['token'], refresh_token=creds_data.get('refresh_token'),
        token_uri=creds_data['token_uri'], client_id=creds_data['client_id'],
        client_secret=creds_data['client_secret'], scopes=creds_data['scopes']
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        creds_data['token'] = creds.token
        with open(TOKEN_PATH, 'w') as f: json.dump(creds_data, f)
    return creds

def get_email_body(payload):
    if 'parts' in payload:
        for part in payload['parts']:
            body = get_email_body(part)
            if body: return body
    if payload.get('mimeType') == 'text/plain':
        data = payload.get('body', {}).get('data')
        if data: return base64.urlsafe_b64decode(data).decode('utf-8')
    return None

def search_gmail(query: str, max_results: int = 5):
    """Search for emails. Returns subject, sender, and IDs."""
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
        output.append(f"ID: {msg['id']}\nFrom: {sender}\nSubject: {subject}\nSnippet: {m.get('snippet')}\n---")
    return "\n".join(output) if output else "No emails found."

def read_gmail_message(message_id: str):
    """Read the FULL content of an email."""
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    service = build('gmail', 'v1', credentials=creds)
    m = service.users().messages().get(userId='me', id=message_id, format='full').execute()
    body = get_email_body(m['payload'])
    return body if body else "No text found."

def search_drive(query: str, max_results: int = 5):
    """Find files in Google Drive."""
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    safe_query = query.replace("'", "\\'")
    service = build('drive', 'v3', credentials=creds)
    results = service.files().list(q=f"name contains '{safe_query}' or fullText contains '{safe_query}'", pageSize=int(float(max_results)) if max_results else 5, fields="files(id, name, mimeType)").execute()
    files = results.get('files', [])
    output = []
    for f in files:
        output.append(f"ID: {f['id']}\nName: {f['name']}\nType: {f['mimeType']}\n---")
    return "\n".join(output) if output else "No files found."

def read_drive_file(file_id: str):
    """Read file content from Google Drive."""
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    service = build('drive', 'v3', credentials=creds)
    file_metadata = service.files().get(fileId=file_id, fields="name, mimeType").execute()
    mime_type = file_metadata.get('mimeType')
    try:
        if mime_type == 'application/vnd.google-apps.spreadsheet': request = service.files().export_media(fileId=file_id, mimeType='text/csv')
        elif mime_type == 'application/vnd.google-apps.document': request = service.files().export_media(fileId=file_id, mimeType='text/plain')
        else: request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False: status, done = downloader.next_chunk()
        return fh.getvalue().decode('utf-8')[:5000]
    except Exception as e: return f"Error: {str(e)}"

def web_search(query: str, max_results: int = 5):
    """Search the live web for real-time information."""
    print(f"DEBUG: Web search for: {query}")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results: return "No results found."
            output = []
            for r in results:
                output.append(f"Title: {r['title']}\nSnippet: {r['body']}\nLink: {r['href']}\n---")
            return "\n".join(output)
    except Exception as e:
        return f"Web search failed: {str(e)}"
