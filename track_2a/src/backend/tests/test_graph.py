import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import llm, main
from backend.interview.graph import MAX_ANALYSIS_ATTEMPTS, InterviewEngine
from backend.interview.prompts import CRITERIA


def analysis_json(follow_up=False):
    return json.dumps({"scores": {key: 3 for key in CRITERIA}, "feedback": "Ok.", "follow_up": follow_up})


class FakeLLM:
    """Stands in for the OpenAI client; answers by call purpose from scripted queues."""

    def __init__(self, analysis_outputs=()):
        self.analysis_outputs = list(analysis_outputs)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, model, messages, **kwargs):
        is_analysis = "evaluate a candidate" in messages[0]["content"]
        self.calls.append("analysis" if is_analysis else "interviewer")
        content = (self.analysis_outputs.pop(0) if self.analysis_outputs else analysis_json()) if is_analysis \
            else f"Question {len(self.calls)}?"
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=None)


@pytest.fixture
def fake(monkeypatch):
    def install(**kwargs):
        client = FakeLLM(**kwargs)
        monkeypatch.setattr(llm, "_get_client", lambda: (client, "fake-model"))
        return client
    return install


async def run_turn(engine, session_id, answer):
    llm.start_request()
    state = await engine.answer(session_id, answer)
    return state, llm.calls_in_request()


async def test_normal_turn_uses_two_calls(fake):
    client = fake()
    engine = InterviewEngine()
    start = await engine.start("s1", "Data Analyst", "de")
    assert start["question"] and start["phase_index"] == 0

    state, calls = await run_turn(engine, "s1", "Ich habe Wirtschaftsinformatik studiert.")
    assert calls == 2
    assert client.calls[-2:] == ["analysis", "interviewer"]
    assert state["analysis"]["scores"] == {key: 3 for key in CRITERIA}
    assert state["phase_index"] == 1


async def test_broken_json_is_retried_and_counted(fake):
    client = fake(analysis_outputs=["Das war gut.", analysis_json()])
    engine = InterviewEngine()
    await engine.start("s2", "Data Analyst", "de")

    state, calls = await run_turn(engine, "s2", "Antwort")
    assert calls == 3
    assert client.calls[-3:] == ["analysis", "analysis", "interviewer"]
    assert state["analysis"] is not None


async def test_gives_up_after_max_attempts_and_stays_under_budget(fake):
    fake(analysis_outputs=["kaputt"] * MAX_ANALYSIS_ATTEMPTS)
    engine = InterviewEngine()
    await engine.start("s3", "Data Analyst", "de")

    state, calls = await run_turn(engine, "s3", "Antwort")
    assert calls == MAX_ANALYSIS_ATTEMPTS + 1 < 5
    assert state["analysis"] is None
    assert state["analyses"][-1]["parse_failed"] is True
    assert state["question"]  # interview continues


async def test_follow_up_stays_in_phase_once(fake):
    fake(analysis_outputs=[analysis_json(follow_up=True), analysis_json(follow_up=True)])
    engine = InterviewEngine()
    await engine.start("s4", "Data Analyst", "de")

    state, _ = await run_turn(engine, "s4", "Hmm.")
    assert (state["phase_index"], state["follow_ups_in_phase"]) == (0, 1)
    state, _ = await run_turn(engine, "s4", "Immer noch vage.")
    assert (state["phase_index"], state["follow_ups_in_phase"]) == (1, 0)


async def test_full_interview_via_api(fake, monkeypatch):
    fake()
    monkeypatch.setattr(main, "engine", InterviewEngine())
    client = TestClient(main.app)

    turn = client.post("/session", json={"role": "Pflegefachperson", "language": "fr"}).json()
    session_id, answers = turn["session_id"], 0
    while not turn["done"]:
        turn = client.post(f"/session/{session_id}/answer", json={"answer": "Réponse"}).json()
        answers += 1
        assert turn["llm_calls"] <= 4
    assert turn["phase"] == "feedback" and answers == 5
    assert client.post(f"/session/{session_id}/answer", json={"answer": "x"}).status_code == 409
    assert client.post("/session/unknown/answer", json={"answer": "x"}).status_code == 404
