"""Engineering Discovery Engine — Requirement Extraction.

Extracts structured requirements from natural language engineering requests.
Classifies requirements by type, priority, and source.
"""

import re
import logging
from dataclasses import dataclass, field
from discovery.domains import DomainRegistry, Domain as DomainType

logger = logging.getLogger("aic.discovery.requirements")


@dataclass
class Requirement:
    """A structured engineering requirement."""

    id: str
    type: str  # functional, non_functional, constraint, assumption, dependency
    description: str
    priority: str = "should_have"  # must_have, should_have, nice_to_have
    source: str = "user_stated"  # user_stated, inferred, clarified
    domain_field: str = ""  # maps to domain mandatory field if applicable


@dataclass
class ExtractionResult:
    """Result of requirement extraction."""

    requirements: list[Requirement] = field(default_factory=list)
    functional: list[Requirement] = field(default_factory=list)
    non_functional: list[Requirement] = field(default_factory=list)
    constraints: list[Requirement] = field(default_factory=list)
    assumptions: list[Requirement] = field(default_factory=list)
    dependencies: list[Requirement] = field(default_factory=list)
    acceptance_criteria: list[Requirement] = field(default_factory=list)
    covered_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)


# Patterns for extracting different requirement types
FUNCTIONAL_PATTERNS = [
    (r"\b(add|create|build|implement|develop)\s+(.+?)(?:\.|,|$)", "functional"),
    (r"\b(fix|resolve|patch|repair)\s+(.+?)(?:\.|,|$)", "functional"),
    (r"\b(feature|capability|function)\s+(.+?)(?:\.|,|$)", "functional"),
]

NON_FUNCTIONAL_PATTERNS = [
    (r"\b(performance|speed|latency|fast|slow)\b", "performance"),
    (r"\b(security|secure|encrypt|auth|permission)\b", "security"),
    (r"\b(usability|user.friendly|intuitive|accessible)\b", "usability"),
    (r"\b(reliable|availability|uptime|fault.tolerant)\b", "reliability"),
    (r"\b(maintainable|clean|readable|modular)\b", "maintainability"),
]

CONSTRAINT_PATTERNS = [
    (r"\b(must|shall|required|mandatory|necessary)\b", "constraint"),
    (r"\b(cannot|must not|shall not|forbidden|prohibited)\b", "constraint"),
    (r"\b(limited to|restricted to|only)\b", "constraint"),
    (r"\b(budget|cost|time|deadline)\b", "constraint"),
]

ASSUMPTION_PATTERNS = [
    (r"\b(assuming|assume|suppose|given that)\b", "assumption"),
    (r"\b(we have|there is|existing)\b", "assumption"),
]

DEPENDENCY_PATTERNS = [
    (r"\b(requires|needs|depends on|using|with)\b", "dependency"),
    (r"\b(library|package|module|service|api|database)\b", "dependency"),
]

ACCEPTANCE_PATTERNS = [
    (r"\b(should|must|will|shall)\s+(.+?)(?:\.|,|$)", "acceptance"),
    (r"\b(done when|complete when|success when|verified by)\b", "acceptance"),
    (r"\b(test|verify|validate|check)\b", "acceptance"),
]


