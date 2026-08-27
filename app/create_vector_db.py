import os
import sys
import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


# --------------------------------
# Configuration
# --------------------------------

# Resolve paths relative to this script location
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOCUMENTS_FOLDER = os.path.join(BASE_DIR, "documents")
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "hr_policy"

CHUNK_SIZE = 600
CHUNK_OVERLAP = 100


# --------------------------------
# Load embedding model
# --------------------------------

print("Loading embedding model (all-MiniLM-L6-v2)...")

embedding_model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

print("Embedding model loaded successfully.")


# --------------------------------
# Connect to HR ChromaDB
# --------------------------------

client = chromadb.PersistentClient(
    path=CHROMA_PATH
)


# --------------------------------
# Create / get HR collection (clear old collection first if exists)
# --------------------------------

try:
    client.delete_collection(COLLECTION_NAME)
except Exception:
    pass

collection = client.get_or_create_collection(
    name=COLLECTION_NAME
)


# --------------------------------
# Read and chunk a single PDF
# --------------------------------

def process_pdf(pdf_path):
    """
    Extracts text from a PDF and splits it into
    overlapping chunks for better semantic coverage.
    """

    reader = PdfReader(pdf_path)

    full_text = ""

    for page in reader.pages:

        text = page.extract_text()

        if text:
            full_text += text + "\n"

    # Sliding-window chunking
    chunks = []
    start = 0

    while start < len(full_text):

        end = start + CHUNK_SIZE
        chunk = full_text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


# --------------------------------
# Process ALL PDFs in documents/
# --------------------------------

print(f"\nScanning documents folder: {DOCUMENTS_FOLDER}")

pdf_files = [
    f for f in os.listdir(DOCUMENTS_FOLDER)
    if f.lower().endswith(".pdf")
]

if not pdf_files:
    print("ERROR: No PDF files found in the documents folder.")
    print("Please add HR policy PDFs to the documents/ folder and re-run.")
    sys.exit(1)

print(f"Found {len(pdf_files)} PDF file(s): {pdf_files}\n")

all_chunks = []

for filename in pdf_files:

    pdf_path = os.path.join(DOCUMENTS_FOLDER, filename)

    print(f"Processing: {filename}")

    chunks = process_pdf(pdf_path)

    print(f"  Chunks created: {len(chunks)}")

    for index, chunk in enumerate(chunks):

        all_chunks.append({
            "text": chunk,
            "source": filename,
            "chunk_index": index
        })


print(f"\nTotal chunks across all documents: {len(all_chunks)}")


# --------------------------------
# Create embeddings and store
# --------------------------------

print("\nGenerating embeddings and storing in ChromaDB...")

documents = []
embeddings = []
metadatas = []
ids = []


for index, item in enumerate(all_chunks):

    embedding = embedding_model.encode(
        item["text"]
    ).tolist()

    documents.append(item["text"])
    embeddings.append(embedding)

    metadatas.append({
        "source": item["source"],
        "chunk_index": item["chunk_index"]
    })

    ids.append(
        f"{item['source']}_{item['chunk_index']}"
    )


# --------------------------------
# Upsert into HR ChromaDB
# --------------------------------

collection.upsert(
    documents=documents,
    embeddings=embeddings,
    metadatas=metadatas,
    ids=ids
)


print("\n==============================")
print("HR Policy documents successfully stored!")
print("==============================")

print(
    f"Collection: '{COLLECTION_NAME}'\n"
    f"Total chunks in HR database: {collection.count()}"
)
