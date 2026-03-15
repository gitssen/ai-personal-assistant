from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
import vertexai
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
from app.logger import logger

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["GOOGLE_CLOUD_QUOTA_PROJECT"] = PROJECT_ID

db = firestore.Client(project=PROJECT_ID, database="my-assistant-db")
vertexai.init(project=PROJECT_ID, location="us-central1")

def get_embedding(text: str):
    model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    inputs = [TextEmbeddingInput(text, "RETRIEVAL_DOCUMENT")]
    embeddings = model.get_embeddings(inputs)
    return embeddings[0].values

def get_user_memories_ref(email: str):
    """Get the reference to a user's specific memories collection."""
    return db.collection("users").document(email).collection("memories")

def save_preference(email: str, text: str):
    """Save a preference to a user's partitioned memory."""
    logger.info(f"Saving preference for {email}: {text}")
    try:
        vector_values = get_embedding(text)
        doc_id = str(uuid.uuid4())
        get_user_memories_ref(email).document(doc_id).set({
            "content": text,
            "embedding": Vector(vector_values),
            "timestamp": datetime.now()
        })
    except Exception as e:
        logger.error(f"Failed to save preference: {e}")

def get_relevant_memories(email: str, query: str, n_results: int = 5):
    """Search a user's partitioned memories."""
    try:
        query_vector = get_embedding(query)
        collection = get_user_memories_ref(email)
        results = collection.find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.COSINE,
            limit=n_results
        ).get()
        return [doc.to_dict().get("content") for doc in results]
    except Exception as e:
        logger.error(f"Cloud Memory search failed for {email}: {e}")
        return []

def delete_memory(email: str, text: str):
    """Delete a specific memory from a user's partition."""
    try:
        collection = get_user_memories_ref(email)
        # 1. Try exact match
        results = collection.where("content", "==", text).get()
        if len(results) > 0:
            for doc in results: doc.reference.delete()
            return True
        # 2. Try semantic match
        query_vector = get_embedding(text)
        results = collection.find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.COSINE,
            limit=1
        ).get()
        for doc in results: doc.reference.delete()
        return True
    except Exception as e:
        logger.error(f"Deletion failed for {email}: {e}")
        return False

def check_onboarding_status(email: str):
    """Check if a user has completed the wizard or has existing data."""
    # 1. Check explicit onboarding flag
    user_doc = db.collection("users").document(email).get()
    if user_doc.exists and user_doc.to_dict().get("has_onboarded", False):
        return True
        
    # 2. Check if they have ANY documents in their memory partition (Migration fallback)
    memories = get_user_memories_ref(email).limit(1).get()
    if len(memories) > 0:
        # If they have data, mark them as onboarded automatically
        db.collection("users").document(email).set({"has_onboarded": True}, merge=True)
        return True
        
    return False

def complete_onboarding(email: str, wizard_data: dict):
    """Save wizard data as initial memories and mark as onboarded."""
    # Mark as onboarded
    db.collection("users").document(email).set({
        "email": email,
        "has_onboarded": True,
        "onboarded_at": datetime.now()
    }, merge=True)
    
    # Save facts
    for key, value in wizard_data.items():
        if value and value.strip():
            save_preference(email, f"{key.capitalize()}: {value}")
