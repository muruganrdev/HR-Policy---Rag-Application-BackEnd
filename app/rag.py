import re
import os
import chromadb
import ollama
from sentence_transformers import SentenceTransformer
from app.reranker import rerank_documents
from app.preprocess import preprocess_question
from app.rewrite import rewrite_question





# --------------------------------
# 1. Configuration & Casual Conversation
# --------------------------------

# Resolve paths relative to this script location
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "hr_policy"

# Configurable distance threshold.
# Adjust this after testing with your actual HR documents.
DISTANCE_THRESHOLD = 1.2

N_RESULTS = 5

OLLAMA_MODEL = "llama3"


CASUAL_PATTERNS = {
    "greetings": {
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening"
    },
    "general": {
        "how are you", "how are you doing", "what's up", "whats up"
    },
    "thanks": {
        "thanks", "thank you", "thanks a lot"
    },
    "farewell": {
        "bye", "goodbye", "see you", "see you later"
    }
}

CASUAL_RESPONSES = {
    "greetings": "Hello! 👋 How can I help you with our HR Policies?",
    "general": "I'm doing well! 😊 How can I help you with our HR Policies?",
    "thanks": "You're welcome! 😊 Feel free to ask any other HR policy questions.",
    "farewell": "Goodbye! 👋 Feel free to ask me anything about our HR Policies."
}


def get_casual_category(question: str) -> str | None:
    cleaned = re.sub(r"[^\w\s']", "", question.strip().lower()).strip()
    for category, patterns in CASUAL_PATTERNS.items():
        if cleaned in patterns:
            return category
    return None


def is_casual_message(question: str) -> bool:
    return get_casual_category(question) is not None


def get_casual_response(question: str) -> str:
    category = get_casual_category(question)
    if category and category in CASUAL_RESPONSES:
        return CASUAL_RESPONSES[category]
    return "Hello! 👋 How can I help you with our HR Policies?"


# --------------------------------
# 2. Load embedding model
# --------------------------------

embedding_model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)


# --------------------------------
# 3. Connect to HR ChromaDB
# --------------------------------

client = chromadb.PersistentClient(
    path=CHROMA_PATH
)

collection = client.get_collection(
    name=COLLECTION_NAME
)


# --------------------------------
# 4. RAG Function
# --------------------------------

def ask_question(question: str):
    """
    Full HR Policy RAG pipeline:
      1. Check for casual conversation
      2. Embed the question
      3. Retrieve relevant HR policy chunks from ChromaDB
      4. Filter by distance threshold
      5. Build grounded context
      6. Send grounded prompt to Llama 3 via Ollama
      7. Return answer + source citations

    Args:
        question: The user's natural language question.

    Returns:
        A dict with keys: question, answer, sources.
    """

    # --------------------------------
    # Casual conversation check
    # --------------------------------

    if is_casual_message(question):
        return {
            "question": question,
            "answer": get_casual_response(question),
            "sources": []
        }


    # --------------------------------
    # Convert question into embedding vector
    # --------------------------------

    processed_question = preprocess_question(question)
    rewritten_question = rewrite_question(processed_question)
    query_embedding = embedding_model.encode(
        rewritten_question
    ).tolist()


    # --------------------------------
    # Retrieve top-N candidate chunks
    # --------------------------------

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=N_RESULTS,
        include=[
            "documents",
            "metadatas",
            "distances"
        ]
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    # Rerank retrieved documents using CrossEncoder
    documents, metadatas, distances = rerank_documents(
        rewritten_question, documents, metadatas, distances
    )


    # --------------------------------
    # Filter chunks by distance threshold
    # --------------------------------

    context_parts = []
    relevant_sources = []

    for document, metadata, distance in zip(
        documents, metadatas, distances
    ):

        # Discard irrelevant chunks beyond threshold
        if distance > DISTANCE_THRESHOLD:
            continue

        source = metadata["source"]
        chunk_index = metadata["chunk_index"]

        # Build context block with citation
        context_parts.append(
            f"""
Source: {source}
Chunk: {chunk_index}

Content:
{document}
"""
        )

        # Store citation for the response
        relevant_sources.append({
            "source": source,
            "chunk": chunk_index
        })


    # --------------------------------
    # Build final context string
    # --------------------------------

    context = "\n\n".join(context_parts)


    # --------------------------------
    # No relevant HR documents found
    # --------------------------------

    if not context:
        return {
            "question": question,
            "answer": "I don't know based on the provided HR policy documents.",
            "sources": []
        }


    # --------------------------------
    # Grounded prompt — HR Policy domain
    # --------------------------------

    prompt = f"""
You are a helpful HR Policy assistant.

Answer the user's question using ONLY the information
provided in the context below.

The context comes exclusively from official HR policy documents.

If the answer cannot be found in the context, say:
"I don't know based on the provided HR policy documents."

Do NOT make up or invent HR policies.
Do NOT use general knowledge to answer — only use what is in the context.

Context:
{context}

User Question:
{question}

Answer:
"""


    # --------------------------------
    # Send grounded prompt to Llama 3
    # --------------------------------

    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )


    # --------------------------------
    # Extract answer text
    # --------------------------------

    answer = response["message"]["content"]


    # --------------------------------
    # Return API-friendly response
    # --------------------------------

    return {
        "question": question,
        "answer": answer,
        "sources": relevant_sources
    }

