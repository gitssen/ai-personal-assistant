import os
import json
import base64
import io
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload
from google import genai
from google.genai import types
from app.memory import save_preference, delete_memory, get_relevant_memories
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

def get_user_email():
    if not os.path.exists(TOKEN_PATH): return None
    with open(TOKEN_PATH, 'r') as f:
        return json.load(f).get('email')

def save_personal_fact(fact: str):
    email = get_user_email()
    if not email: return "Error: User not found."
    save_preference(email, fact)
    return f"Success: Remembered '{fact}'"

def delete_personal_fact(fact: str):
    email = get_user_email()
    if not email: return "Error: User not found."
    success = delete_memory(email, fact)
    return f"Success: Forgotten '{fact}'" if success else "Fact not found."

def search_memory(query: str):
    email = get_user_email()
    if not email: return "Error: Not authenticated."
    results = get_relevant_memories(email, query, n_results=5)
    return "\n".join(results) if results else "No relevant memories."

# ... [rest of tools: search_gmail, read_gmail_message, etc. remain unchanged] ...

def get_email_body(payload):
    if 'parts' in payload:
        for part in payload['parts']:
            body = get_email_body(part)
            if body: return body
    if payload.get('mimeType') == 'text/plain':
        data = payload.get('body', {}).get('data')
        if data: return base64.urlsafe_b64decode(data).decode('utf-8')
    return None

from email.message import EmailMessage

def create_gmail_draft(subject: str, body: str, to: str = None):
    """Creates a draft email in the user's Gmail account. subject is the email subject, body is the content, and to is the optional recipient email."""
    logger.info(f"🚀 EXECUTING GMAIL DRAFT TOOL: To={to}, Subject={subject}")
    try:
        creds = get_google_creds()
        if not creds: return "Error: Not authenticated"
        service = build('gmail', 'v1', credentials=creds)
        
        message = EmailMessage()
        message.set_content(body)
        if to:
            message['To'] = to
        message['Subject'] = subject
        
        # encoded message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        create_message = {
            'message': {
                'raw': encoded_message
            }
        }
        
        draft = service.users().drafts().create(userId='me', body=create_message).execute()
        return f"Draft created successfully. Draft ID: {draft['id']}"
    except Exception as e:
        logger.error(f"Gmail Draft Error: {str(e)}")
        return f"Error creating draft: {str(e)}"

def search_gmail(query: str, max_results: int = 5):
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
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    service = build('gmail', 'v1', credentials=creds)
    m = service.users().messages().get(userId='me', id=message_id, format='full').execute()
    return get_email_body(m['payload']) or "No text found."

def list_gmail_attachments(message_id: str):
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    service = build('gmail', 'v1', credentials=creds)
    m = service.users().messages().get(userId='me', id=message_id).execute()
    parts = m.get('payload', {}).get('parts', [])
    output = [f"Filename: {p['filename']}\nID: {p['body']['attachmentId']}\nMime: {p['mimeType']}\n---" for p in parts if p.get('filename')]
    return "\n".join(output) if output else "No attachments."

def read_gmail_attachment(message_id: str, attachment_id: str, filename: str, mime_type: str):
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
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    safe_query = query.replace("'", "\\'")
    service = build('drive', 'v3', credentials=creds)
    results = service.files().list(q=f"name contains '{safe_query}' or fullText contains '{safe_query}'", pageSize=int(float(max_results)) if max_results else 5, fields="files(id, name, mimeType)").execute()
    files = results.get('files', [])
    output = [f"ID: {f['id']}\nName: {f['name']}\nType: {f['mimeType']}\n---" for f in files]
    return "\n".join(output) if output else "No files found."

