"""Engineering Discovery Engine — Intent Classification.

Extends existing intent detection with domain classification.
Regex-first approach for deterministic classification, LLM fallback for ambiguous cases.

Current intents (6): question, task_request, task_confirm, approval, status, chat
Extended domains (15): feature, bugfix, refactor, docs, test, infra, research,
architecture, security, performance, devops, database, ui, ai_llm, chat
"""

import re
import logging
from dataclasses import dataclass, field
from discovery.domains import DomainRegistry

logger = logging.getLogger("aic.discovery.intent")


@dataclass
class IntentResult:
    """Result of intent classification."""

    base_intent: str  # task_request, question, chat, etc.
    domain: str       # feature, bugfix, ui, backend, etc.
    confidence: float  # 0.0 to 1.0
    reason: str = ""
    domain_fields: list[str] = field(default_factory=list)


# Domain classification patterns — regex-first for deterministic classification
DOMAIN_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    # Bug fix patterns (highest priority — specific verbs)
    ("bugfix", "backend", re.compile(
        r"\b(fix|bug|error|broken|crash|fail|issue|defect|patch|resolve)\b", re.I)),
    ("bugfix", "frontend", re.compile(
        r"\b(ui\s*bug|css\s*fix|style\s*fix|layout\s*issue|rendering|display\s*bug)\b", re.I)),

    # Test patterns
    ("test", "testing", re.compile(
        r"\b(tests?|specs?|coverage|unit\s*tests?|integration\s*tests?|e2e|end.to.end)\b", re.I)),

    # Documentation patterns
    ("docs", "documentation", re.compile(
        r"\b(doc|documentation|readme|guide|tutorial|manual|changelog|api\s*doc)\b", re.I)),

    # Refactoring patterns
    ("refactor", "refactoring", re.compile(
        r"\b(refactor|clean|restructure|simplify|optimize\s*code|extract|rename)\b", re.I)),

    # Infrastructure patterns
    ("infra", "infrastructure", re.compile(
        r"\b(deploy|docker|ci.?cd|pipeline|infrastructure|server|host|kubernetes|container)\b", re.I)),

    # Research patterns
    ("research", "research", re.compile(
        r"\b(research|investigate|analyze|explore|study|evaluate|compare)\b", re.I)),

    # Architecture patterns
    ("architecture", "architecture", re.compile(
        r"\b(architecture|redesign|microservice|rewrite\s*core|framework\s*migration)\b", re.I)),

    # Security patterns
    ("security", "security", re.compile(
        r"\b(security|encrypt|hash|token|rbac|permission|sanitize|inject|vulnerability|auth)\b", re.I)),

    # Performance patterns
    ("performance", "performance", re.compile(
        r"\b(performance|latency|optimize|speed|fast|slow|bottleneck|cache)\b", re.I)),

    # DevOps patterns
    ("devops", "operations", re.compile(
        r"\b(automate|script|cron|monitoring|alerting|backup|restore)\b", re.I)),

    # Database patterns
    ("database", "database", re.compile(
        r"\b(database|sql|migration|schema|query|sqlite|postgres|mysql|orm|column|table|index)\b", re.I)),

    # AI/LLM patterns
    ("ai_llm", "ai", re.compile(
        r"\b(ai|llm|gpt|claude|embedding|rag|prompt|model|openai|anthropic)\b", re.I)),

    # UI patterns
    ("ui", "frontend", re.compile(
        r"\b(ui|css|tailwind|react|vue|angular|component|layout|dashboard|page|form|button|modal|responsive|style|design|dark\s*mode)\b", re.I)),

    # Feature patterns (catch-all for new capabilities)
    ("feature", "coding", re.compile(
        r"\b(build|create|add|implement|develop|make|feature|enhance|improve)\b", re.I)),
]


