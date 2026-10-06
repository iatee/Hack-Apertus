import json

import pytest

from backend.interview.parsing import AnalysisParseError, parse_analysis
from backend.interview.prompts import CRITERIA

SCORES = {key: 4 for key in CRITERIA}
VALID = json.dumps({"scores": SCORES, "feedback": "Gut.", "follow_up": False})


@pytest.mark.parametrize("text", [
    VALID,
    f"Hier ist meine Bewertung:\n```json\n{VALID}\n```\nViel Erfolg!",
    f"<think>Let me consider {{the answer}}...</think>{VALID}",
    VALID[:-1] + ",}",                                   # trailing comma
    VALID.replace('"', "'").replace("false", "False"),  # Python-style dict
    VALID[:-1],                                          # truncated closing brace
])
def test_parses_messy_but_recoverable_output(text):
    result = parse_analysis(text)
    assert result.scores == SCORES
    assert result.follow_up is False


def test_normalises_keys_and_score_formats():
    raw = {
        "scores": {"Relevance": "4/5", "structure": 5.4, "Concreteness": {"score": 2},
                   "self-reflection": "3", "motivation fit": 9, "communication": 0},
        "follow_up": "ja",
    }
    result = parse_analysis(json.dumps(raw))
    assert result.scores == {"relevance": 4, "structure": 5, "concreteness": 2,
                             "self_reflection": 3, "motivation_fit": 5, "communication": 1}
    assert result.follow_up is True


@pytest.mark.parametrize("text, error", [
    ("Die Antwort war gut.", "no JSON"),
    (json.dumps({"scores": {"relevance": 4}}), "missing scores"),
    (json.dumps({"scores": {**SCORES, "structure": "n/a"}}), "not a number"),
])
def test_rejects_unusable_output(text, error):
    with pytest.raises(AnalysisParseError, match=error):
        parse_analysis(text)
