# AIC Agents Module — Technical Codemap

**Location**: `/backend/agents/`  
**Last Updated**: 2026-08-10

---

## 1. Responsibility

This module implements the **canonical agent registry and context assembly system** for the AI Software Company platform. It serves as the **single source of truth** for defining, organizing, and orchestrating 15 specialized LLM-powered workers (called "agents").

### Core Functions

- **Agent Registry**: Centralized data-driven definitions of all agents using Python `@dataclass` structures (`AgentIdentity`, `AgentSoul`, `ToolPermissions`, `ModelPolicy`, `HeartbeatPolicy`, `WorkerTuningPolicy`)
- **Context Assembly**: Builds runtime system prompts by combining agent soul definitions with phase-specific instructions, tool permissions, task context, worker handoffs, project memory, and adaptive tuning policies
- **Model Routing**: Provides per-agent LLM configuration (tier-based temperature, timeout, max_retries) via `get_model_config()`
- **Query Interface**: Filters agents by department, phase, or ID via helper functions (`get_agent()`, `get_agents_by_department()`, `get_agents_by_phase()`)

### Organizational Structure

Agents are organized into four departments:

| Department | Agents | Primary FSM Phase |
|------------|--------|-------------------|
| **Leadership** | Hermes (Dispatcher), Rex (Governor) | Global / Closeout |
| **Product** | Aria (PM), Sage (Researcher), Luna (Designer), Echo (Documentation) | Investigate / Planning / Closeout |
| **Engineering** | Atlas (Architect), Hugo (Backend), Leo (Frontend), Eve (QA), Pulse (Performance) | Planning / Implementation / Verification |
| **Platform** | Nova (Database), Nexus (Integration), Flint (Infrastructure), Sentinel (Security) | Planning / Verification |

---

## 2. Design Patterns

### Pattern: Repository (Registry Pattern)

The `AGENT_REGISTRY` dict acts as a **lookup table** that replaces scattered hardcoded agent definitions previously located in:
- `backend/canonical_workforce.py` (identity fields)
- `workers/base.py` (SYSTEM_PROMPT blocks)
- `workflow/fsm.py` (PHASE_WORKERS routing maps)

**Implementation**: The `_register()` function populates a module-level dictionary keyed by agent ID, enabling O(1) lookups via `AGENT_REGISTRY[agent_id]`.

### Pattern: Configuration Object (Data Class Composition)

Each `AgentDefinition` is composed from atomic data classes:
- `AgentIdentity`: Static metadata (id, name, role, tier, department, phase, personality)
- `AgentSoul`: Behavioral DNA (core_purpose, engineering_philosophy, quality_bar, risk_philosophy, evidence_standards, collaboration_style, escalation_policy, anti_patterns, system_prompt)
- `ToolPermissions`: Access control (allowed, restricted, prohibited lists)
- `ModelPolicy`: LLM hyperparameters (tier, temperature, timeout, max_retries)
- `HeartbeatPolicy`: Proactive behavior config (enabled, interval_seconds, actions)
- `WorkerTuningPolicy`: Execution tuning (planning_depth, verification_frequency, checkpoint_strategy, max_parallel_workers, prompt_detail)

### Pattern: Template Method

The `assemble_system_prompt()` function builds context using a structured pipeline:
1. Agent's base `system_prompt` (from `AgentSoul`)
2. Operating constraints block (quality bar, evidence standards, anti-patterns)
3. Engineering philosophy blocks (risk, collaboration)
4. Phase-specific hints dictionary lookup
5. Tool permissions summary
6. Task context injection
7. Prior worker handoffs (last 3 phases)
8. Task-relevant skills mapping (`SKILL_MAP`)
9. Durable project memory injection
10. Adaptive runtime policy OR worker tuning policy defaults
11. Lessons learned from company history
12. Project structure context

This template ensures **contextual consistency** across all LLM calls while allowing dynamic substitution of phase-specific instructions.

### Pattern: Strategy Selector (Phase Hints)

The `phase_hints` dict provides phase-specific behavioral guidance that overrides generic instructions based on current FSM phase:
- `discovery`: Clarification and requirement analysis
- `investigate`: Research and specification production
- `planning`: Architecture design with mandatory subtask decomposition
- `implementation`: Actual code writing with error handling
- `verification`: Deterministic checks (file presence, syntax, tests)
- `closeout`: Deliverable finalization and documentation review

### Pattern: Flyweight (Shared Data)

Agent definitions are shared read-only structures loaded once at import time. Each agent instance references shared constants like `_ANTI_SLOP_BLOCK` (writing style constraints) rather than duplicating them inline.

### Pattern: Command Injection (Runtime Policy)

