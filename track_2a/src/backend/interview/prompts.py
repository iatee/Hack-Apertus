"""Criteria, phase goals and prompt builders for the interview loop.

Setting: a school student (about 14-16) practises the job interview for an
apprenticeship (Lehrstelle / apprentissage / apprendistato) in Switzerland.
"""

import json
from typing import Optional

# The 6 analysis criteria (ids and labels from docs/api.md), each scored 1-5.
CRITERIA = {
    "relevance": "Does the answer address the question that was asked?",
    "structure": "Clear beginning, middle and end (e.g. situation, action, result)?",
    "examples": "Real situations and concrete examples instead of empty claims?",
    "motivation": "Genuine interest in the occupation and the company?",
    "language": "Clear, polite and age-appropriate expression?",
    "self_reflection": "Honest view of own strengths and weaknesses?",
}

CRITERIA_LABELS = {
    "de": {"relevance": "Relevanz", "structure": "Struktur", "examples": "Konkrete Beispiele",
           "motivation": "Motivation", "language": "Sprache & Ausdruck", "self_reflection": "Selbstreflexion"},
    "fr": {"relevance": "Pertinence", "structure": "Structure", "examples": "Exemples concrets",
           "motivation": "Motivation", "language": "Langue et expression", "self_reflection": "Autoréflexion"},
    "it": {"relevance": "Pertinenza", "structure": "Struttura", "examples": "Esempi concreti",
           "motivation": "Motivazione", "language": "Lingua ed espressione", "self_reflection": "Autoriflessione"},
}
CRITERIA_LABELS["gsw"] = CRITERIA_LABELS["de"]

# What each main question in a phase should cover (index = question number - 1).
PHASE_GOALS = {
    "intro": ["Let the candidate introduce themselves: school, hobbies, what they like doing."],
    "motivation": [
        "Why does the candidate want to learn this occupation? How did they find out about it?",
        "Why did they apply at this company, and what do they know about the apprenticeship (e.g. from a Schnupperlehre)?",
    ],
    "strengths_weaknesses": [
        "Ask about a strength that helps in this occupation, with a concrete example from school, hobbies or a job.",
        "Ask about a weakness or something they want to get better at, and what they do about it.",
    ],
    "situational": [
        "Ask about a concrete situation from school, a club or a group project where they had to take responsibility or work in a team.",
        "Ask about a time something went wrong or there was a conflict: what happened, what they did, what they learned.",
    ],
    "candidate_questions": ["Invite the candidate to ask their own questions about the apprenticeship or the company."],
}

LANGUAGES = {
    "de": "German (Swiss Standard German, use 'ss' instead of 'ß')",
    "fr": "French",
    "it": "Italian",
    "gsw": "Swiss German dialect (Schweizerdeutsch, e.g. Zurich dialect), written the way Swiss people write it in chats",
}

# How the coach (tips and final report) addresses the candidate: always informal, in all languages.
ADDRESS = {
    "de": "Address the candidate with informal 'du'. Never use 'Sie', 'man' or the third person ('der Kandidat', 'er', 'sie').",
    "fr": "Address the candidate with informal 'tu'. Never use 'vous' or the third person ('le candidat', 'il', 'elle').",
    "it": "Address the candidate with informal 'tu'. Never use 'Lei' or the third person ('il candidato', 'lui', 'lei').",
}
ADDRESS["gsw"] = ADDRESS["de"]

# Fixed closing line when the candidate has no more questions (saves an LLM call). Key: (language, formal).
CLOSING = {
    ("de", False): "Vielen Dank{name}! Es hat mich gefreut, dich kennenzulernen. Wir melden uns bald bei dir.",
    ("de", True): "Vielen Dank{name} für das Gespräch. Wir melden uns in den nächsten Tagen bei Ihnen.",
    ("fr", False): "Merci beaucoup{name} ! J'ai été ravi·e de faire ta connaissance. Nous te recontacterons bientôt.",
    ("fr", True): "Merci beaucoup{name} pour cet entretien. Nous vous recontacterons prochainement.",
    ("it", False): "Grazie mille{name}! È stato un piacere conoscerti. Ti ricontatteremo presto.",
    ("it", True): "Grazie mille{name} per il colloquio. La ricontatteremo nei prossimi giorni.",
    ("gsw", False): "Merci vielmal{name}! Hät mi gfreut, dich kenneztlehre. Mir mälded eus bald bi dir.",
    ("gsw", True): "Merci vielmal{name} für s Gspröch. Mir mälded eus i de nächschte Täg bi Ihne.",
}


def closing_message(language: str, formal: bool, first_name: Optional[str]) -> str:
    return CLOSING[(language, formal)].format(name=f", {first_name}" if first_name else "")


def _setting(occupation: dict) -> str:
    return (f"Apprenticeship: {occupation['label']['de']} ({occupation['description'].strip()})\n"
            "The candidate is a school student (about 14-16 years old) applying for this apprenticeship in Switzerland.")


def _candidate_info(candidate: Optional[dict]) -> str:
    if not candidate:
        return ""
    parts = [f"{key.replace('_', ' ')}: {value}" for key, value in candidate.items() if value]
    return "About the candidate: " + "; ".join(parts) + "\n" if parts else ""


_ANALYSIS_EXAMPLE = {
    "scores": {"relevance": 4, "structure": 2, "examples": 3, "motivation": 5, "language": 4, "self_reflection": 2},
    "short_tip": "One short, concrete tip for the candidate.",
    "follow_up": False,
}


