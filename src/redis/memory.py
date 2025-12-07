import os
import numpy as np
from redisvl.index import SearchIndex
from redisvl.query import VectorQuery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Define schema for task memory
schema = {
    "index": {
        "name": "task_memory",
        "prefix": "task",
    },
    "fields": [
        {"name": "text", "type": "text"},
        {"name": "user", "type": "tag"},
        {"name": "task_type", "type": "tag"},
        {"name": "status", "type": "tag"},
        {
            "name": "embedding",
            "type": "vector",
            "attrs": {
                "dims": 3,  # Simple 3D vectors for testing
                "distance_metric": "cosine",
                "algorithm": "flat",
                "datatype": "float32"
            }
        }
    ]
}

# Create index
index = SearchIndex.from_dict(schema, redis_url=REDIS_URL, validate_on_load=True)


def simple_embed(text: str) -> bytes:
    """Simple mock embedding - in production, use a real embedding model."""
    # Create a deterministic vector based on text hash
    np.random.seed(hash(text) % 2**32)
    vec = np.random.rand(3).astype(np.float32)
    vec = vec / np.linalg.norm(vec)  # Normalize
    return vec.tobytes()


def store_task(text: str, user: str = "default", task_type: str = "general", status: str = "pending"):
    """Store a task with its embedding."""
    data = [{
        "text": text,
        "user": user,
        "task_type": task_type,
        "status": status,
        "embedding": simple_embed(text)
    }]
    keys = index.load(data)
    return keys[0]


def search_similar(query_text: str, top_k: int = 3):
    """Search for similar tasks."""
    # Get embedding for query
    np.random.seed(hash(query_text) % 2**32)
    query_vec = np.random.rand(3).astype(np.float32)
    query_vec = query_vec / np.linalg.norm(query_vec)

    query = VectorQuery(
        vector=query_vec.tolist(),
        vector_field_name="embedding",
        return_fields=["text", "user", "task_type", "status", "vector_distance"],
        num_results=top_k
    )
    return index.query(query)


def test_memory():
    """Test vector storage and search."""
    print("Creating index...")
    index.create(overwrite=True)

    print("\nStoring example tasks...")
    tasks = [
        ("Deploy the app to production", "azmat", "deployment", "completed"),
        ("Fix the login bug on mobile", "azmat", "bugfix", "pending"),
        ("Add dark mode to settings", "azmat", "feature", "pending"),
        ("Update dependencies", "azmat", "maintenance", "completed"),
        ("Write unit tests for auth", "azmat", "testing", "pending"),
    ]

    for text, user, task_type, status in tasks:
        key = store_task(text, user, task_type, status)
        print(f"  Stored: {text[:30]}... -> {key}")

    print("\nSearching for similar tasks...")

    # Search for a task
    results = search_similar("Deploy the app to production")
    print(f"\nQuery: 'Deploy the app to production'")
    for r in results:
        print(f"  -> {r.get('text', 'N/A')[:40]} (distance: {r.get('vector_distance', 'N/A')})")

    print("\n✓ Vector search test complete!")


if __name__ == "__main__":
    test_memory()
