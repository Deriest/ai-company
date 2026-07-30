"""Engineering Discovery Engine — Ambiguity Detection.

Identifies and scores ambiguity types in engineering requests.
Detects 7 ambiguity types from the SOT.
"""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("aic.discovery.ambiguity")


@dataclass
class Ambiguity:
    """A detected ambiguity in the request."""

    type: str  # lexical, referential, scope, technical, missing_context, conflicting, temporal
    description: str
    severity: float  # 0.0 to 1.0
    example: str = ""
    suggestion: str = ""


@dataclass
class AmbiguityReport:
    """Report of detected ambiguities."""

    ambiguities: list[Ambiguity] = field(default_factory=list)
    overall_score: float = 0.0  # 0.0 = no ambiguity, 1.0 = maximum ambiguity
    has_ambiguity: bool = False


# Ambiguity detection patterns
LEXICAL_PATTERNS = [
    (r"\b(a|an|the)\s+(button|field|form|page|section|component|feature)\b",
     "Missing target — which specific element?"),
    (r"\b(something|somehow|somewhere)\b",
     "Vague reference — what specifically?"),
]

REFERENTIAL_PATTERNS = [
    (r"\b(it|that|this|those|these)\b(?!\s+(?:is|are|was|were))",
     "Unresolved pronoun — what does 'it' refer to?"),
    (r"\b(the thing|the stuff|the part|the section)\b",
     "Unresolved reference — which thing?"),
    (r"\b(the other one|another one|similar)\b",
     "Unresolved reference — which other one?"),
]

SCOPE_PATTERNS = [
    (r"\b(improve|optimize|enhance|update|change)\b(?!.*\b(specific|particular|only|just)\b)",
     "Unbounded scope — which component to improve?"),
    (r"\b(everything|all|everywhere)\b",
     "Very broad scope — is this really everything?"),
]

TECHNICAL_PATTERNS = [
    (r"\b(best|better|good|nice|proper|correct|right)\s+(approach|way|solution|method)\b",
     "Subjective qualifier — what is 'best'?"),
    (r"\b(simple|easy|quick|fast)\b",
     "Subjective assessment — define what 'simple' means here"),
]

MISSING_CONTEXT_PATTERNS = [
    (r"\b(like the other|like before|as usual|same as)\b",
     "Unresolved reference — which previous instance?"),
    (r"\b(remember|you know|as we discussed)\b",
     "Assumed context — what was discussed?"),
]

CONFLICTING_PATTERNS = [
    (r"\b(fast|quick|speed)\b.*\b(cheap|low.cost|budget)\b",
     "Potential tension — speed vs cost"),
    (r"\b(cheap|low.cost|budget)\b.*\b(high.quality|robust|comprehensive)\b",
     "Potential tension — cost vs quality"),
    (r"\b(real.time|live|instant)\b.*\b(offline|cached|local)\b",
     "Potential tension — real-time vs offline"),
]

TEMPORAL_PATTERNS = [
    (r"\b(soon|asap|urgently|quickly|when ready|eventually)\b",
     "Fuzzy time bound — when exactly?"),
    (r"\b(deadline|by\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|next week))\b",
     "Time constraint — confirm exact date"),
]


