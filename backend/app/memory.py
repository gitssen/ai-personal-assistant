from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
import vertexai
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Force the project and quota project
PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
if not PROJECT_ID:
    raise ValueError("GOOGLE_PROJECT_ID not set in .env file")

os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["GOOGLE_CLOUD_QUOTA_PROJECT"] = PROJECT_ID

print(f"DEBUG: Forcing Project & Quota to: {PROJECT_ID}")

# Initialize GCP Project
vertexai.init(project=PROJECT_ID, location="us-central1")

# POINT TO THE CORRECT DATABASE: 'my-assistant-db'
db = firestore.Client(project=PROJECT_ID, database="my-assistant-db")

# Load the embedding model
embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")

def get_embedding(text: str):
    """Generate a vector embedding using Vertex AI."""
    inputs = [TextEmbeddingInput(text, "RETRIEVAL_DOCUMENT")]
    embeddings = embedding_model.get_embeddings(inputs)
    return embeddings[0].values

def save_preference(text: str):
    """Save a preference to Google Cloud Firestore with a vector embedding."""
    print(f"DEBUG: Saving preference to Cloud Firestore: {text}")
    vector_values = get_embedding(text)
    
    doc_id = str(uuid.uuid4())
    db.collection("memories").document(doc_id).set({
        "content": text,
        "embedding": Vector(vector_values),
        "timestamp": datetime.now()
    })

def get_relevant_memories(query: str, n_results: int = 5):
    """Search Cloud Firestore using Vector Search (KNN)."""
    try:
        query_vector = get_embedding(query)
        
        # Perform Vector Search on 'my-assistant-db'
        collection = db.collection("memories")
        results = collection.find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.COSINE,
            limit=n_results
        ).get()
        
        return [doc.to_dict().get("content") for doc in results]
    except Exception as e:
        print(f"DEBUG: Cloud Memory search failed: {e}")
        return []