class IntentClassifier:
    """Classifies user intent and engineering domain.

    Uses regex-first approach for deterministic classification.
    Falls back to LLM only for ambiguous cases.
    """

    @classmethod
    def classify(cls, content: str, history: list | None = None) -> IntentResult:
        """Classify user intent and engineering domain.

        Args:
            content: User message content
            history: Conversation history for context

        Returns:
            IntentResult with base_intent, domain, confidence
        """
        if not content or not content.strip():
            return IntentResult(
                base_intent="chat",
                domain="chat",
                confidence=1.0,
                reason="Empty message",
            )

        lower = content.lower().strip()
        words = content.split()

        # Step 1: Classify base intent (reuse existing logic)
        base_intent = cls._classify_base_intent(lower, words)

        # Step 2: If not a task request, return early
        if base_intent != "task_request":
            return IntentResult(
                base_intent=base_intent,
                domain="chat",
                confidence=0.95,
                reason=f"Base intent is {base_intent}, not task_request",
            )

        # Step 3: Classify domain for task_request
        domain, confidence = cls._classify_domain(lower, words)

        # Step 4: Get domain mandatory fields
        domain_obj = DomainRegistry.get(domain)
        domain_fields = []
        if domain_obj:
            domain_fields = [f.name for f in domain_obj.mandatory_fields if f.required]

        return IntentResult(
            base_intent=base_intent,
            domain=domain,
            confidence=confidence,
            reason=f"Domain classified as {domain}",
            domain_fields=domain_fields,
        )

    @classmethod
    def _classify_base_intent(cls, lower: str, words: list) -> str:
        """Classify base intent — delegates to shared intent patterns.

        Single source of truth: shared/intent_patterns.py
        """
        from shared.intent_patterns import classify_intent
        return classify_intent(lower)

    @staticmethod
    def _sanitize_content_for_domain_classification(content: str) -> str:
        """Strip file paths, URLs, folder names from content before domain classification."""
        import re
        
        sanitized = re.sub(r"(?:/[^\s\"'<>|?*]+)+/?", "", content, flags=re.I)
        sanitized = re.sub(r"[A-Za-z]:[\\\/][^\s\"'<>|?*]+", "", sanitized, flags=re.I)
        sanitized = re.sub(r"https?://\S+", "", sanitized, flags=re.I)
        sanitized = re.sub(r'"[^"]*"', "", sanitized)
        sanitized = re.sub(r"'[^']*'", "", sanitized)
        
        return sanitized.strip()
    
    @classmethod
    def _classify_domain(cls, lower: str, words: list) -> tuple[str, float]:
        """Classify engineering domain from task request.

        Returns (domain_name, confidence).
        """
        matches: list[tuple[str, float]] = []
        
        # Sanitize content first to prevent path/URL keyword pollution
        cleaned = cls._sanitize_content_for_domain_classification(lower)
        
        for domain, _context, pattern in DOMAIN_PATTERNS:
            if pattern.search(cleaned):
                # Calculate confidence based on match specificity
                match_count = len(pattern.findall(cleaned))
                confidence = min(0.95, 0.70 + (match_count * 0.05))
                matches.append((domain, confidence))

        if not matches:
            # Default to feature for task requests with no domain match
            return "feature", 0.60

        # Return highest confidence match
        # Priority: specificity (bugfix/test/docs/refactor > feature)
        priority_order = [
            "bugfix", "test", "docs", "refactor", "infra", "research",
            "architecture", "security", "performance", "devops", "database",
            "ai_llm", "ui", "feature"
        ]

        for priority_domain in priority_order:
            for match_domain, match_confidence in matches:
                if match_domain == priority_domain:
                    return match_domain, match_confidence

        # Fallback to first match
        return matches[0]

    @classmethod
    async def classify_with_llm(
        cls,
        content: str,
        history: list | None = None,
    ) -> IntentResult:
        """Classify using LLM for ambiguous cases.

        Only used when regex classification has low confidence.
        """
        from llm.provider import provider_manager, ModelTier

        provider = provider_manager.get_active_with_key()
        if not provider:
            # Fallback to regex
            return cls.classify(content, history)

        CLASSIFY_PROMPT = """Classify this engineering request into exactly one domain:
feature, bugfix, refactor, docs, test, infra, research, architecture, security,
performance, devops, database, ui, ai_llm, chat

Respond with ONLY the domain name, nothing else."""

        try:
            result = await provider.chat(
                messages=[
                    {"role": "system", "content": CLASSIFY_PROMPT},
                    {"role": "user", "content": content},
                ],
                tier=ModelTier.SPRINTER,
                temperature=0.0,
                max_tokens=20,
                purpose="discovery_domain_classification",
            )

            raw = result.get("content", "").strip().lower()
            if raw.startswith("``"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            valid_domains = DomainRegistry.get_names()
            if raw in valid_domains:
                return IntentResult(
                    base_intent="task_request",
                    domain=raw,
                    confidence=0.90,
                    reason=f"LLM classified as {raw}",
                )

        except Exception as e:
            logger.warning(f"LLM domain classification failed: {e}")

        # Fallback to regex
        return cls.classify(content, history)
