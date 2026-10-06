"""LangGraph core loop: one turn = analysis call (+ retries) -> interviewer call.

    START ──(answer?)──> analyze ──(parsed or out of attempts)──> interviewer ──> END
       └───(no answer: opening question)──────────────────────────────┘
                          ^    │
                          └────┘ retry on unusable JSON

Call budget per answer: MAX_ANALYSIS_ATTEMPTS analysis calls + 1 interviewer
call. Retries count as calls, so the worst case is 4 (< 5) and the normal
case is 2. If all attempts fail, the turn continues without an analysis
instead of erroring.
"""

import json
import logging
import operator
from typing import Annotated, Optional, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from backend import llm
from backend.interview.parsing import AnalysisParseError, parse_analysis
from backend.interview.prompts import PHASES, analysis_messages, interviewer_messages, repair_message

logger = logging.getLogger("interview")

MAX_ANALYSIS_ATTEMPTS = 3
MAX_FOLLOW_UPS_PER_PHASE = 1


class InterviewState(TypedDict, total=False):
    # Session-wide (kept by the checkpointer across turns)
    role: str
    language: str
    phase_index: int
    follow_ups_in_phase: int
    transcript: Annotated[list[dict], operator.add]  # {"speaker": "interviewer"|"candidate", "text": str}
    analyses: Annotated[list[dict], operator.add]
    question: Optional[str]
    done: bool
    # Per turn (reset by each invoke)
    answer: Optional[str]
    attempts: int
    analysis: Optional[dict]
    analysis_error: Optional[str]
    last_raw: Optional[str]


def _last_question(state: InterviewState) -> str:
    return next((t["text"] for t in reversed(state["transcript"]) if t["speaker"] == "interviewer"), "")


async def analyze(state: InterviewState) -> dict:
    attempt = state.get("attempts", 0) + 1
    messages = analysis_messages(state["role"], state["language"], _last_question(state), state["answer"])
    if state.get("analysis_error"):
        messages += [{"role": "assistant", "content": state.get("last_raw") or ""}, repair_message(state["analysis_error"])]

    raw = await llm.chat_completion(
        messages,
        purpose="analysis" if attempt == 1 else "analysis_retry",
        temperature=0.2 if attempt == 1 else 0.0,
    )
    try:
        analysis = parse_analysis(raw).model_dump()
    except AnalysisParseError as exc:
        logger.warning(json.dumps({"event": "analysis_parse_failed", "attempt": attempt, "error": str(exc)}))
        update = {"attempts": attempt, "analysis_error": str(exc), "last_raw": raw}
        if attempt >= MAX_ANALYSIS_ATTEMPTS:
            update["analyses"] = [{"phase": PHASES[state["phase_index"]][0], "parse_failed": True, "error": str(exc)}]
        return update
    analysis["phase"] = PHASES[state["phase_index"]][0]
    return {"attempts": attempt, "analysis": analysis, "analysis_error": None, "analyses": [analysis]}


def route_after_analyze(state: InterviewState) -> str:
    if state.get("analysis") is None and state["attempts"] < MAX_ANALYSIS_ATTEMPTS:
        return "analyze"
    return "interviewer"


async def interviewer(state: InterviewState) -> dict:
    phase_index = state["phase_index"]
    follow_ups = state["follow_ups_in_phase"]
    new_turns = []
    follow_up = False

    if state.get("answer"):
        new_turns.append({"speaker": "candidate", "text": state["answer"]})
        wants_follow_up = bool((state.get("analysis") or {}).get("follow_up"))
        if wants_follow_up and follow_ups < MAX_FOLLOW_UPS_PER_PHASE:
            follow_up, follow_ups = True, follow_ups + 1
        else:
            phase_index, follow_ups = phase_index + 1, 0

    phase = PHASES[phase_index][0]
    update = {"phase_index": phase_index, "follow_ups_in_phase": follow_ups}
    if phase == "feedback":
        return {**update, "transcript": new_turns, "question": None, "done": True}

    transcript = state.get("transcript", []) + new_turns
    question = (await llm.chat_completion(
        interviewer_messages(state["role"], state["language"], phase, follow_up, transcript),
        purpose="interviewer",
        temperature=0.7,
    )).strip()
    new_turns.append({"speaker": "interviewer", "text": question})
    return {**update, "transcript": new_turns, "question": question, "done": False}


def build_graph(checkpointer=None):
    builder = StateGraph(InterviewState)
    builder.add_node("analyze", analyze)
    builder.add_node("interviewer", interviewer)
    builder.add_conditional_edges(START, lambda s: "analyze" if s.get("answer") else "interviewer", ["analyze", "interviewer"])
    builder.add_conditional_edges("analyze", route_after_analyze, ["analyze", "interviewer"])
    builder.add_edge("interviewer", END)
    return builder.compile(checkpointer=checkpointer or InMemorySaver())


_TURN_RESET = {"attempts": 0, "analysis": None, "analysis_error": None, "last_raw": None}


class InterviewEngine:
    """Session-level API over the graph; session id = LangGraph thread id."""

    def __init__(self, checkpointer=None):
        self.graph = build_graph(checkpointer)

    def _config(self, session_id: str) -> dict:
        return {"configurable": {"thread_id": session_id}}

    async def get_state(self, session_id: str) -> Optional[dict]:
        snapshot = await self.graph.aget_state(self._config(session_id))
        return snapshot.values or None

    async def start(self, session_id: str, role: str, language: str) -> dict:
        initial = {"role": role, "language": language, "phase_index": 0, "follow_ups_in_phase": 0,
                   "done": False, "answer": None, **_TURN_RESET}
        return await self.graph.ainvoke(initial, self._config(session_id))

    async def answer(self, session_id: str, answer: str) -> dict:
        return await self.graph.ainvoke({"answer": answer, **_TURN_RESET}, self._config(session_id))
