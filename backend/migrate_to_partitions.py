import os
import json
from google.cloud import firestore
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
TOKEN_PATH = "tokens.json"

if not PROJECT_ID:
    print("[!] Error: GOOGLE_PROJECT_ID not set in .env")
    exit(1)

# Initialize Firestore
db = firestore.Client(project=PROJECT_ID, database="my-assistant-db")

def get_current_user_email():
    if not os.path.exists(TOKEN_PATH):
        print("[!] Error: tokens.json not found. Please log in to the app first.")
        return None
    with open(TOKEN_PATH, 'r') as f:
        data = json.load(f)
        # We'll extract email from scopes or assume it's the primary user
        # For this migration, we'll try to find it in the tokens.json if available
        # Otherwise, we'll ask the user to provide it.
        return data.get('email') # We'll need to make sure auth saves email

def migrate():
    print("--- STARTING DATA MIGRATION ---")
    
    # 1. Get Email
    email = get_current_user_email()
    if not email:
        email = input("[?] Email not found in tokens. Enter your Google Email to migrate data to: ").strip()
    
    print(f"[*] Migrating data for user: {email}")

    # 2. Get all old memories
    old_memories_ref = db.collection("memories")
    old_docs = old_memories_ref.get()
    
    if len(old_docs) == 0:
        print("[i] No legacy memories found to migrate.")
    else:
        print(f"[*] Found {len(old_docs)} memories. Moving them...")
        
        # 3. Batch move to new location: users/{email}/memories
        new_memories_ref = db.collection("users").document(email).collection("memories")
        
        count = 0
        for doc in old_docs:
            data = doc.to_dict()
            # Save to new location
            new_memories_ref.document(doc.id).set(data)
            # Delete from old location
            doc.reference.delete()
            count += 1
            print(f"    [+] Moved: {data.get('content', 'Untitled')[:30]}...")

        print(f"[!] Migration complete. Moved {count} documents.")

    # 4. Set Onboarding Status
    print(f"[*] Marking user {email} as onboarded...")
    db.collection("users").document(email).set({
        "email": email,
        "has_onboarded": True,
        "migration_date": firestore.SERVER_TIMESTAMP
    }, merge=True)

    print("\n\033[92mSUCCESS: Database partitioned and user profile updated.\033[0m")

if __name__ == "__main__":
    migrate()
