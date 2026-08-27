# HR Policy RAG — ACME Corporation

A fully self-contained Retrieval-Augmented Generation (RAG) application for answering
questions about HR policies. Powered by **all-MiniLM-L6-v2** embeddings, **ChromaDB**,
**Llama 3 via Ollama**, and **FastAPI**.

> **NOTE**: This application is completely independent of the Student Management RAG.
> It uses its own documents, its own ChromaDB collection (`hr_policy`), and its own FastAPI server.

---

## Project Purpose

This RAG system allows employees and HR teams to ask natural language questions about
company HR policies and receive grounded, cited answers — with zero hallucination.

Supported documents:
- `leave_policy.pdf` — Annual, sick, maternity/paternity, compassionate leave
- `attendance_policy.pdf` — Working hours, punctuality, late arrival rules
- `work_from_home_policy.pdf` — WFH eligibility, entitlements, expectations
- `working_hours_policy.pdf` — Standard hours, overtime, shift work
- `employee_conduct_policy.pdf` — Code of conduct, harassment, disciplinary process
- `notice_period_policy.pdf` — Resignation notice, employer notice, buyout, F&F settlement

---

## Folder Structure

```
hr_policy_rag/
|
+-- app/
|   +-- __init__.py          # Package marker
|   +-- create_vector_db.py  # Step 1: Build ChromaDB from PDFs
|   +-- search.py            # Step 2: Semantic search utility
|   +-- rag.py               # Step 3: Full RAG pipeline
|   +-- api.py               # Step 4: FastAPI router (POST /ask)
|   +-- main.py              # FastAPI application entry point
|
+-- documents/               # HR Policy PDF files
|   +-- leave_policy.pdf
|   +-- attendance_policy.pdf
|   +-- work_from_home_policy.pdf
|   +-- working_hours_policy.pdf
|   +-- employee_conduct_policy.pdf
|   +-- notice_period_policy.pdf
|
+-- chroma_db/               # Persistent ChromaDB vector store
|
+-- README.md                # This file
```

---

## RAG Architecture

```
HR Policy PDFs
      |
      v
PDF Text Extraction (pypdf)
      |
      v
Text Chunking (sliding window, 300 chars, 50 overlap)
      |
      v
all-MiniLM-L6-v2 (SentenceTransformer)
      |
      v
384-dimensional Embeddings
      |
      v
HR ChromaDB (collection: hr_policy)
      |
      v
User Question
      |
      v
Question Embedding (all-MiniLM-L6-v2)
      |
      v
Cosine Similarity Search (n=3 candidates)
      |
      v
Distance Filtering (DISTANCE_THRESHOLD = 1.0)
      |
      v
Relevant Chunks + Metadata (source, chunk_index)
      |
      v
Context Building (source + chunk labels)
      |
      v
Grounded Prompt (answer ONLY from context)
      |
      v
Llama 3 via Ollama
      |
      v
Answer + Source Citations
      |
      v
FastAPI Response (JSON)
```

---

## Key Concepts

### PDF Text Extraction
`pypdf.PdfReader` is used to extract raw text from each page of every HR policy PDF.
All pages are concatenated with newlines to form a single document string.

### Text Chunking
A sliding-window chunking approach is used:
- `CHUNK_SIZE = 600` characters

This ensures that sentence-level information at chunk boundaries is not lost.

### Embeddings
The `all-MiniLM-L6-v2` model from Sentence Transformers converts text into 384-dimensional
dense vectors that capture semantic meaning — not just keywords.

### ChromaDB
ChromaDB is used as the local, persistent vector database.
- Collection name: `hr_policy`
- Location: `hr_policy_rag/chroma_db/`
- This is completely separate from the Student Management RAG ChromaDB.

### Metadata
Every chunk stored in ChromaDB includes:
```python
{
    "source": "leave_policy.pdf",
    "chunk_index": 3
}
```

### Similarity Search
ChromaDB queries are performed with cosine distance. The top `N_RESULTS = 3` nearest
chunks are retrieved for each user question.

### Distance Filtering
Retrieved chunks are filtered by `DISTANCE_THRESHOLD = 1.0`.
- Chunks with distance > threshold are discarded.
- If NO chunks pass the filter, the LLM is NOT called — the system returns:
  `"I don't know based on the provided HR policy documents."`
- This prevents the LLM from hallucinating answers.
- The threshold is configurable in `app/rag.py` and `app/search.py`.

### Context Building
Filtered chunks are assembled into a numbered context block:
```
Source: leave_policy.pdf
Chunk: 3

Content:
Annual leave accrues at a rate of 1.67 days per month...
```

### Grounded Prompt
The prompt explicitly instructs the LLM:
- Answer ONLY from the provided context
- Do NOT use general knowledge
- If the answer is not in the context, say: "I don't know based on the provided HR policy documents."

