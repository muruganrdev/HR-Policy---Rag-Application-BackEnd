import os
import chromadb
from sentence_transformers import SentenceTransformer


# --------------------------------
# Configuration
# --------------------------------

# Resolve paths relative to this script location
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "hr_policy"

# Configurable distance threshold.
# Lower = stricter (only very close matches).
# Higher = more permissive (more results but possibly less relevant).
# Adjust this value after testing with your actual documents.
DISTANCE_THRESHOLD = 1.2

N_RESULTS = 5


# --------------------------------
# Load embedding model
# --------------------------------

embedding_model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)


# --------------------------------
# Connect to HR ChromaDB
# --------------------------------

client = chromadb.PersistentClient(
    path=CHROMA_PATH
)

collection = client.get_collection(
    name=COLLECTION_NAME
)


# --------------------------------
# Search function
# --------------------------------

def search(question: str, n_results: int = N_RESULTS, threshold: float = DISTANCE_THRESHOLD):
    """
    Embeds the user question and retrieves the most
    semantically relevant HR policy chunks from ChromaDB.

    Args:
        question:  The user's natural language question.
        n_results: Maximum number of candidates to retrieve.
        threshold: Maximum allowed cosine distance (lower = stricter).

    Returns:
        A list of dicts with keys: source, chunk_index, distance, content.
    """

    # Convert question to embedding vector
    query_embedding = embedding_model.encode(
        question
    ).tolist()

    # Query ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    # Apply distance filtering
    relevant = []

    for document, metadata, distance in zip(
        documents, metadatas, distances
    ):
        if distance > threshold:
            continue

        relevant.append({
            "source": metadata["source"],
            "chunk_index": metadata["chunk_index"],
            "distance": round(distance, 4),
            "content": document
        })

    return relevant


# --------------------------------
# CLI test when run directly
# --------------------------------

if __name__ == "__main__":

    test_questions = [
        "What is the annual leave policy?",
        "How many vacation days can an employee take?",
        "What is the work from home policy?",
        "What happens if an employee is late?",
        "What is the employee notice period?",
        "What is the company policy on cryptocurrency investments?",
    ]

    for question in test_questions:

        print(f"\n{'='*60}")
        print(f"Question: {question}")
        print(f"{'='*60}")

        results = search(question)

        if not results:
            print("No relevant HR policy documents found within threshold.")
        else:
            for index, result in enumerate(results, start=1):
                print(f"\n--- Result {index} ---")
                print(f"Source:   {result['source']}")
                print(f"Chunk:    {result['chunk_index']}")
                print(f"Distance: {result['distance']}")
                print(f"\nContent:\n{result['content']}")

