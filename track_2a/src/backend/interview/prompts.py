"""Criteria, phases and prompt builders for the interview loop."""

import json

# The 6 analysis criteria, each scored 1-5. Keys are the JSON keys the model must return.
CRITERIA = {
    "relevance": "Does the answer address the question that was asked?",
    "structure": "Is the answer logically organised (e.g. situation, action, result)?",
    "concreteness": "Does it use concrete examples, facts or numbers instead of generalities?",
    "self_reflection": "Does the candidate show awareness of their own strengths, weaknesses and learning?",
    "motivation_fit": "Does it show motivation for and fit with the role?",
    "communication": "Is it clear, concise and professional in tone?",
}

PHASES = [
    ("intro", "Warm-up: let the candidate introduce themselves and their background."),
    ("motivation", "Why this role and this company? What drives the candidate?"),
    ("strengths_weaknesses", "Strengths and weaknesses, with concrete evidence."),
    ("situational", "Behavioural/situational questions: past situations, conflicts, decisions."),
    ("candidate_questions", "Invite the candidate to ask their own questions about the role."),
    ("feedback", "Interview finished; final feedback follows."),
]

LANGUAGES = {"de": "German", "fr": "French", "it": "Italian"}

_EXAMPLE = {
    "scores": {key: 3 for key in CRITERIA},
    "feedback": "One or two sentences of feedback for the candidate.",
    "follow_up": False,
}


def analysis_messages(role: str, language: str, question: str, answer: str) -> list[dict]:
    criteria = "\n".join(f"- {key}: {desc}" for key, desc in CRITERIA.items())
    system = (
        "You evaluate a candidate's answer in a job interview.\n"
        f"Role applied for: {role}\n\n"
        f"Score each criterion from 1 (very weak) to 5 (excellent):\n{criteria}\n\n"
        'Set "follow_up" to true if the answer is vague or incomplete and a follow-up question would help.\n'
        f'Write "feedback" in {LANGUAGES[language]}.\n\n'
        "Respond with ONLY a JSON object, no other text, exactly in this shape:\n"
        f"{json.dumps(_EXAMPLE)}"
    )
    user = f"Interview question:\n{question}\n\nCandidate answer:\n{answer}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def repair_message(error: str) -> dict:
    return {
        "role": "user",
        "content": (
            f"Your previous output could not be used: {error}\n"
            "Return ONLY the corrected JSON object with all 6 scores as integers 1-5, "
            '"feedback" as a string and "follow_up" as true/false. No other text.'
        ),
    }


def interviewer_messages(role: str, language: str, phase: str, follow_up: bool, transcript: list[dict]) -> list[dict]:
    goal = dict(PHASES)[phase]
    if not transcript:
        task = "Greet the candidate briefly and ask your first question."
    elif follow_up:
        task = "The last answer was vague or incomplete. Ask ONE follow-up question that digs deeper into it."
    else:
        task = "Ask ONE new question for the current interview phase."
    system = (
        f"You are a professional, friendly job interviewer for the role: {role}.\n"
        f"Conduct the interview in {LANGUAGES[language]}.\n"
        f"Current phase: {phase} ({goal})\n"
        f"{task}\n"
        "Reply with the question only (at most 2 sentences), no evaluation, no commentary."
    )
    messages = [{"role": "system", "content": system}]
    for turn in transcript:
        messages.append({"role": "assistant" if turn["speaker"] == "interviewer" else "user", "content": turn["text"]})
    if not transcript:
        messages.append({"role": "user", "content": "(The candidate has joined the interview.)"})
    return messages
