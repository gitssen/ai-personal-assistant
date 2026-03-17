import os
from google import genai

api_key = "AIzaSyArqGgQpC-RIzit-ATWX9JXs_c-zB0CYjQ"
print(f"Testing key: {api_key[:10]}...")

try:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Hello"
    )
    print("✅ Key is WORKING!")
except Exception as e:
    print(f"❌ Key FAILED: {e}")
