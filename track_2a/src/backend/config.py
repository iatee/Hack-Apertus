"""Setup options for the interview (GET /api/v1/config), loaded from the YAML files in data/."""

from functools import lru_cache
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

LANGUAGES = [
    {"code": "de", "label": "Deutsch"},
    {"code": "fr", "label": "Français"},
    {"code": "it", "label": "Italiano"},
    {"code": "gsw", "label": "Schwiizerdütsch (Beta)"},
]

MODES = [
    {"id": "training", "description": "Short feedback after every answer"},
    {"id": "rehearsal", "description": "Realistic, feedback only at the end"},
]


def _load(name: str) -> list[dict]:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def occupations() -> dict[str, dict]:
    return {o["id"]: o for o in _load("occupations.yaml")}


@lru_cache
def interviewer_styles() -> dict[str, dict]:
    return {s["id"]: s for s in _load("interviewer_styles.yaml")}


def public_config() -> dict:
    return {
        "languages": LANGUAGES,
        "occupations": [{"id": o["id"], "label": o["label"]} for o in occupations().values()],
        "interviewer_styles": [{"id": s["id"], "label": s["label"]} for s in interviewer_styles().values()],
        "modes": MODES,
    }
