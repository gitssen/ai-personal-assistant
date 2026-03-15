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

# Force Project and Quota
PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
if not PROJECT_ID:
    raise ValueError("GOOGLE_PROJECT_ID not set in .env file")

os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["GOOGLE_CLOUD_QUOTA_PROJECT"] = PROJECT_ID

logger.info(f"Forcing Project & Quota to: {PROJECT_ID}")

# Initialize Firestore
db = firestore.Client(project=PROJECT_ID, database="my-assistant-db")

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location="us-central1")

def get_embedding(text: str):
    """Generate a vector embedding using Vertex AI (Native SDK)."""
    model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    inputs = [TextEmbeddingInput(text, "RETRIEVAL_DOCUMENT")]
    embeddings = model.get_embeddings(inputs)
    return embeddings[0].values

def save_preference(text: str):
    """Save a preference to Google Cloud Firestore."""
    logger.info(f"Saving preference to Cloud Firestore: {text}")
    try:
        vector_values = get_embedding(text)
        doc_id = str(uuid.uuid4())
        db.collection("memories").document(doc_id).set({
            "content": text,
            "embedding": Vector(vector_values),
            "timestamp": datetime.now()
        })
    except Exception as e:
        logger.error(f"Failed to save preference: {e}")

def get_relevant_memories(query: str, n_results: int = 5):
    """Search Cloud Firestore using Vector Search (KNN)."""
    try:
        query_vector = get_embedding(query)
        collection = db.collection("memories")
        results = collection.find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.COSINE,
            limit=n_results
        ).get()
        
        return [doc.to_dict().get("content") for doc in results]
    except Exception as e:
        logger.error(f"Cloud Memory search failed: {e}")
        return []

def delete_memory(text: str):
    """Find and delete a specific memory by its exact content match."""
    logger.info(f"Attempting to delete memory: {text}")
    try:
        collection = db.collection("memories")
        # Exact match delete
        results = collection.where("content", "==", text).get()
        deleted_count = 0
        for doc in results:
            doc.reference.delete()
            deleted_count += 1
            
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} memories.")
            return True
            
        # If exact match fails, we try a semantic search to find the closest thing
        logger.info("No exact match found. Searching semantically to find item to delete...")
        query_vector = get_embedding(text)
        results = collection.find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.COSINE,
            limit=1
        ).get()
        
        for doc in results:
            doc.reference.delete()
            logger.info(f"Deleted semantically similar memory: {doc.to_dict().get('content')}")
            return True
            
        return False
    except Exception as e:
        logger.error(f"Deletion failed: {e}")
        return False
