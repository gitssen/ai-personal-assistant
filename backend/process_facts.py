import json
import os
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def deduplicate_and_clean_facts():
    input_file = "extracted_personal_facts.json"
    if not os.path.exists(input_file):
        print(f"❌ Error: {input_file} not found.")
        return

    with open(input_file, 'r') as f:
        data = json.load(f)

    if not data:
        print("📭 No facts found in the file.")
        return

    raw_facts = [item['fact'] for item in data]
    print(f"📋 Total raw facts collected: {len(raw_facts)}")
    print("🧠 Using AI to deduplicate and categorize...")

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # We use a prompt to deduplicate because many facts are repeats (e.g., "User is Saurav")
    prompt = f"""
    Below is a list of personal facts extracted from a user's emails. 
    1. Remove exact duplicates.
    2. Merge overlapping facts (e.g., "User lives in CA" and "User lives in Belmont, CA" -> "User lives in Belmont, CA").
    3. Categorize them into logical groups (Identity, Family, Preferences, Home, etc.).
    4. Return the result as a clean, human-readable list.

    RAW FACTS:
    {json.dumps(raw_facts, indent=2)}
    
    Return ONLY the categorized list in a clear text format.
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        print("\n" + "="*50)
        print("✨ CLEANED & CATEGORIZED PERSONAL FACTS")
        print("="*50)
        print(response.text)
        print("="*50)
        print("\n✅ Review the list above. If correct, these can be imported into your Cloud Memory.")

    except Exception as e:
        print(f"❌ Error during AI processing: {e}")

if __name__ == "__main__":
    deduplicate_and_clean_facts()
