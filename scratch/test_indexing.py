import os
import sys
import re
import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.abspath(".")
DOCUMENTS_FOLDER = os.path.join(BASE_DIR, "documents")
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "hr_policy"

def process_pdf(pdf_path, max_chunk_size=800, chunk_overlap=100):
    reader = PdfReader(pdf_path)
    full_text = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"

    # Split by numbered section headings (e.g. 1. Purpose, 2. Standard Working Hours, etc.)
    raw_sections = re.split(r'\n(?=[0-9]+\.\s+[A-Z])', full_text)
    chunks = []
    for sec in raw_sections:
        sec_clean = sec.strip()
        if not sec_clean:
            continue
        if len(sec_clean) <= max_chunk_size:
            chunks.append(sec_clean)
        else:
            start = 0
            while start < len(sec_clean):
                end = start + max_chunk_size
                c = sec_clean[start:end].strip()
                if c:
                    chunks.append(c)
                start += max_chunk_size - chunk_overlap
    return chunks

if __name__ == "__main__":
    print("Loading embedding model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    pdf_files = [f for f in os.listdir(DOCUMENTS_FOLDER) if f.lower().endswith(".pdf")]
    all_chunks = []

    for filename in pdf_files:
        pdf_path = os.path.join(DOCUMENTS_FOLDER, filename)
        chunks = process_pdf(pdf_path)
        print(f"  {filename}: {len(chunks)} chunks created")
        for index, chunk in enumerate(chunks):
            all_chunks.append({
                "text": chunk,
                "source": filename,
                "chunk_index": index
            })

    documents = []
    embeddings = []
    metadatas = []
    ids = []

    for item in all_chunks:
        embedding = model.encode(item["text"]).tolist()
        documents.append(item["text"])
        embeddings.append(embedding)
        metadatas.append({
            "source": item["source"],
            "chunk_index": item["chunk_index"]
        })
        ids.append(f"{item['source']}_{item['chunk_index']}")

    collection.upsert(
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )

    print(f"Collection: '{COLLECTION_NAME}'")
    print(f"Total chunks stored: {collection.count()}")