class AmbiguityDetector:
    """Detects and scores ambiguity in engineering requests."""

    @classmethod
    def detect(cls, content: str, history: list | None = None) -> AmbiguityReport:
        """Detect ambiguities in the request.

        Args:
            content: User message content
            history: Conversation history for context

        Returns:
            AmbiguityReport with detected ambiguities and score
        """
        if not content:
            return AmbiguityReport(overall_score=0.0, has_ambiguity=False)

        lower = content.lower().strip()
        ambiguities: list[Ambiguity] = []

        # Detect each ambiguity type
        ambiguities.extend(cls._detect_lexical(lower))
        ambiguities.extend(cls._detect_referential(lower))
        ambiguities.extend(cls._detect_scope(lower))
        ambiguities.extend(cls._detect_technical(lower))
        ambiguities.extend(cls._detect_missing_context(lower))
        ambiguities.extend(cls._detect_conflicting(lower))
        ambiguities.extend(cls._detect_temporal(lower))

        # Calculate overall score
        overall_score = cls._calculate_score(ambiguities, content)

        return AmbiguityReport(
            ambiguities=ambiguities,
            overall_score=overall_score,
            has_ambiguity=overall_score > 0.15,  # Lower threshold for better detection
        )

    @classmethod
    def _detect_lexical(cls, text: str) -> list[Ambiguity]:
        """Detect lexical ambiguity."""
        ambiguities = []

        for pattern, description in LEXICAL_PATTERNS:
            if re.search(pattern, text, re.I):
                ambiguities.append(Ambiguity(
                    type="lexical",
                    description=description,
                    severity=0.4,
                    suggestion="Be more specific about which element",
                ))

        return ambiguities

    @classmethod
    def _detect_referential(cls, text: str) -> list[Ambiguity]:
        """Detect referential ambiguity."""
        ambiguities = []

        for pattern, description in REFERENTIAL_PATTERNS:
            matches = re.findall(pattern, text, re.I)
            if matches:
                ambiguities.append(Ambiguity(
                    type="referential",
                    description=description,
                    severity=0.6,
                    suggestion="Specify what the pronoun refers to",
                ))
                break  # One referential ambiguity is enough

        return ambiguities

    @classmethod
    def _detect_scope(cls, text: str) -> list[Ambiguity]:
        """Detect scope ambiguity."""
        ambiguities = []

        for pattern, description in SCOPE_PATTERNS:
            if re.search(pattern, text, re.I):
                ambiguities.append(Ambiguity(
                    type="scope",
                    description=description,
                    severity=0.5,
                    suggestion="Define clear scope boundaries",
                ))
                break

        return ambiguities

    @classmethod
    def _detect_technical(cls, text: str) -> list[Ambiguity]:
        """Detect technical ambiguity."""
        ambiguities = []

        for pattern, description in TECHNICAL_PATTERNS:
            if re.search(pattern, text, re.I):
                ambiguities.append(Ambiguity(
                    type="technical",
                    description=description,
                    severity=0.5,
                    suggestion="Define specific technical criteria",
                ))
                break

        return ambiguities

    @classmethod
    def _detect_missing_context(cls, text: str) -> list[Ambiguity]:
        """Detect missing context ambiguity."""
        ambiguities = []

        for pattern, description in MISSING_CONTEXT_PATTERNS:
            if re.search(pattern, text, re.I):
                ambiguities.append(Ambiguity(
                    type="missing_context",
                    description=description,
                    severity=0.7,
                    suggestion="Provide the specific context being referenced",
                ))
                break

        return ambiguities

    @classmethod
    def _detect_conflicting(cls, text: str) -> list[Ambiguity]:
        """Detect conflicting requirements."""
        ambiguities = []

        for pattern, description in CONFLICTING_PATTERNS:
            if re.search(pattern, text, re.I):
                ambiguities.append(Ambiguity(
                    type="conflicting",
                    description=description,
                    severity=0.8,
                    suggestion="Clarify which requirement takes priority",
                ))
                break

        return ambiguities

    @classmethod
    def _detect_temporal(cls, text: str) -> list[Ambiguity]:
        """Detect temporal ambiguity."""
        ambiguities = []

        for pattern, description in TEMPORAL_PATTERNS:
            if re.search(pattern, text, re.I):
                ambiguities.append(Ambiguity(
                    type="temporal",
                    description=description,
                    severity=0.3,
                    suggestion="Provide specific timeline or deadline",
                ))
                break

        return ambiguities

    @classmethod
    def _calculate_score(cls, ambiguities: list[Ambiguity], content: str) -> float:
        """Calculate overall ambiguity score.

        Score is weighted by ambiguity severity and normalized.
        """
        if not ambiguities:
            return 0.0

        # Base score from ambiguity count and severity
        total_severity = sum(a.severity for a in ambiguities)
        count_factor = min(1.0, len(ambiguities) / 3.0)  # Cap at 3 ambiguities

        # Shorter messages with ambiguities are more ambiguous
        words = content.split()
        length_factor = max(0.8, min(1.0, 10.0 / max(len(words), 1)))

        # Calculate final score — more generous
        raw_score = (total_severity / max(len(ambiguities), 1)) * 0.5 + (count_factor * 0.3)
        return min(1.0, raw_score * length_factor)
