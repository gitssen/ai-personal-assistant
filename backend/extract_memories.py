import os
import json
import sys
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from googleapiclient.discovery import build
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.tools import get_google_creds, get_email_body

def process_single_email(msg_id, creds):
    """Worker function to process one email and extract facts. 
    Creates its own service instances to be thread-safe."""
    try:
        # Create thread-local service instances
        gmail_service = build('gmail', 'v1', credentials=creds)
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

        m = gmail_service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        subject = next((h['value'] for h in m['payload']['headers'] if h['name'] == 'Subject'), 'No Subject')
        body = get_email_body(m['payload'])
        
        if not body:
            return subject, []

        prompt = f"""
        Analyze the following email and extract any PERSONAL FACTS about the user.
        Look for:
        - Names of family, friends, or pets.
        - Physical addresses or locations.
        - Likes/Dislikes (food, movies, travel, hobbies).
        - Important recurring dates or health info.
        
        EMAIL SUBJECT: {subject}
        EMAIL BODY:
        {body[:3000]}
        
        Return ONLY a JSON list of strings (facts). If no facts found, return [].
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        
        facts = json.loads(response.text)
        results = []
        if facts:
            for f in facts:
                results.append({
                    "fact": f,
                    "source_subject": subject,
                    "message_id": msg_id
                })
        return subject, results
    except Exception as e:
        return f"Error ({msg_id})", []

from google.cloud import storage

# ... existing imports ...

def upload_to_gcs(bucket_name, source_file, destination_blob):
    """Uploads a file to the bucket."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob)
        blob.upload_from_filename(source_file)
        print(f"☁️  Synced results to GCS: gs://{bucket_name}/{destination_blob}")
    except Exception as e:
        print(f"⚠️  GCS Upload failed: {e}")

def extract_facts_from_emails_parallel(max_to_process=100, max_workers=10):
    # HIGH-SIGNAL FILTER: Focus on emails likely to have personal info
    # Excludes promotions, social, and generic newsletters
    SEARCH_QUERY = 'category:personal OR label:important OR "order" OR "reservation" OR "confirm" OR "family" -category:promotions -category:social'
    
    print(f"\n🚀 Starting GCP-Ready Fact Extraction")
    print(f"🔍 Filter: {SEARCH_QUERY}")
    print(f"📦 Target: {max_to_process} emails")
    print("-" * 50)
    
    creds = get_google_creds()
    if not creds:
        print("❌ Error: No Google credentials found.")
        return

    gmail_service = build('gmail', 'v1', credentials=creds)
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    # Page through messages with the search filter
    new_messages = []
    page_token = None
    processed_ids_file = "processed_ids.json"
    
    # Load processed IDs
    processed_ids = set()
    if os.path.exists(processed_ids_file):
        with open(processed_ids_file, 'r') as f:
            try: processed_ids = set(json.load(f))
            except: pass

    print(f"🔍 Searching filtered inbox...")
    while len(new_messages) < max_to_process:
        results = gmail_service.users().messages().list(
            userId='me', q=SEARCH_QUERY, maxResults=100, pageToken=page_token
        ).execute()
        
        msgs = results.get('messages', [])
        if not msgs: break
        
        for m in msgs:
            if m['id'] not in processed_ids:
                new_messages.append(m)
                if len(new_messages) >= max_to_process: break
        
        page_token = results.get('nextPageToken')
        if not page_token: break

    total = len(new_messages)
    if total == 0:
        print("📭 No new high-signal emails found.")
        return

    print(f"🆕 Found {total} high-signal emails to process.")

    extracted_data = []
    newly_processed = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_msg = {executor.submit(process_single_email, msg['id'], creds): msg['id'] for msg in new_messages}
        
        processed_count = 0
        for future in as_completed(future_to_msg):
            processed_count += 1
            msg_id = future_to_msg[future]
            subject, facts = future.result()
            newly_processed.append(msg_id)
            
            if facts:
                print(f"✅ [{processed_count}/{total}] Found {len(facts)} facts in: {subject[:30]}...")
                extracted_data.extend(facts)

    # 1. Save Local Backup
    output_file = "extracted_personal_facts.json"
    with open(output_file, 'w') as f:
        json.dump(extracted_data, f, indent=2)
    
    # 2. Sync to GCS if configured
    gcs_bucket = os.getenv("GCS_MEMORIES_BUCKET")
    if gcs_bucket:
        email = get_user_email() or "unknown"
        destination = f"raw_facts_{email}.json"
        upload_to_gcs(gcs_bucket, output_file, destination)

    # 3. Update Checkpoint
    with open(processed_ids_file, 'w') as f:
        json.dump(list(processed_ids.union(newly_processed)), f)
    
    print(f"\n🎉 Task Complete! Total Facts: {len(extracted_data)}")

if __name__ == "__main__":
    # Allow specifying number of emails via CLI arg
    limit = 20
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            pass
            
    extract_facts_from_emails_parallel(max_to_process=limit)
