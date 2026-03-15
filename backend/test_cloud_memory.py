import os
import json
from google.cloud import storage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_gcs_sync():
    print("🧪 Testing GCS Memory Sync...")
    
    bucket_name = os.getenv("GCS_MEMORIES_BUCKET")
    project_id = os.getenv("GOOGLE_PROJECT_ID")
    token_path = "tokens.json"

    if not bucket_name:
        print("❌ Error: GCS_MEMORIES_BUCKET not found in .env")
        return

    if not os.path.exists(token_path):
        print(f"❌ Error: {token_path} not found. Please log in to the app first.")
        return

    with open(token_path, 'r') as f:
        email = json.load(f).get('email')
    
    print(f"👤 User: {email}")
    print(f"🪣  Bucket: {bucket_name}")
    print(f"🏗️  Project: {project_id}")

    try:
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.bucket(bucket_name)
        blob_name = f"raw_facts_{email}.json"
        blob = bucket.blob(blob_name)

        print(f"🔍 Checking for blob: {blob_name}...")
        
        if blob.exists():
            print(f"✅ Blob found! Size: {blob.size} bytes")
            local_file = "test_sync_results.json"
            blob.download_to_filename(local_file)
            print(f"💾 Downloaded to: {local_file}")
            
            with open(local_file, 'r') as f:
                data = json.load(f)
                print(f"📋 Found {len(data)} raw facts in cloud storage.")
                if len(data) > 0:
                    print(f"💡 Sample Fact: {data[0]['fact']}")
        else:
            print(f"❓ Blob not found. Have you run the datamining job yet?")
            print("   Listing all blobs in bucket to help debug:")
            blobs = list(bucket.list_blobs(max_results=10))
            for b in blobs:
                print(f"   - {b.name}")

    except Exception as e:
        print(f"💥 GCS Error: {str(e)}")

if __name__ == "__main__":
    test_gcs_sync()
