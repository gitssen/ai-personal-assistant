import os
from dotenv import load_dotenv
load_dotenv()

from app.memory import save_preference, get_relevant_memories

def test_memory():
    print("--- TESTING CLOUD MEMORY ---")
    
    # 1. Save a sample preference
    test_fact = "User is allergic to peanuts and loves spicy Mexican food."
    try:
        save_preference(test_fact)
        print("SUCCESS: Preference saved to Firestore.")
    except Exception as e:
        print(f"FAILED: Could not save preference: {e}")
        return

    # 2. Retrieve the preference
    print("\n--- RETRIEVING MEMORY ---")
    query = "What food does the user like?"
    try:
        results = get_relevant_memories(query)
        if results:
            print(f"SUCCESS: Found relevant memories: {results}")
        else:
            print("WARNING: No relevant memories found. (Did you create the Vector Index?)")
    except Exception as e:
        print(f"FAILED: Could not retrieve memories: {e}")

if __name__ == "__main__":
    test_memory()
