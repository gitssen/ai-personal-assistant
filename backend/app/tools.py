import os
import json
import base64
import io
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload
from google import genai
from google.genai import types
from app.memory import save_preference, get_relevant_memories, delete_memory
from app.logger import logger

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

def save_personal_fact(fact: str):
    logger.info(f"Tool save_personal_fact called: {fact}")
    save_preference(fact)
    return f"Success: Remembered '{fact}'"

def delete_personal_fact(fact: str):
    logger.info(f"Tool delete_personal_fact called: {fact}")
    success = delete_memory(fact)
    return f"Success: Forgotten '{fact}'" if success else "Fact not found."

def search_memory(query: str):
    logger.info(f"Tool search_memory called: {query}")
    results = get_relevant_memories(query, n_results=5)
    return "\n".join(results) if results else "No relevant memories."

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
    logger.info(f"search_gmail: {query}")
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
    logger.info(f"read_gmail_message: {message_id}")
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    service = build('gmail', 'v1', credentials=creds)
    m = service.users().messages().get(userId='me', id=message_id, format='full').execute()
    return get_email_body(m['payload']) or "No text found."

def list_gmail_attachments(message_id: str):
    logger.info(f"list_gmail_attachments: {message_id}")
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    service = build('gmail', 'v1', credentials=creds)
    m = service.users().messages().get(userId='me', id=message_id).execute()
    parts = m.get('payload', {}).get('parts', [])
    output = [f"Filename: {p['filename']}\nID: {p['body']['attachmentId']}\nMime: {p['mimeType']}\n---" for p in parts if p.get('filename')]
    return "\n".join(output) if output else "No attachments."

def read_gmail_attachment(message_id: str, attachment_id: str, filename: str, mime_type: str):
    logger.info(f"read_gmail_attachment: {filename}")
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    service = build('gmail', 'v1', credentials=creds)
    attachment = service.users().messages().attachments().get(userId='me', messageId=message_id, id=attachment_id).execute()
    file_data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=[types.Part.from_bytes(data=file_data, mime_type=mime_type), f"Summarize {filename}"])
        return f"SUMMARY OF {filename}:\n{response.text}"
    except Exception as e: return f"Error parsing attachment: {str(e)}"

def search_drive(query: str, max_results: int = 5):
    logger.info(f"search_drive: {query}")
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    safe_query = query.replace("'", "\\'")
    service = build('drive', 'v3', credentials=creds)
    results = service.files().list(q=f"name contains '{safe_query}' or fullText contains '{safe_query}'", pageSize=int(float(max_results)) if max_results else 5, fields="files(id, name, mimeType)").execute()
    files = results.get('files', [])
    output = [f"ID: {f['id']}\nName: {f['name']}\nType: {f['mimeType']}\n---" for f in files]
    return "\n".join(output) if output else "No files found."

def read_drive_file(file_id: str):
    """Read any Drive file (Doc, Sheet, PDF, Image, OR Google Form) using AI parsing."""
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    service = build('drive', 'v3', credentials=creds)
    
    file_metadata = service.files().get(fileId=file_id, fields="name, mimeType").execute()
    mime_type = file_metadata.get('mimeType')
    name = file_metadata.get('name')
    
    logger.info(f"Reading Drive file '{name}' ({mime_type})")
    
    try:
        # SPECIAL CASE: Google Forms
        if mime_type == 'application/vnd.google-apps.form':
            form_service = build('forms', 'v1', credentials=creds)
            form = form_service.forms().get(formId=file_id).execute()
            return f"GOOGLE FORM CONTENT '{name}':\n{json.dumps(form, indent=2)}"

        # Standard cases (Docs, Sheets, Binary)
        if mime_type == 'application/vnd.google-apps.spreadsheet':
            request = service.files().export_media(fileId=file_id, mimeType='text/csv')
        elif mime_type == 'application/vnd.google-apps.document':
            request = service.files().export_media(fileId=file_id, mimeType='text/plain')
        else:
            request = service.files().get_media(fileId=file_id)

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False: status, done = downloader.next_chunk()
        file_data = fh.getvalue()

        if 'text/' in mime_type or 'csv' in mime_type or 'json' in mime_type:
            return f"CONTENT OF {name}:\n{file_data.decode('utf-8')[:5000]}"
        else:
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            response = client.models.generate_content(model="gemini-2.5-flash", contents=[types.Part.from_bytes(data=file_data, mime_type=mime_type), f"Analyze {name}"])
            return f"AI ANALYSIS OF '{name}':\n{response.text}"
            
    except Exception as e:
        logger.error(f"Error in read_drive_file: {str(e)}")
        return f"Error reading file '{name}': {str(e)}"
