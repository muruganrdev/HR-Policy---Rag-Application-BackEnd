from fastapi import APIRouter
from pydantic import BaseModel

from app.rag import ask_question

router = APIRouter()


class QuestionRequest(BaseModel):
    question: str


@router.post("/ask")
def ask(request: QuestionRequest):
    """
    HR Policy RAG endpoint.

    Receives a natural language question about HR policies
    and returns a grounded answer with source citations.

    Request body:
        { "question": "What is the annual leave policy?" }

    Response:
        {
            "question": "...",
            "answer":   "...",
            "sources":  [{ "source": "leave_policy.pdf", "chunk": 0 }]
        }
    """

    result = ask_question(request.question)

    return result
