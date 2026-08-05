"""Shared intake-completeness evaluation — single source of truth.

Used by:
- conversation/engine.py (ConversationEngine._handle_task_request)
- api/routes/chat.py (/chat/execute clarify gate)

Extracted from ConversationEngine._evaluate_intake_completeness /
_user_forces_task_creation so both the conversation engine and the /chat/execute
streaming gate agree on what counts as a "complete" task request.
"""
import re

# Reduced from 6 to 3 mandatory fields — more pragmatic
_INTAKE_MANDATORY = {
    "business_goal": r"\b(goal|purpose|objective|why|app to|site to|website for|buatkan|untuk|tujuan|aplikasi|sistem|aplikasi ini|project)\b",
    "target_user": r"\b(user|users|audience|people|client|customer|admin|developer|pengembang|pelanggan|pengguna|masyarakat|umum|untuk siapa)\b",
    "core_features": r"\b(feature|features|allow|function|receive|send|auth|login|button|api|crud|fitur|section|table|form|gallery|kontak|lokasi|sistem|dashboard|database|user|payment|notification)\b",
}

# Explicit "start now" language short-circuits the completeness check.
_FORCE_BUILD_PATTERN = re.compile(
    r"\b(create task|build now|start task|start build|create task to|"
    r"langsung kerjakan|gas sekarang|mulai sekarang|kerjakan sekarang)\b",
    re.I,
)

_FORCE_TASK_PATTERN = re.compile(
    r"\b(create task|build now|start task|start build|create the task|"
    r"just do it|do it now|implement now|kerjakan sekarang|buat task|"
    r"langsung kerjakan|gas sekarang)\b",
    re.I,
)


def evaluate_intake_completeness(text_corpus: str) -> tuple[bool, list[str]]:
    """Evaluate requirement completeness against the mandatory intake checklist.

    Returns (is_complete, missing_fields). Complete if <= 1 mandatory field is
    missing or the user explicitly forces a build.
    """
    text = (text_corpus or "").lower()
    missing = [field for field, pattern in _INTAKE_MANDATORY.items() if not re.search(pattern, text)]
    is_complete = (len(missing) <= 1) or bool(_FORCE_BUILD_PATTERN.search(text))
    return is_complete, missing


def user_forces_task_creation(text: str) -> bool:
    """True when the user explicitly wants engineering to start now."""
    return bool(_FORCE_TASK_PATTERN.search((text or "").lower()))


def missing_field_question(missing_field: str) -> str | None:
    """Map a missing mandatory intake field to a clarifying question."""
    field_questions = {
        "business_goal": "What is the main goal of this project? What should it accomplish?",
        "target_user": "Who is this for? (target users / audience)",
        "core_features": "What core features must it include? (e.g. login, gallery, dashboard, contact form)",
    }
    return field_questions.get(missing_field)