Adaptive runtime policies (`task_context.get("adaptive_runtime")`) inject execution strategies at runtime:
- Context classification
- Planning depth selection
- Verification frequency
- Checkpoint strategy
- Max parallel workers

This enables dynamic tuning without modifying static agent definitions.

### Pattern: Observer (Heartbeat Policy)

Only Hermes has `HeartbeatPolicy.enabled=True` with 60-second intervals triggering `check_stale_tasks` and `check_blocked_tasks`. Other agents use default disabled heartbeats, representing an **observer pattern** where only specific agents actively poll state changes.

---

## 3. Data & Control Flow

### Entry Points

1. **Module Import**: `from agents.registry import AGENT_REGISTRY`
   - All 15 agents registered at import via `_register()` calls
   - `assert len(AGENT_REGISTRY) == 15` validates completeness

2. **Direct API Usage**:
   ```python
   from agents.registry import get_agent
   agent = get_agent("hermes")  # Returns AgentDefinition or None
   
   from agents.registry import get_all_agents
   agents = get_all_agents()  # Returns list[AgentDefinition]
   
   from agents.registry import get_agents_by_department
   product_agents = get_agents_by_department("Product")  # Filtered list
   ```

3. **Context Assembly Call**:
   ```python
   from agents.context_assembly import assemble_system_prompt, get_model_config
   prompt = assemble_system_prompt(
       agent_id="backend",
       task_context={"title": "...", "type": "feature"},
       phase="Implementation"
   )
   config = get_model_config("backend")
   ```

### Internal Processing Flow

```mermaid
graph LR
    A[Task Request] --> B{Agent Resolution}
    B -->|ID| C[AGENT_REGISTRY[id]]
    B -->|Department| D[get_agents_by_department()]
    B -->|Phase| E[get_agents_by_phase()]
    C --> F[extract .soul.system_prompt]
    C --> G[extract .tools.allowed/prohibited]
    C --> H[extract .model.tier/timeout/temperature]
    C --> I[extract .tuning.*]
    
    J[task_context] --> K[assemble_system_prompt]
    K --> L[Inject operating constraints]
    K --> M[Inject phase hints]
    K --> N[Inject prior handoffs]
    K --> O[Inject SKILL_MAP rules]
    K --> P[Inject memories]
    K --> Q[Inject adaptive_runtime OR tuning policy]
    K --> R[Inject lessons_learned]
    K --> S[Inject project_context]
    
    T[Output System Prompt] --> U[LLM Worker Invocation]
    
    H --> V[get_model_config]
    V --> W[LLM provider config dict]
    W --> U
```

### Data Dependencies

| Source | Consumed By | Purpose |
|--------|-------------|---------|
| `task_context` | `assemble_system_prompt()` | Task title, description, type, skills, handoffs, memories, lessons_learned, adaptive_runtime |
| `phase` | `assemble_system_prompt()` | Selects phase_hint from `phase_hints` dict |
| `project_context` | `assemble_system_prompt()` | Optional project metadata (memory notes, structural info) |
| `registry.AgentSoul` | `assemble_system_prompt()` | Core behavioral DNA (purpose, philosophy, quality bar) |
| `registry.ToolPermissions` | `assemble_system_prompt()` | Allowed/restricted/prohibited tool lists |
| `registry.ModelPolicy` | `get_model_config()` | Temperature, timeout, max_retries, tier |

### Output Structures

**System Prompt String**: Concatenated markdown-formatted blocks separated by `--- SEPARATOR ---`:
```
[SYS_PROMPT]\n
--- OPERATING CONSTRAINTS ---\nQuality bar: ...\nEvidence standards: ...\nAnti-patterns: ...\n
--- ENGINEERING PHILOSOPHY ---\n...\n
--- RISK PHILOSOPHY ---\n...\n
--- COLLABORATION & ESCALATION ---\n...\n
--- CURRENT PHASE: {PHASE} ---\n{PHASE_HINT}\n
--- ALLOWED TOOLS ---\n...\n
--- TASK ---\nTitle: ...\nDescription: ...\nExecution Level: ...\n
--- PRIOR WORKER HANDOFFS ---\n...[-3 handoff snippets...]\n
--- TASK-RELEVANT SKILLS ---\n• skill1\n• skill2\n...
--- DURABLE PROJECT MEMORY ---\n...\n
--- ADAPTIVE RUNTIME POLICY ---\n...\n(or)\n--- WORKING MODE ---\n...\n
--- LESSONS LEARNED ---\n...\n
--- PROJECT CONTEXT ---\n...
```

**Model Config Dict**: 
```python
{
    "tier": "thinker"|"crafter"|"sprinter"|"vision",
    "temperature": 0.1–0.4,
    "timeout": 60–120,
    "max_retries": 1
}
```