def analysis_messages(occupation: dict, language: str, question: str, answer: str) -> list[dict]:
    criteria = "\n".join(f"- {key}: {desc}" for key, desc in CRITERIA.items())
    system = (
        "You evaluate a candidate's answer in a practice interview for an apprenticeship.\n"
        f"{_setting(occupation)}\n"
        "Judge the answer by what can be expected from a school student, not from an experienced professional.\n"
        "Be encouraging: the tip should start with something positive and then give one concrete improvement.\n\n"
        f"Score each criterion from 1 (weak) to 5 (excellent):\n{criteria}\n"
        "Guide: 1 = no real answer (e.g. 'I don't know'), 3 = okay but general, 5 = clear, on topic and with a "
        "concrete example. An answer that lists its points in order ('first ..., second ...') has good structure. "
        "Score each criterion on its own; they usually differ.\n\n"
        'Set "follow_up" to true if the answer is vague or incomplete and a follow-up question would help.\n'
        f'Write "short_tip" (one sentence) in {LANGUAGES[language]}. {ADDRESS[language]}\n\n'
        "Respond with ONLY a JSON object, no other text, in this shape (the numbers are only an example):\n"
        f"{json.dumps(_ANALYSIS_EXAMPLE)}"
    )
    user = f"Interview question:\n{question}\n\nCandidate answer:\n{answer}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _task(mode: str, phase: str, question_number: int) -> str:
    goals = PHASE_GOALS.get(phase, [""])
    goal = goals[min(question_number, len(goals)) - 1]
    answer_question = ("The candidate asked a question. Answer it briefly and honestly; you do not know the "
                       "company's internals, so stay general where needed.")
    tasks = {
        "opening": f"Greet the candidate briefly and ask your first question. Goal: {goal}",
        "follow_up": "The last answer was vague or incomplete. Ask ONE follow-up question that digs deeper into it.",
        "next_question": f"Ask ONE new question. Goal: {goal}",
        "new_phase": f"Start a new part of the interview with one short transition sentence, then ask ONE question. Goal: {goal}",
        "answer_candidate": f"{answer_question} Then ask whether they have any further questions.",
        "answer_and_close": f"{answer_question} Then thank them for the interview and say goodbye.",
    }
    return tasks[mode]


_CLOSING_MODES = ("answer_and_close", "close")
_NO_GOODBYE = (" The interview is not over yet: do not say goodbye, do not thank the candidate for the interview "
               "and do not promise them the apprenticeship.")


def interviewer_messages(occupation: dict, style: dict, language: str, candidate: Optional[dict], phase: str,
                         mode: str, question_number: int, transcript: list[dict]) -> list[dict]:
    system = (
        "You are the interviewer in a practice interview for an apprenticeship.\n"
        f"{_setting(occupation)}\n"
        f"{_candidate_info(candidate)}"
        f"{style['prompt'].strip()}\n"
        f"Conduct the interview in {LANGUAGES[language]}.\n"
        f"Current interview phase: {phase}.\n"
        f"{_task(mode, phase, question_number)}\n"
        "Keep it short (at most 3 sentences), use simple words and keep a positive tone suitable for a teenager. "
        "Do not evaluate or comment on the "
        "candidate's answers. Do not repeat questions that were already asked."
        f"{'' if mode in _CLOSING_MODES else _NO_GOODBYE}"
    )
    messages = [{"role": "system", "content": system}]
    for turn in transcript:
        messages.append({"role": "assistant" if turn["role"] == "interviewer" else "user", "content": turn["text"]})
    if not transcript:
        messages.append({"role": "user", "content": "(The candidate has joined the interview.)"})
    return messages


_REPORT_EXAMPLE = {
    "criteria": {key: {"comment": "One sentence about this criterion.", "evidence": "Exact quote from the candidate."}
                 for key in CRITERIA},
    "strengths": ["Strength 1", "Strength 2"],
    "improvements": [{"tip": "Concrete tip.", "example_answer": "A short example of a better answer."}],
}


def report_messages(occupation: dict, language: str, averages: dict[str, float], analyses: list[dict],
                    transcript: list[dict]) -> list[dict]:
    scores = "\n".join(f"- {key}: {value:.1f}/5 ({CRITERIA[key]})" for key, value in averages.items())
    tips = "\n".join(f"- [{a['phase']}] {a['short_tip']}" for a in analyses if a.get("short_tip"))
    dialogue = "\n".join(f"{t['role'].upper()}: {t['text']}" for t in transcript)
    system = (
        "You are an experienced career coach for young people. Write the final feedback after a practice "
        "interview for an apprenticeship.\n"
        f"{_setting(occupation)}\n"
        f"Write all texts in {LANGUAGES[language]}. {ADDRESS[language]} Be positive and "
        "encouraging, suitable for a teenager, but honest about what to improve.\n"
        f"- criteria: use exactly these keys: {', '.join(CRITERIA)}. For each one sentence of comment that "
        "explains the score, and as evidence an EXACT quote (a few words) from the CANDIDATE's answers that "
        "supports it, or an empty string if there is none.\n"
        "- strengths: 2-3 strengths, each referring to something the candidate actually said.\n"
        "- improvements: 2-3 concrete tips, each referring to one of the candidate's answers, with a short "
        "example of a better answer. The example may only use facts the candidate mentioned; for anything "
        "else use a placeholder in square brackets, e.g. [dein Hobby].\n"
        "Base everything on the scores, tips and transcript below. Do not invent facts.\n\n"
        "Respond with ONLY a JSON object, no other text, in this shape:\n"
        f"{json.dumps(_REPORT_EXAMPLE, ensure_ascii=False)}"
    )
    user = f"Average scores:\n{scores or '(none)'}\n\nTips per answer:\n{tips or '(none)'}\n\nTranscript:\n{dialogue}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