### Llama 3 via Ollama
The grounded prompt is sent to the `llama3` model running locally through Ollama.
The LLM generates a human-readable answer grounded in the retrieved HR policy context.

### Source Citations
Every answer includes a `sources` list with:
```json
[{ "source": "leave_policy.pdf", "chunk": 3 }]
```

### Hallucination Prevention
Three layers of hallucination prevention:
1. **Distance filtering** — irrelevant chunks are never sent to the LLM
2. **Grounded prompt** — the LLM is explicitly instructed to use only the provided context
3. **Fallback response** — if no relevant chunk is found, a fixed response is returned

---

## Installation

### Prerequisites
- Python 3.10+
- Ollama installed and running (`ollama serve`)
- Llama 3 model pulled (`ollama pull llama3`)

### Install Dependencies
```bash
pip install pypdf sentence-transformers chromadb ollama fastapi uvicorn
```

Or using the existing virtual environment from the Student Management RAG project:
```bash
# From Ask My Documents/ folder
venv\Scripts\activate
pip install pypdf sentence-transformers chromadb ollama fastapi uvicorn
```

---

## How to Run

### Step 1: Generate HR Policy PDF Documents

The sample PDFs are already in the `documents/` folder.

To regenerate them:
```bash
cd "HR Policy - Ask my documents"
python generate_hr_pdfs.py
```

Requires: `pip install reportlab`

---

### Step 2: Build the HR Vector Database

Run this once (or whenever documents change):
```bash
cd hr_policy_rag
python app/create_vector_db.py
```

Expected output:
```
Loading embedding model (all-MiniLM-L6-v2)...
Embedding model loaded successfully.

Scanning documents folder: ...
Found 6 PDF file(s)

Processing: attendance_policy.pdf     Chunks created: 13
Processing: employee_conduct_policy.pdf  Chunks created: 16
...

Total chunks across all documents: 87

HR Policy documents successfully stored!
Collection: 'hr_policy'
Total chunks in HR database: 87
```

---

### Step 3: Test Semantic Search

```bash
cd hr_policy_rag
python app/search.py
```

This runs all 6 test questions directly against ChromaDB and prints results with
source, chunk index, and distance scores.

---

### Step 4: Start the FastAPI Server

```bash
cd hr_policy_rag
uvicorn app.main:app --reload --port 8001
```

The API will be available at:
- http://localhost:8001
- http://localhost:8001/docs  (Swagger UI)
- http://localhost:8001/ask   (POST endpoint)

> Use port 8001 to avoid conflict with the Student Management RAG running on 8000.

---

## API Usage

### POST /ask

**Request:**
```json
{
  "question": "How many annual leave days are employees entitled to?"
}
```

**Response:**
```json
{
  "question": "How many annual leave days are employees entitled to?",
  "answer": "According to the Leave Policy, all full-time employees are entitled to 20 working days of annual leave per calendar year...",
  "sources": [
    { "source": "leave_policy.pdf", "chunk": 3 },
    { "source": "leave_policy.pdf", "chunk": 2 }
  ]
}
```

---

## Example Questions and Expected Responses

| Question | Expected Source | Behaviour |
|---|---|---|
| What is the annual leave policy? | leave_policy.pdf | Returns leave entitlements |
| How many vacation days can an employee take? | leave_policy.pdf | Semantic match to annual leave |
| What is the work from home policy? | work_from_home_policy.pdf | Returns WFH rules |
| What happens if an employee is late? | attendance_policy.pdf | Returns punctuality rules |
| What is the employee notice period? | notice_period_policy.pdf | Returns notice period by grade |
| What is the company policy on cryptocurrency investments? | — | Returns "I don't know..." |

---

## Distance Threshold Tuning

The `DISTANCE_THRESHOLD` controls how strict the semantic matching is:

| Value | Effect |
|---|---|
| 0.5 | Very strict — only exact topic matches |
| 0.75 | Strict — good for tightly scoped questions |
| 1.0 | Balanced — recommended for HR policy queries |
| 1.5+ | Permissive — may include loosely related content |

To change the threshold, edit `DISTANCE_THRESHOLD` in:
- `app/rag.py` — affects the full RAG pipeline
- `app/search.py` — affects standalone search tests

---

## Independence from Student Management RAG

This application is completely independent:

| Component | Student Management RAG | HR Policy RAG |
|---|---|---|
| Documents | `Ask My Documents/documents/` | `hr_policy_rag/documents/` |
| ChromaDB path | `Ask My Documents/chroma_db/` | `hr_policy_rag/chroma_db/` |
| ChromaDB collection | `student_management` | `hr_policy` |
| FastAPI port | 8000 | 8001 |
| Python files | `Ask My Documents/app/` | `hr_policy_rag/app/` |