### Exit Points

1. **System Prompt → LLM Provider**: Full concatenated prompt string sent to model inference endpoint
2. **Model Config → Provider Router**: Dict used to select model provider (e.g., OpenAI, Anthropic) and route inference request
3. **Agent Definition → Runtime**: Used by `workers/base.py` during worker instantiation to set `SYSTEM_PROMPT` dynamically

---

## 4. Integration Points

### Producer Dependencies (Consumers of This Module)

| Consumer | Import | Usage |
|----------|--------|-------|
| `backend/canonical_workforce.py` | `from agents.registry import get_agent` | Replaces old hardcoded identity fields with centralized registry queries |
| `workers/base.py` | `from agents.registry import get_agent` | Dynamically fetches `system_prompt` at worker initialization time |
| `workflow/fsm.py` | `from agents.registry import get_agents_by_phase` | Maps FSM phases to appropriate worker candidates during task routing |
| `runtime/worker_executor.py` | `from agents.context_assembly import assemble_system_prompt, get_model_config` | Builds runtime context before each LLM call; selects model config per agent |
| `task/orchestration.py` | `from agents.registry import get_agent` | Validates agent existence before dispatching work |
| `heartbeat/service.py` | `from agents.registry import get_agents_by_department` | Checks heartbeat-enabled agents for stale/blocked tasks |

### External Dependencies

| Dependency | Type | Version | Purpose |
|------------|------|---------|---------|
| `typing` | stdlib | N/A | Type hints (`Optional`, `dict`, `list`, `str`) |
| `dataclasses` | stdlib | N/A | Data class decorators (`@dataclass`, `field`) |

### Anti-Patterns Block Injection

All writing-oriented agents (documentation, pm, rex, research, qa) share the `_ANTI_SLOP_BLOCK` constant:
- Prevents LLM clichés ("delve", "crucial", "pivotal", "seamless", "groundbreaking")
- Enforces active voice, simple words, sentence length variation
- Injected verbatim into their system prompts via `+ _ANTI_SLOP_BLOCK`

### File Annotations

| File | Lines | Description |
|------|-------|-------------|
| `registry.py` | 726 | Complete agent definitions, registry infrastructure, helper functions |
| `context_assembly.py` | 157 | Runtime context builder, phase hints, SKILL_MAP, model config extractor |

### Known Issues

1. **Assertion Mismatch**: Line 726 asserts `len(AGENT_REGISTRY) == 15` but comment header states "16 canonical agent definitions" — actual count is 15 (verified via docstring).
2. **Missing Integration Tests**: No test files found in this directory (excluded patterns match `**/*.test.py`).
3. **Hardcoded Phase List**: `phase_hints` dict in `context_asassembly.py` must be updated whenever new FSM phases are added.

---

## Appendix: Agent Quick Reference

| ID | Name | Role | Tier | Department | Skills |
|----|------|------|------|------------|--------|
| hermes | Hermes | Dispatcher | thinker | Leadership | discovery, requirements, delegation, orchestration |
| rex | Rex | Governor | sprinter | Leadership | governance, closeout, compliance, review, taste |
| pm | Aria | Product Manager | thinker | Product | discovery, requirements, user_stories, acceptance_criteria, taste |
| research | Sage | Researcher | thinker | Product | research, analysis, trade_off_evaluation, documentation_review, taste |
| designer | Luna | Designer | crafter | Product | ui_design, ux_design, accessibility, design_system |
| documentation | Echo | Documentation Engineer | crafter | Product | documentation, readme_generation, api_docs, user_guides, taste |
| architect | Atlas | Architect | thinker | Engineering | architecture, system_design, decomposition, trade_off_analysis |
| backend | Hugo | Backend Engineer | crafter | Engineering | backend, api_design, database, error_handling, testing |
| frontend | Leo | Frontend Engineer | crafter | Engineering | frontend, react, ui_implementation, accessibility, state_management |
| qa | Eve | QA Engineer | sprinter | Engineering | qa, testing, verification, syntax_checking, requirements_validation, code_review, taste |
| performance | Pulse | Performance Engineer | sprinter | Engineering | performance, profiling, optimization, benchmarking |
| database | Nova | Data Engineer | crafter | Platform | database, schema_design, sql, data_modeling, migrations |
| nexus | Nexus | Integration Engineer | crafter | Platform | integration, interface_design, contract_testing, system_testing |
| flint | Flint | Infrastructure Engineer | crafter | Platform | infrastructure, ci_cd, deployment, docker, monitoring |
| security | Sentinel | Security Engineer | crafter | Platform | security, threat_modeling, vulnerability_analysis, input_validation, secret_detection |
