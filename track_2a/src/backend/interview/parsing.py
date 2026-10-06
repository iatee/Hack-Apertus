"""Robust parsing of the analysis call's JSON output.

Small models often wrap JSON in prose or code fences, emit <think> blocks,
leave trailing commas, use Python literals or return scores as "4/5".
`parse_analysis` handles those locally (no extra LLM call) and raises
`AnalysisParseError` only when the output is really unusable.
"""

import ast
import json
import re

from pydantic import BaseModel, ValidationError, field_validator

from backend.interview.prompts import CRITERIA


class AnalysisParseError(ValueError):
    pass


class Analysis(BaseModel):
    scores: dict[str, int]
    feedback: str = ""
    follow_up: bool = False

    @field_validator("scores", mode="before")
    @classmethod
    def _normalise_scores(cls, raw):
        if not isinstance(raw, dict):
            raise ValueError("scores must be an object")
        scores = {}
        for key, value in raw.items():
            norm = re.sub(r"[\s\-]+", "_", str(key).strip().lower())
            if norm in CRITERIA:
                scores[norm] = _to_score(value)
        missing = [key for key in CRITERIA if key not in scores]
        if missing:
            raise ValueError(f"missing scores: {', '.join(missing)}")
        return scores

    @field_validator("follow_up", mode="before")
    @classmethod
    def _to_bool(cls, value):
        if isinstance(value, str):
            return value.strip().lower() in ("true", "yes", "ja", "oui", "si", "sì", "1")
        return bool(value)


def _to_score(value) -> int:
    if isinstance(value, dict):  # {"score": 4, "reason": "..."}
        value = value.get("score", value.get("value"))
    match = re.search(r"\d+(\.\d+)?", str(value))
    if not match:
        raise ValueError(f"score is not a number: {value!r}")
    return max(1, min(5, round(float(match.group()))))


def _candidates(text: str):
    """Yield substrings that may contain the JSON object, best guesses first."""
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    text = text.replace("“", '"').replace("”", '"')
    for fenced in re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL):
        yield fenced.strip()
    # Balanced {...} spans, scanning while respecting string literals.
    depth, start, in_str, escape = 0, None, False, False
    for i, ch in enumerate(text):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                yield text[start : i + 1]
    if start is not None and depth:  # truncated output: try closing the braces
        yield text[start:] + "}" * depth


def _loads(candidate: str):
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    fixed = re.sub(r",\s*([}\]])", r"\1", candidate)  # trailing commas
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    try:  # Python-style dict: single quotes, True/False/None
        pythonic = re.sub(r"\btrue\b", "True", re.sub(r"\bfalse\b", "False", re.sub(r"\bnull\b", "None", fixed)))
        return ast.literal_eval(pythonic)
    except (ValueError, SyntaxError):
        return None


def parse_analysis(text: str) -> Analysis:
    last_error = "no JSON object found"
    for candidate in _candidates(text or ""):
        data = _loads(candidate)
        if not isinstance(data, dict):
            last_error = "invalid JSON syntax"
            continue
        try:
            return Analysis.model_validate(data)
        except ValidationError as exc:
            last_error = "; ".join(err["msg"] for err in exc.errors())
    raise AnalysisParseError(last_error)
