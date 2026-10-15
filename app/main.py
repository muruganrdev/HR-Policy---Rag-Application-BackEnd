from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

@app.exception_handler(ConnectionError)
async def connection_error_handler(request, exc: ConnectionError):
    if "ollama" in str(exc).lower():
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Failed to connect to Ollama. Please ensure Ollama is running (e.g. run 'ollama serve' or open the Ollama app).",
                "error": str(exc),
            },
        )
    return JSONResponse(status_code=500, content={"detail": str(exc)})


app.include_router(hr_router)


@app.get("/")
def root():
    return {
        "message": "HR Policy RAG API is running",
        "docs": "/docs",
        "endpoint": "POST /ask"
    }