class RequirementExtractor:
    """Extracts structured requirements from natural language."""

    @classmethod
    def extract(
        cls,
        content: str,
        history: list | None = None,
        domain: str = "feature",
    ) -> ExtractionResult:
        """Extract requirements from user message.

        Args:
            content: User message content
            history: Conversation history for context
            domain: Engineering domain for field mapping

        Returns:
            ExtractionResult with categorized requirements
        """
        if not content:
            return ExtractionResult()

        lower = content.lower().strip()

        # Build full corpus from history
        corpus_parts = [content]
        if history:
            for msg in history:
                if isinstance(msg, dict) and msg.get("content"):
                    corpus_parts.append(msg["content"])
                elif hasattr(msg, "content") and msg.content:
                    corpus_parts.append(msg.content)
        full_corpus = " ".join(corpus_parts).lower()

        # Extract requirements by type
        functional = cls._extract_functional(lower)
        non_functional = cls._extract_non_functional(lower)
        constraints = cls._extract_constraints(lower)
        assumptions = cls._extract_assumptions(lower)
        dependencies = cls._extract_dependencies(lower)
        acceptance = cls._extract_acceptance(lower)

        # Map to domain mandatory fields
        domain_obj = DomainRegistry.get(domain)
        covered_fields, missing_fields = cls._map_to_domain(
            functional + non_functional + constraints + acceptance,
            domain_obj,
            full_corpus,
        )

        # Deduplicate requirements
        functional = cls._deduplicate(functional)
        non_functional = cls._deduplicate(non_functional)
        constraints = cls._deduplicate(constraints)
        assumptions = cls._deduplicate(assumptions)
        dependencies = cls._deduplicate(dependencies)
        acceptance = cls._deduplicate(acceptance)

        # Assign IDs
        all_requirements = functional + non_functional + constraints + assumptions + dependencies + acceptance
        for i, req in enumerate(all_requirements, 1):
            req.id = f"REQ-{i:03d}"

        return ExtractionResult(
            requirements=all_requirements,
            functional=functional,
            non_functional=non_functional,
            constraints=constraints,
            assumptions=assumptions,
            dependencies=dependencies,
            acceptance_criteria=acceptance,
            covered_fields=covered_fields,
            missing_fields=missing_fields,
        )

    @classmethod
    def _extract_functional(cls, text: str) -> list[Requirement]:
        """Extract functional requirements."""
        requirements = []

        for pattern_str, req_type in FUNCTIONAL_PATTERNS:
            for match in re.finditer(pattern_str, text, re.I):
                description = match.group(0).strip()
                if len(description) > 10:  # Skip very short matches
                    requirements.append(Requirement(
                        id="",
                        type="functional",
                        description=description,
                        priority="must_have",
                        source="user_stated",
                    ))

        return requirements

    @classmethod
    def _extract_non_functional(cls, text: str) -> list[Requirement]:
        """Extract non-functional requirements."""
        requirements = []

        for pattern_str, category in NON_FUNCTIONAL_PATTERNS:
            if re.search(pattern_str, text, re.I):
                requirements.append(Requirement(
                    id="",
                    type="non_functional",
                    description=f"{category.title()} requirement detected",
                    priority="should_have",
                    source="inferred",
                ))

        return requirements

    @classmethod
    def _extract_constraints(cls, text: str) -> list[Requirement]:
        """Extract constraints."""
        requirements = []

        for pattern_str, req_type in CONSTRAINT_PATTERNS:
            if re.search(pattern_str, text, re.I):
                requirements.append(Requirement(
                    id="",
                    type="constraint",
                    description=f"Constraint detected: {pattern_str}",
                    priority="must_have",
                    source="user_stated",
                ))

        return requirements

    @classmethod
    def _extract_assumptions(cls, text: str) -> list[Requirement]:
        """Extract assumptions."""
        requirements = []

        for pattern_str, req_type in ASSUMPTION_PATTERNS:
            if re.search(pattern_str, text, re.I):
                requirements.append(Requirement(
                    id="",
                    type="assumption",
                    description=f"Assumption detected: {pattern_str}",
                    priority="should_have",
                    source="inferred",
                ))

        return requirements

    @classmethod
    def _extract_dependencies(cls, text: str) -> list[Requirement]:
        """Extract dependencies."""
        requirements = []

        for pattern_str, req_type in DEPENDENCY_PATTERNS:
            if re.search(pattern_str, text, re.I):
                requirements.append(Requirement(
                    id="",
                    type="dependency",
                    description=f"Dependency detected: {pattern_str}",
                    priority="should_have",
                    source="inferred",
                ))

        return requirements

    @classmethod
    def _extract_acceptance(cls, text: str) -> list[Requirement]:
        """Extract acceptance criteria."""
        requirements = []

        for pattern_str, req_type in ACCEPTANCE_PATTERNS:
            for match in re.finditer(pattern_str, text, re.I):
                description = match.group(0).strip()
                if len(description) > 10:
                    requirements.append(Requirement(
                        id="",
                        type="acceptance",
                        description=description,
                        priority="must_have",
                        source="user_stated",
                    ))

        return requirements

    @classmethod
    def _map_to_domain(
        cls,
        requirements: list[Requirement],
        domain_obj: DomainType | None,
        corpus: str,
    ) -> tuple[list[str], list[str]]:
        """Map requirements to domain mandatory fields.

        Returns (covered_fields, missing_fields).
        """
        if not domain_obj:
            return [], []

        covered = []
        missing = []

        for field in domain_obj.mandatory_fields:
            if not field.required:
                continue

            # Check if any requirement covers this field
            field_covered = False

            # Check detection pattern against corpus
            if field.detection_pattern:
                if re.search(field.detection_pattern, corpus, re.I):
                    field_covered = True

            # Check if any requirement mentions this field
            for req in requirements:
                if field.name.lower() in req.description.lower():
                    field_covered = True
                    req.domain_field = field.name
                    break

            if field_covered:
                covered.append(field.name)
            else:
                missing.append(field.name)

        return covered, missing

    @classmethod
    def _deduplicate(cls, requirements: list[Requirement]) -> list[Requirement]:
        """Remove duplicate requirements."""
        seen = set()
        unique = []

        for req in requirements:
            key = req.description.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(req)

        return unique
