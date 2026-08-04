"""AIC Platform — Anti-AI-Slop Taste Checker.

Quality gate that scans text output for AI-ism patterns and reports findings.
Used by executor (closeout/verification) and chat engine to flag or rewrite
sloppy AI-generated text.

Three severity levels:
- high: banned phrases that should never appear
- medium: structural patterns that indicate AI slop
- low: stylistic suggestions
"""
import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("aic.taste")


# ── AI-ism Wordlist ──────────────────────────────────────

BANNED_PHRASES: list[str] = [
    "delve", "delve into", "delving",
    "crucial", "pivotal", "comprehensive",
    "testament", "underscore", "underscoring",
    "vibrant", "seamless", "groundbreaking",
    "it's important to note",
    "i'd be happy to",
    "let's dive in",
    "here's what you need to know",
    "in conclusion",
    "the future looks bright",
    "at the end of the day",
    "when it comes to",
    "moving forward",
    "circle back",
    "game-changer",
    "in today's fast-paced world",
    "i'd be happy to help",
    "great question",
    "good question",
    "let me know if",
    "let me know if you need",
    "feel free to",
    "don't hesitate to",
    "don't hesitate",
    "do not hesitate",
    "it's worth noting",
    "it's worth mentioning",
    "not only.*but also",
    "it's not just.*it's",
    "serves as a",
    "plays a crucial role",
    "in the realm of",
    "navigate the complexities",
    "shed light on",
    "tapestry",
    "multifaceted",
    "holistic approach",
    "leverage",
    "utilize",
    "cutting-edge",
    "state-of-the-art",
    "robust solution",
    "paradigm shift",
    # BUG-20: greeting / polite AI-isms
    "how can i help",
    "happy to help",
    "is there anything else",
    "anything else i can",
    "what else can i do",
    "i hope this helps",
    "hope this helps",
    "as an ai",
    "as an ai assistant",
    "as a language model",
    "i'm here to help",
    "here to help you",
    "absolutely!",
    "of course!",
    "certainly!",
]

# Compiled patterns for banned phrases (case-insensitive)
# BUG-20: Handle trailing non-word chars (e.g. "absolutely!") properly
_BANNED_RE = []
for _p in BANNED_PHRASES:
    _escaped = re.escape(_p).replace(r'\.\*', '.*')
    # Word boundary at start only if phrase starts with word char
    _start = r'\b' if _p[0].isalnum() else ''
    # Word boundary at end only if phrase ends with word char;
    # for trailing punctuation use lookahead for non-word or EOL
    _end = r'\b' if _p[-1].isalnum() else r'(?=\W|$)'
    _BANNED_RE.append(re.compile(_start + _escaped + _end, re.IGNORECASE))

# Single-word AI-isms — demoted to "medium" severity. FIX: a lone word-level
# AI-ism (e.g. "crucial", "leverage", "comprehensive") must NOT trigger a full
# rewrite; only phrase-level patterns or 2+ distinct AI-isms are "high".
_WORD_LEVEL: set[str] = {
    "delve", "delving",
    "crucial", "pivotal", "comprehensive",
    "testament", "underscore", "underscoring",
    "vibrant", "seamless", "groundbreaking",
    "tapestry", "multifaceted", "leverage", "utilize",
}


# ── Structural Heuristics ────────────────────────────────

@dataclass
class Finding:
    """A single taste finding."""
    pattern: str
    severity: str  # high | medium | low
    count: int = 1
    examples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pattern": self.pattern,
            "severity": self.severity,
            "count": self.count,
            "examples": self.examples[:3],
        }


