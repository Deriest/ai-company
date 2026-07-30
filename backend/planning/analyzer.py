"""Planning Engine — Brief Analyzer.

Analyzes Engineering Briefs to extract planning-relevant information.
"""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("aic.planning.analyzer")


@dataclass
class BriefAnalysis:
    """Result of analyzing an Engineering Brief."""

    complexity: str = "medium"  # low, medium, high, very_high
    scope_size: str = "medium"  # small, medium, large, very_large
    technology_stack: list[str] = field(default_factory=list)
    affected_components: list[str] = field(default_factory=list)
    requires_database_changes: bool = False
    requires_ui_changes: bool = False
    requires_api_changes: bool = False
    requires_infrastructure_changes: bool = False
    estimated_complexity_score: float = 0.5  # 0.0 to 1.0
    key_requirements: list[str] = field(default_factory=list)
    technical_challenges: list[str] = field(default_factory=list)


# Complexity indicators
COMPLEXITY_INDICATORS = {
    "low": [
        r"\b(fix|patch|update|change|rename|move|copy)\b",
        r"\b(simple|small|minor|quick)\b",
    ],
    "medium": [
        r"\b(add|create|implement|build)\b",
        r"\b(feature|component|module|endpoint)\b",
    ],
    "high": [
        r"\b(refactor|redesign|migrate|rewrite)\b",
        r"\b(complex|significant|major|large)\b",
    ],
    "very_high": [
        r"\b(architecture|system|platform|framework)\b",
        r"\b(from scratch|complete|entire|full)\b",
    ],
}

# Technology patterns
TECHNOLOGY_PATTERNS = {
    "python": r"\b(python|fastapi|django|flask|sqlalchemy|pytest)\b",
    "javascript": r"\b(javascript|node|react|vue|angular|typescript)\b",
    "database": r"\b(postgres|mysql|sqlite|redis|mongodb|sql)\b",
    "docker": r"\b(docker|container|kubernetes|k8s)\b",
    "api": r"\b(api|rest|graphql|endpoint|route)\b",
    "frontend": r"\b(ui|css|html|tailwind|bootstrap|component)\b",
    "testing": r"\b(test|pytest|jest|coverage|integration)\b",
    "security": r"\b(auth|jwt|token|encrypt|hash|permission)\b",
}


class BriefAnalyzer:
    """Analyzes Engineering Briefs for planning purposes."""

    @classmethod
    def analyze(cls, brief_data: dict) -> BriefAnalysis:
        """Analyze an Engineering Brief.

        Args:
            brief_data: Brief data dictionary

        Returns:
            BriefAnalysis with extracted information
        """
        analysis = BriefAnalysis()

        # Extract text for analysis
        text_parts = []
        if brief_data.get("engineering_goal"):
            text_parts.append(brief_data["engineering_goal"])
        if brief_data.get("user_intent"):
            text_parts.append(brief_data["user_intent"])

        # Include functional requirements
        for req in brief_data.get("functional_requirements", []):
            if isinstance(req, dict) and req.get("description"):
                text_parts.append(req["description"])

        full_text = " ".join(text_parts).lower()

        # Analyze complexity
        analysis.complexity = cls._analyze_complexity(full_text)
        analysis.estimated_complexity_score = cls._complexity_score(analysis.complexity)

        # Analyze scope
        analysis.scope_size = cls._analyze_scope(full_text, brief_data)

        # Detect technologies
        analysis.technology_stack = cls._detect_technologies(full_text)

        # Detect affected components
        analysis.affected_components = cls._detect_components(full_text)

        # Detect change types
        analysis.requires_database_changes = bool(
            re.search(r"\b(database|sql|migration|schema|column|table|index)\b", full_text)
        )
        analysis.requires_ui_changes = bool(
            re.search(r"\b(ui|css|component|page|form|button|modal|dashboard)\b", full_text)
        )
        analysis.requires_api_changes = bool(
            re.search(r"\b(api|endpoint|route|controller|handler)\b", full_text)
        )
        analysis.requires_infrastructure_changes = bool(
            re.search(r"\b(docker|deploy|ci.?cd|pipeline|server|nginx)\b", full_text)
        )

        # Extract key requirements
        analysis.key_requirements = cls._extract_key_requirements(brief_data)

        # Identify technical challenges
        analysis.technical_challenges = cls._identify_challenges(full_text, analysis)

        return analysis

    @classmethod
    def _analyze_complexity(cls, text: str) -> str:
        """Determine complexity level."""
        scores = {"low": 0, "medium": 0, "high": 0, "very_high": 0}

        for level, patterns in COMPLEXITY_INDICATORS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.I):
                    scores[level] += 1

        # Return highest scoring level
        if scores["very_high"] > 0:
            return "very_high"
        elif scores["high"] > 0:
            return "high"
        elif scores["medium"] > 0:
            return "medium"
        return "low"

    @classmethod
    def _complexity_score(cls, complexity: str) -> float:
        """Convert complexity to numeric score."""
        return {"low": 0.25, "medium": 0.5, "high": 0.75, "very_high": 1.0}.get(complexity, 0.5)

    @classmethod
    def _analyze_scope(cls, text: str, brief_data: dict) -> str:
        """Determine scope size."""
        # Count requirements
        req_count = len(brief_data.get("functional_requirements", []))

        # Count scope items
        scope = brief_data.get("scope", {})
        in_scope_count = len(scope.get("in_scope", []))

        total_items = req_count + in_scope_count

        if total_items <= 2:
            return "small"
        elif total_items <= 5:
            return "medium"
        elif total_items <= 10:
            return "large"
        return "very_large"

    @classmethod
    def _detect_technologies(cls, text: str) -> list[str]:
        """Detect mentioned technologies."""
        technologies = []
        for tech, pattern in TECHNOLOGY_PATTERNS.items():
            if re.search(pattern, text, re.I):
                technologies.append(tech)
        return technologies

    @classmethod
    def _detect_components(cls, text: str) -> list[str]:
        """Detect affected components."""
        components = []
        component_patterns = [
            (r"\b(api|endpoint|route)\b", "api"),
            (r"\b(ui|frontend|component)\b", "frontend"),
            (r"\b(database|db|schema)\b", "database"),
            (r"\b(auth|authentication)\b", "auth"),
            (r"\b(worker|executor)\b", "worker"),
            (r"\b(service|microservice)\b", "service"),
            (r"\b(middleware|handler)\b", "middleware"),
        ]
        for pattern, component in component_patterns:
            if re.search(pattern, text, re.I):
                components.append(component)
        return components

    @classmethod
    def _extract_key_requirements(cls, brief_data: dict) -> list[str]:
        """Extract key requirements from brief."""
        requirements = []
        for req in brief_data.get("functional_requirements", []):
            if isinstance(req, dict) and req.get("description"):
                requirements.append(req["description"][:100])
        return requirements[:10]  # Limit to 10

    @classmethod
    def _identify_challenges(cls, text: str, analysis: BriefAnalysis) -> list[str]:
        """Identify potential technical challenges."""
        challenges = []

        if analysis.requires_database_changes:
            challenges.append("Database schema changes may require migration")
        if analysis.requires_ui_changes and analysis.requires_api_changes:
            challenges.append("Full-stack changes require coordination")
        if analysis.complexity in ("high", "very_high"):
            challenges.append("High complexity requires careful architecture")
        if len(analysis.technology_stack) > 3:
            challenges.append("Multiple technologies increase integration risk")

        return challenges