def read_drive_file(file_id: str):
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    service = build('drive', 'v3', credentials=creds)
    file_metadata = service.files().get(fileId=file_id, fields="name, mimeType").execute()
    mime_type = file_metadata.get('mimeType')
    try:
        if mime_type == 'application/vnd.google-apps.form':
            form_service = build('forms', 'v1', credentials=creds)
            form = form_service.forms().get(formId=file_id).execute()
            return f"GOOGLE FORM CONTENT '{file_metadata['name']}':\n{json.dumps(form, indent=2)}"
        if mime_type == 'application/vnd.google-apps.spreadsheet': request = service.files().export_media(fileId=file_id, mimeType='text/csv')
        elif mime_type == 'application/vnd.google-apps.document': request = service.files().export_media(fileId=file_id, mimeType='text/plain')
        else: request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False: status, done = downloader.next_chunk()
        file_data = fh.getvalue()
        if 'text/' in mime_type or 'csv' in mime_type or 'json' in mime_type: return f"CONTENT OF {file_metadata['name']}:\n{file_data.decode('utf-8')[:5000]}"
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(model="gemini-2.5-flash", contents=[types.Part.from_bytes(data=file_data, mime_type=mime_type), f"Analyze {file_metadata['name']}"])
        return f"AI ANALYSIS OF '{file_metadata['name']}':\n{response.text}"
    except Exception as e: return f"Error: {str(e)}"

def list_calendar_events(query: str = None, time_min: str = None, time_max: str = None, max_results: int = 10):
    """Lists or searches calendar events. query is optional for searching. time_min/max should be ISO format (e.g. 2024-03-24T00:00:00Z)."""
    try:
        creds = get_google_creds()
        if not creds: return "Error: Not authenticated"
        service = build('calendar', 'v3', credentials=creds)
        
        events_result = service.events().list(
            calendarId='primary', 
            q=query,
            timeMin=time_min or datetime.utcnow().isoformat() + 'Z',
            timeMax=time_max,
            maxResults=max_results, 
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        
        if not events: return "No events found."
        
        output = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            output.append(f"ID: {event['id']}\nSummary: {event['summary']}\nStart: {start}\n---")
        return "\n".join(output)
    except Exception as e:
        logger.error(f"Calendar List Error: {str(e)}")
        return f"Error accessing calendar: {str(e)}. (Hint: Make sure the Calendar API is enabled and you have re-logged in if you just enabled it.)"

def create_calendar_event(summary: str, start_time: str, end_time: str, description: str = None, location: str = None, timezone: str = "UTC", attendees: list[str] = None):
    """Creates a calendar event. Times must be ISO format (e.g., 2024-03-24T10:00:00). attendees is a list of emails."""
    try:
        creds = get_google_creds()
        if not creds: return "Error: Not authenticated"
        service = build('calendar', 'v3', credentials=creds)
        
        event = {
            'summary': summary,
            'location': location,
            'description': description,
            'start': {'dateTime': start_time, 'timeZone': timezone},
            'end': {'dateTime': end_time, 'timeZone': timezone},
        }
        
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]
        
        event = service.events().insert(calendarId='primary', body=event, sendUpdates='all').execute()
        return f"Event created successfully. ID: {event.get('id')} | Link: {event.get('htmlLink')}"
    except Exception as e:
        logger.error(f"Calendar Create Error: {str(e)}")
        return f"Error creating event: {str(e)}"

def update_calendar_event(event_id: str, summary: str = None, start_time: str = None, end_time: str = None, description: str = None, location: str = None, attendees: list[str] = None):
    """Updates an existing calendar event by ID. attendees is a list of emails."""
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    service = build('calendar', 'v3', credentials=creds)
    
    event = service.events().get(calendarId='primary', eventId=event_id).execute()
    if summary: event['summary'] = summary
    if location: event['location'] = location
    if description: event['description'] = description
    if start_time: event['start']['dateTime'] = start_time
    if end_time: event['end']['dateTime'] = end_time
    if attendees:
        event['attendees'] = [{'email': email} for email in attendees]
    
    updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event, sendUpdates='all').execute()
    return f"Event updated: {updated_event.get('htmlLink')}"

def delete_calendar_event(event_id: str):
    """Deletes a calendar event by ID."""
    creds = get_google_creds()
    if not creds: return "Error: Not authenticated"
    service = build('calendar', 'v3', credentials=creds)
    service.events().delete(calendarId='primary', eventId=event_id).execute()
    return "Event deleted successfully."
