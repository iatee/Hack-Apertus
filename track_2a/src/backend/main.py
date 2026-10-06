import json
import logging
import uuid
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend import llm
from backend.interview.graph import InterviewEngine
from backend.interview.prompts import PHASES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("api")

app = FastAPI(title="FHGR Interview Coach")
engine = InterviewEngine()


class ChatRequest(BaseModel):
    message: str = "Hallo! Stell dich bitte kurz vor."


class ChatResponse(BaseModel):
    answer: str
    request_id: str
    llm_calls: int


class SessionRequest(BaseModel):
    role: str = Field(min_length=1, examples=["Junior Data Analyst"])
    language: Literal["de", "fr", "it"] = "de"


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1)


class TurnResponse(BaseModel):
    session_id: str
    question: Optional[str]
    phase: str
    done: bool
    analysis: Optional[dict] = None
    llm_calls: int


async def _run_llm(coro):
    try:
        return await coro
    except llm.LLMConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {type(exc).__name__}: {exc}")


def _turn_response(session_id: str, state: dict, analysis: Optional[dict]) -> TurnResponse:
    return TurnResponse(
        session_id=session_id,
        question=state.get("question"),
        phase=PHASES[state["phase_index"]][0],
        done=state.get("done", False),
        analysis=analysis,
        llm_calls=llm.calls_in_request(),
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "llm_calls_total": llm.total_calls()}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    request_id = llm.start_request()
    answer = await _run_llm(llm.chat_completion([{"role": "user", "content": req.message}], purpose="chat_test"))
    calls = llm.calls_in_request()
    logger.info(json.dumps({"event": "answer", "request_id": request_id, "calls_per_answer": calls}))
    return ChatResponse(answer=answer, request_id=request_id, llm_calls=calls)


@app.post("/session", response_model=TurnResponse)
async def start_session(req: SessionRequest) -> TurnResponse:
    llm.start_request()
    session_id = uuid.uuid4().hex
    state = await _run_llm(engine.start(session_id, req.role, req.language))
    return _turn_response(session_id, state, None)


@app.post("/session/{session_id}/answer", response_model=TurnResponse)
async def answer(session_id: str, req: AnswerRequest) -> TurnResponse:
    current = await engine.get_state(session_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    if current.get("done"):
        raise HTTPException(status_code=409, detail="Interview already finished")

    request_id = llm.start_request()
    state = await _run_llm(engine.answer(session_id, req.answer))
    calls = llm.calls_in_request()
    logger.info(json.dumps({
        "event": "answer", "request_id": request_id, "session_id": session_id,
        "calls_per_answer": calls, "analysis_attempts": state.get("attempts"),
        "analysis_ok": state.get("analysis") is not None,
    }))
    return _turn_response(session_id, state, state.get("analysis"))
