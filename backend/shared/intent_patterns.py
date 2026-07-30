"""Shared intent detection patterns — single source of truth.

Used by:
- conversation/engine.py (ConversationEngine._detect_intent)
- discovery/intent.py (IntentClassifier._classify_base_intent)

This module eliminates the triplicate regex definitions that existed
across ConversationEngine, IntentClassifier._classify_base_intent,
and IntentClassifier.classify.
"""
import re

# ── Intent constants ────────────────────────────────────
INTENT_APPROVAL = "approval"
INTENT_STATUS = "status"
INTENT_TASK_CONFIRM = "task_confirm"
INTENT_TASK_REQUEST = "task_request"
INTENT_QUESTION = "question"
INTENT_CHAT = "chat"

# ── Compiled patterns ───────────────────────────────────
APPROVAL_PATTERN = re.compile(
    r"\b(approve|reject|deny|accept|decline|setuju|tolak|terima|iya)\b", re.I
)
STATUS_PATTERN = re.compile(
    r"\b(status|progress|how.?s it going|what.?s happening|update|kemajuan|progres|perkembangan)\b", re.I
)
CONFIRM_PATTERN = re.compile(
    r"\b(yes|ya|ok|oke|go ahead|do it|confirm|proceed|sure|setuju|lanjutkan?|proses|"
    r"gas|let'?s go|create it|make it so)\b",
    re.I,
)
QUESTION_START_PATTERN = re.compile(
    r"^\b(what|how|why|when|where|who|which|can you|could you|do you|is it|are there|"
    r"bagaimana|apa|kenapa|mengapa|kapan|dimana|siapa|mana|bisakah|bisa)\b",
    re.I,
)
TASK_VERB_PATTERN = re.compile(
    r"\b(build|create|make|fix|add|implement|deploy|refactor|develop|design|write|"
    r"generate|scaffold|set\s*up|document|optimize|improve|update|change|"
    r"configure|setup|install|remove|delete|rename|move|copy|extract|merge|"
    r"bangun|buat|perbaiki|tambah|terapkan|kembangkan|rancang|tulis|"
    r"kerjakan|buatkan|pasang|hapus|pindah|salin|gabung|debug|profil|audit|"
    r"tes|test|review|inspect|analisis|analyze)\b",
    re.I,
)
TEST_TASK_PATTERN = re.compile(
    r"\b(write tests?|add tests?|create tests?|test the \w+|"
    r"tulis test|tambah test|buat test|tes)\b", re.I
)


def classify_intent(content: str) -> str:
    """Classify user message intent using regex patterns.

    This is the canonical intent detection function.
    Both ConversationEngine and IntentClassifier delegate to this.

    Priority order:
    1. Approval (approve/reject keywords)
    2. Status (progress/update keywords)
    3. Task confirm (short affirmative messages)
    4. Question (ends with ? or starts with question word)
    5. Task request (action verbs + minimum 3 words)
    6. Chat (default fallback)
    """
    lower = content.lower().strip()
    words = content.split()

    # Task confirm first — short messages with confirm/task verbs override approval
    if len(words) <= 6 and CONFIRM_PATTERN.search(lower):
        return INTENT_TASK_CONFIRM

    if APPROVAL_PATTERN.search(lower):
        return INTENT_APPROVAL

    if STATUS_PATTERN.search(lower):
        return INTENT_STATUS

    words = content.split()
    if len(words) <= 6 and CONFIRM_PATTERN.search(lower):
        return INTENT_TASK_CONFIRM

    is_question = lower.endswith("?") or bool(QUESTION_START_PATTERN.match(lower))
    if is_question:
        return INTENT_QUESTION

    if TASK_VERB_PATTERN.search(lower) and len(words) >= 3:
        return INTENT_TASK_REQUEST

    if TEST_TASK_PATTERN.search(lower):
        return INTENT_TASK_REQUEST

    return INTENT_CHAT
