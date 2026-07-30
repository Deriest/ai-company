"""Engineering Discovery Engine — Domain Registry.

Domain-specific mandatory fields and readiness adjustments.
Each engineering domain requires different information for readiness.
"""

from dataclasses import dataclass, field


@dataclass
class DomainField:
    """A mandatory or optional field for an engineering domain."""

    name: str
    description: str
    required: bool = True
    detection_pattern: str = ""
    weight: float = 1.0


@dataclass
class Domain:
    """An engineering domain with its mandatory fields."""

    name: str
    description: str
    mandatory_fields: list[DomainField] = field(default_factory=list)
    optional_fields: list[DomainField] = field(default_factory=list)
    readiness_adjustment: float = 0.0


class DomainRegistry:
    """Registry of engineering domains and their mandatory fields.

    Domains determine what information is required for Engineering Readiness.
    """

    _domains: dict[str, Domain] = {}
    _initialized: bool = False

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Lazily initialize default domains."""
        if cls._initialized:
            return
        cls._register_default_domains()
        cls._initialized = True

    @classmethod
    def register(cls, domain: Domain) -> None:
        """Register a new domain.

        Args:
            domain: Domain to register
        """
        cls._ensure_initialized()
        cls._domains[domain.name] = domain

    @classmethod
    def get(cls, name: str) -> Domain | None:
        """Get a domain by name.

        Args:
            name: Domain name

        Returns:
            Domain if found, None otherwise.
        """
        cls._ensure_initialized()
        return cls._domains.get(name)

    @classmethod
    def get_all(cls) -> dict[str, Domain]:
        """Get all registered domains."""
        cls._ensure_initialized()
        return dict(cls._domains)

    @classmethod
    def get_names(cls) -> list[str]:
        """Get all domain names."""
        cls._ensure_initialized()
        return list(cls._domains.keys())

    @classmethod
    def get_mandatory_fields(cls, domain_name: str) -> list[DomainField]:
        """Get mandatory fields for a domain.

        Args:
            domain_name: Domain name

        Returns:
            List of mandatory fields. Empty if domain not found.
        """
        domain = cls.get(domain_name)
        if not domain:
            return []
        return [f for f in domain.mandatory_fields if f.required]

    @classmethod
    def _register_default_domains(cls) -> None:
        """Register the 14 default engineering domains."""

        cls._domains["ui"] = Domain(
            name="ui",
            description="Frontend or visual changes",
            mandatory_fields=[
                DomainField("component", "Component or screen name", True,
                           r"\b(component|screen|page|view|modal|dialog|panel)\b"),
                DomainField("visual_behaviour", "What the user sees", True,
                           r"\b(show|display|render|appear|visible|layout)\b"),
                DomainField("interaction", "What the user does", True,
                           r"\b(click|tap|hover|drag|scroll|submit|input)\b"),
                DomainField("responsive", "Mobile/tablet/desktop requirements", True,
                           r"\b(responsive|mobile|tablet|desktop|breakpoint)\b"),
                DomainField("design_system", "Design system reference", True,
                           r"\b(tailwind|material|bootstrap|antd|figma|design)\b"),
            ],
        )

        cls._domains["backend"] = Domain(
            name="backend",
            description="Backend API changes",
            mandatory_fields=[
                DomainField("endpoint", "Endpoint path and method", True,
                           r"\b(endpoint|route|api|GET|POST|PUT|DELETE|PATCH)\b"),
                DomainField("schema", "Request/response schema", True,
                           r"\b(schema|request|response|payload|body|param)\b"),
                DomainField("auth", "Authentication requirements", True,
                           r"\b(auth|token|jwt|bearer|permission|role)\b"),
                DomainField("error_handling", "Error handling behaviour", True,
                           r"\b(error|exception|404|500|validation|fail)\b"),
                DomainField("rate_limiting", "Rate limiting needs", True,
                           r"\b(rate|limit|throttle|quota)\b"),
            ],
        )

        cls._domains["bugfix"] = Domain(
            name="bugfix",
            description="Defect resolution",
            mandatory_fields=[
                DomainField("reproduction", "Reproduction steps", True,
                           r"\b(repro|steps|when|triggers|causes|happens)\b"),
                DomainField("expected_behaviour", "Expected vs actual behaviour", True,
                           r"\b(expected|should|actual|instead|wrong|correct)\b"),
                DomainField("affected_component", "Affected version/component", True,
                           r"\b(affects|component|module|page|endpoint)\b"),
                DomainField("severity", "Severity/priority", True,
                           r"\b(severity|priority|critical|high|medium|low|urgent)\b"),
                DomainField("regression_risk", "Regression risk", True,
                           r"\b(regression|side.effect|break|impact)\b"),
            ],
        )

        cls._domains["feature"] = Domain(
            name="feature",
            description="New capability or enhancement",
            mandatory_fields=[
                DomainField("user_story", "User story or intent", True,
                           r"\b(user|want|need|as a|so that|goal)\b"),
                DomainField("scope", "Scope boundaries", True,
                           r"\b(scope|include|exclude|boundary|limit)\b"),
                DomainField("acceptance", "Acceptance criteria", True,
                           r"\b(accept|criteria|done|complete|verify)\b"),
            ],
        )

        cls._domains["refactor"] = Domain(
            name="refactor",
            description="Code restructuring without behaviour change",
            mandatory_fields=[
                DomainField("target_module", "Target module(s)", True,
                           r"\b(module|file|class|function|component)\b"),
                DomainField("structure", "Current vs desired structure", True,
                           r"\b(extract|move|rename|split|merge|restructure)\b"),
                DomainField("behaviour_preservation", "Behaviour preservation requirement", True,
                           r"\b(same behaviour|no change|preserve|keep|maintain)\b"),
                DomainField("test_coverage", "Test coverage requirement", True,
                           r"\b(test|coverage|spec|verify)\b"),
            ],
        )

        cls._domains["docs"] = Domain(
            name="docs",
            description="Documentation creation or update",
            mandatory_fields=[
                DomainField("doc_type", "Document type", True,
                           r"\b(readme|api|guide|tutorial|manual|changelog)\b"),
                DomainField("audience", "Target audience", True,
                           r"\b(developer|user|admin|beginner|advanced)\b"),
                DomainField("scope", "Scope of coverage", True,
                           r"\b(cover|include|document|describe|explain)\b"),
            ],
        )

        cls._domains["test"] = Domain(
            name="test",
            description="Test creation or improvement",
            mandatory_fields=[
                DomainField("test_type", "Test type", True,
                           r"\b(unit|integration|e2e|end.to.end|smoke|regression)\b"),
                DomainField("coverage", "Target coverage", True,
                           r"\b(coverage|percent|target|aim)\b"),
                DomainField("framework", "Framework preference", True,
                           r"\b(pytest|jest|vitest|mocha|cypress|playwright)\b"),
            ],
        )

        cls._domains["infra"] = Domain(
            name="infra",
            description="Infrastructure or deployment",
            mandatory_fields=[
                DomainField("environment", "Environment", True,
                           r"\b(dev|staging|prod|production|local|cloud)\b"),
                DomainField("service_type", "Service type", True,
                           r"\b(docker|kubernetes|nginx|server|container|vm)\b"),
                DomainField("scaling", "Scaling requirements", True,
                           r"\b(scale|replicas|load|horizontal|vertical)\b"),
            ],
        )

        cls._domains["architecture"] = Domain(
            name="architecture",
            description="System-level design decisions",
            mandatory_fields=[
                DomainField("current_arch", "Current architecture", True,
                           r"\b(current|existing|monolith|microservice|layered)\b"),
                DomainField("proposed_arch", "Proposed architecture", True,
                           r"\b(proposed|new|target|design|split|migrate)\b"),
                DomainField("migration", "Migration strategy", True,
                           r"\b(migration|transition|phase|step|plan)\b"),
                DomainField("impact", "Impact analysis", True,
                           r"\b(impact|affect|change|break|modify)\b"),
            ],
        )

        cls._domains["security"] = Domain(
            name="security",
            description="Security hardening or audit",
            mandatory_fields=[
                DomainField("threat_model", "Threat model", True,
                           r"\b(threat|attack|vulnerability|exploit|risk)\b"),
                DomainField("vulnerability", "Vulnerability description", True,
                           r"\b(vulnerability|cve|injection|xss|csrf|auth.bypass)\b"),
                DomainField("mitigation", "Mitigation approach", True,
                           r"\b(mitigate|fix|patch|protect|secure|harden)\b"),
            ],
        )

        cls._domains["performance"] = Domain(
            name="performance",
            description="Performance optimisation",
            mandatory_fields=[
                DomainField("current_metric", "Current metric", True,
                           r"\b(current|slow|latency|response.time|memory|cpu)\b"),
                DomainField("target_metric", "Target metric", True,
                           r"\b(target|goal|improve|reduce|optimize|faster)\b"),
                DomainField("bottleneck", "Bottleneck identification", True,
                           r"\b(bottleneck|slow|hot.path|profiling|measure)\b"),
            ],
        )

        cls._domains["database"] = Domain(
            name="database",
            description="Schema or data changes",
            mandatory_fields=[
                DomainField("change_type", "Schema change type", True,
                           r"\b(migration|alter|create.table|add.column|index|schema)\b"),
                DomainField("migration_strategy", "Migration strategy", True,
                           r"\b(migration|migrate|rollback|forward|backward)\b"),
                DomainField("data_integrity", "Data integrity constraints", True,
                           r"\b(integrity|constraint|foreign.key|unique|not.null)\b"),
            ],
        )

        cls._domains["ai_llm"] = Domain(
            name="ai_llm",
            description="AI/LLM feature integration",
            mandatory_fields=[
                DomainField("model_provider", "Model/provider", True,
                           r"\b(openai|anthropic|llm|model|gpt|claude|embedding)\b"),
                DomainField("prompt_design", "Prompt/context design", True,
                           r"\b(prompt|context|system.prompt|instruction)\b"),
                DomainField("fallback", "Fallback behaviour", True,
                           r"\b(fallback|default|error|retry|timeout)\b"),
                DomainField("token_budget", "Token/cost constraints", True,
                           r"\b(token|cost|budget|limit|quota)\b"),
            ],
        )

        cls._domains["devops"] = Domain(
            name="devops",
            description="Operations and automation",
            mandatory_fields=[
                DomainField("automation_type", "Automation type", True,
                           r"\b(ci|cd|pipeline|workflow|automate|script)\b"),
                DomainField("trigger", "Trigger mechanism", True,
                           r"\b(trigger|schedule|webhook|cron|event|push)\b"),
                DomainField("environment", "Target environment", True,
                           r"\b(github.actions|gitlab.ci|jenkins|docker|cloud)\b"),
            ],
        )

        cls._domains["research"] = Domain(
            name="research",
            description="Investigation without implementation",
            mandatory_fields=[
                DomainField("question", "Research question", True,
                           r"\b(evaluate|compare|investigate|analyze|study|research)\b"),
                DomainField("scope", "Research scope", True,
                           r"\b(scope|focus|area|domain|technology)\b"),
                DomainField("output", "Expected output", True,
                           r"\b(report|summary|recommendation|finding)\b"),
            ],
        )
