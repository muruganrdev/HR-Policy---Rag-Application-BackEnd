import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.rag import ask_question
from app.router import route_question
from app.agent import run_agent
from app.short_term_memory import (
	ShortTermConversationMemory,
	resolve_employee_reference,
)

router = APIRouter()
_logger = logging.getLogger(__name__)
_conversation_memory = ShortTermConversationMemory()


class QuestionRequest(BaseModel):
	question: str
	conversation_id: str | None = Field(default=None, min_length=1, max_length=128)


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
	conversation_id = (request.conversation_id or "").strip()
	history = _conversation_memory.get_history(conversation_id) if conversation_id else []
	resolved_question = resolve_employee_reference(request.question, history)
	selected_route = route_question(resolved_question)
	if conversation_id:
		_logger.info(
			"Short-term conversation context: conversation_id=%s history_turns=%d reference_resolved=%s",
			conversation_id,
			len(history) // 2,
			resolved_question != request.question,
		)

	if selected_route == "agent":
		if conversation_id:
			agent_res = run_agent(
				resolved_question,
				original_question=request.question,
				conversation_history=history,
			)
		else:
			agent_res = run_agent(request.question)
		sources = _extract_agent_sources(agent_res.get("steps", []))
		response = {
			"question": request.question,
			"answer": agent_res["answer"],
			"sources": sources,
			"route": "agent",
		}
	else:
		response = ask_question(resolved_question)
		response["route"] = "rag"
		if conversation_id:
			response["question"] = request.question

	if conversation_id:
		_conversation_memory.add_exchange(
			conversation_id, request.question, response["answer"]
		)
	return response
