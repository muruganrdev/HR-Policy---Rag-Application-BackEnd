from fastapi import APIRouter
from pydantic import BaseModel

from app.rag import ask_question
from app.router import route_question
from app.agent import run_agent

router = APIRouter()


class QuestionRequest(BaseModel):
	question: str


def _extract_agent_sources(steps: list[dict]) -> list[dict]:
	"""Extract citations from policy search observations in agent steps."""
	sources = []
	seen = set()
	for step in steps:
		if step.get("tool") == "lookup_annual_leave_policy":
			obs = step.get("observation", {})
			res = obs.get("result", {})
			for item in res.get("results", []):
				src = item.get("source")
				chunk = item.get("chunk_index")
				if src and chunk is not None and (src, chunk) not in seen:
					seen.add((src, chunk))
					sources.append({"source": src, "chunk": chunk})
	return sources


@router.post("/ask")
def ask(request: QuestionRequest):
	"""Route HR policy questions to RAG or employee Agent handling."""
	selected_route = route_question(request.question)

	if selected_route == "agent":
		agent_res = run_agent(request.question)
		sources = _extract_agent_sources(agent_res.get("steps", []))
		return {
			"question": agent_res["question"],
			"answer": agent_res["answer"],
			"sources": sources,
			"route": "agent",
		}

	rag_res = ask_question(request.question)
	rag_res["route"] = "rag"
	return rag_res
