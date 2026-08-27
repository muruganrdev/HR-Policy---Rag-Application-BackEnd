from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as hr_router

app = FastAPI(
    title="HR Policy RAG API",
    description="RAG-based HR Policy Document Assistant powered by Llama 3 + ChromaDB",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hr_router)


@app.get("/")
def root():
    return {
        "message": "HR Policy RAG API is running",
        "docs": "/docs",
        "endpoint": "POST /ask"
    }