def scan_text(text: str) -> list[Finding]:
    """Scan text for AI-ism patterns and return findings.

    Returns a list of Finding objects. Empty list = clean text.
    """
    if not text or len(text.strip()) < 20:
        return []

    findings: list[Finding] = []
    lower = text.lower()

    # 1. Banned phrases
    word_level_findings: list[Finding] = []
    for i, phrase in enumerate(BANNED_PHRASES):
        pattern = _BANNED_RE[i]
        matches = pattern.findall(text)
        if matches:
            # FIX: demote word-level instant bans to "medium" — a single word
            # like "crucial" must not trigger a full rewrite. Phrase-level
            # patterns (greetings/hedges) stay "high".
            severity = "medium" if phrase in _WORD_LEVEL else "high"
            finding = Finding(
                pattern=f"banned:{phrase}",
                severity=severity,
                count=len(matches),
                examples=[m[:80] for m in matches[:3]],
            )
            findings.append(finding)
            if severity == "medium":
                word_level_findings.append(finding)

    # FIX: require 2+ distinct word-level AI-isms (or a phrase-level pattern)
    # before word-level findings are treated as "high".
    if len(word_level_findings) >= 2:
        for f in word_level_findings:
            f.severity = "high"

    # 2. Em-dash density (— or --)
    em_dashes = len(re.findall(r'[—–]', text)) + len(re.findall(r'(?<!-)--(?!-)', text))
    word_count = max(len(text.split()), 1)
    em_density = em_dashes / word_count * 100
    if em_dashes > 3 and em_density > 0.5:
        findings.append(Finding(
            pattern="em_dash_overuse",
            severity="medium",
            count=em_dashes,
            examples=[f"{em_dashes} em-dashes in {word_count} words ({em_density:.1f}%)"],
        ))

    # 3. Rule-of-three forcing (three consecutive comma-separated items)
    triple_patterns = re.findall(
        r'\b(\w+),\s+(\w+),\s+(?:and|or)\s+(\w+)\b', text
    )
    if len(triple_patterns) > 3:
        findings.append(Finding(
            pattern="rule_of_three",
            severity="low",
            count=len(triple_patterns),
            examples=[", ".join(t) for t in triple_patterns[:3]],
        ))

    # 4. "-ing" tail superficial openers ("Highlighting...", "Underscoring...")
    ing_openers = re.findall(
        r'^(Highlighting|Underscoring|Emphasizing|Noting|Showcasing|Demonstrating)\b',
        text, re.MULTILINE
    )
    if ing_openers:
        findings.append(Finding(
            pattern="ing_tail_opener",
            severity="medium",
            count=len(ing_openers),
            examples=ing_openers[:3],
        ))

    # 5. Title Case headings (## This Is Title Case)
    title_case_headings = re.findall(
        r'^#{1,6}\s+((?:[A-Z][a-z]+\s+){2,}[A-Z][a-z]+)',
        text, re.MULTILINE
    )
    if title_case_headings:
        findings.append(Finding(
            pattern="title_case_heading",
            severity="low",
            count=len(title_case_headings),
            examples=title_case_headings[:3],
        ))

    # 6. Emoji in headings
    emoji_headings = re.findall(
        r'^#{1,6}\s+.*[\U0001F300-\U0001F9FF]',
        text, re.MULTILINE
    )
    if emoji_headings:
        findings.append(Finding(
            pattern="emoji_in_heading",
            severity="low",
            count=len(emoji_headings),
            examples=[h[:60] for h in emoji_headings[:3]],
        ))

    # 7. Boldface overuse (**text**)
    bold_count = len(re.findall(r'\*\*[^*]+\*\*', text))
    if bold_count > 10:
        findings.append(Finding(
            pattern="boldface_overuse",
            severity="low",
            count=bold_count,
            examples=[f"{bold_count} bold segments"],
        ))

    # 8. Rhetorical questions immediately answered
    rhet_q = re.findall(
        r'([^.!?]*\?)\s+([A-Z][^.!?]*\.)', text
    )
    if len(rhet_q) > 2:
        findings.append(Finding(
            pattern="rhetorical_question_answered",
            severity="medium",
            count=len(rhet_q),
            examples=[f"{q} {a}" for q, a in rhet_q[:3]],
        ))

    # 9. Mic-drop closings
    mic_drop_patterns = [
        r"(?:and that's|that's) (?:the bottom line|all there is to it|that simple)\.?$",
        r"(?:period|full stop)\.?$",
        r"mic drop",
    ]
    for pat in mic_drop_patterns:
        matches = re.findall(pat, text, re.IGNORECASE | re.MULTILINE)
        if matches:
            findings.append(Finding(
                pattern="mic_drop_closing",
                severity="medium",
                count=len(matches),
                examples=[m[:60] for m in matches[:3]],
            ))

    # 10. Curly quotes ("" '') — should be straight quotes
    curly = len(re.findall(r'[“”‘’]', text))
    if curly > 0:
        findings.append(Finding(
            pattern="curly_quotes",
            severity="low",
            count=curly,
            examples=[f"{curly} curly quote characters"],
        ))

    return findings


def has_ai_slop(text: str, threshold: int = 1) -> bool:
    """Quick check: does text contain any high-severity AI-isms?"""
    findings = scan_text(text)
    high_count = sum(f.count for f in findings if f.severity == "high")
    return high_count >= threshold


def scan_summary(text: str) -> dict:
    """Return a summary dict suitable for API responses."""
    findings = scan_text(text)
    return {
        "total_findings": len(findings),
        "high": sum(1 for f in findings if f.severity == "high"),
        "medium": sum(1 for f in findings if f.severity == "medium"),
        "low": sum(1 for f in findings if f.severity == "low"),
        "findings": [f.to_dict() for f in findings],
    }


# ── Rewrite Prompt ───────────────────────────────────────

REWRITE_PROMPT = """Rewrite the following text to remove AI writing patterns while keeping the meaning.
Rules:
- Remove: "delve", "crucial", "comprehensive", "seamless", "groundbreaking", "it's important to note", "in conclusion"
- Remove: AI greeting patterns like "How can I help you today?", "I'd be happy to", "Great question!", "Let me know if", "Feel free to", "Don't hesitate"
- Remove: em-dash overuse, forced rule-of-three, "-ing" superficial openers
- Use: simple words ("is" not "serves as"), varied sentence length, specific details
- Sound like a knowledgeable human, not a polite LLM
- Keep the same information and structure

Text to rewrite:
"""
