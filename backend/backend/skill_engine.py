"""AIC Platform — First-Class Skill Ecosystem Engine.

Manages skill registry, worker assignments, toggle state, and dynamic task resolution:
- Built-in skills automatically seeded on startup
- Skills assigned to target worker types (e.g. backend, frontend, qa, security)
- Dynamic task-relevant skill resolver injects ONLY relevant enabled skills per worker
- Prevents context pollution by isolating worker skill sets
"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import SkillEntry

logger = logging.getLogger("aic.skills")

BUILTIN_SKILLS = [
    {
        "skill_id": "taste",
        "name": "Anti-AI-Slop Taste",
        "description": "Writing standard that eliminates AI slop patterns. Output must sound human, specific, and direct.",
        "category": "quality",
        "instructions": (
            "WRITING STANDARD (anti-slop):\n"
            "NEVER use: delve, crucial, pivotal, comprehensive, testament, underscore, vibrant, seamless, "
            "groundbreaking, 'It's important to note', 'I'd be happy to', 'Let's dive in', "
            "'Here's what you need to know', 'In conclusion', 'The future looks bright', "
            "'at the end of the day', 'when it comes to', 'moving forward', 'circle back', "
            "'game-changer', 'In today's fast-paced world'.\n"
            "NEVER: em-dash overuse, forced rule-of-three, elegant variation (synonym swapping), "
            "'-ing' superficial openers ('Highlighting...', 'Underscoring...'), Title Case headings, "
            "emoji in headings, curly quotes.\n"
            "AVOID: 'not only... but also', 'It's not just X; it's Y', ad-copy sentences "
            "('no guessing', 'it just works'), rhetorical questions immediately answered, mic-drop closings.\n"
            "MUST: vary sentence length, use specifics (numbers/names/context), state opinions clearly, "
            "prefer simple words ('is'/'has' over 'serves as'), active voice."
        ),
        "assigned_workers": ["documentation", "rex", "pm", "qa", "coding", "research"],
    },
    {
        "skill_id": "api-completeness-audit",
        "name": "API Completeness Audit",
        "description": "Audit backend/frontend API completeness for commercial operations.",
        "category": "software-development",
        "instructions": "Audit all REST endpoints for request validation, status codes, error responses, and authorization checks.",
        "assigned_workers": ["backend", "qa"],
    },
    {
        "skill_id": "systematic-debugging",
        "name": "Systematic Debugging",
        "description": "4-phase root cause debugging — understand bugs before fixing.",
        "category": "software-development",
        "instructions": "Phase 1: Understand problem & reproduce. Phase 2: Trace root cause in source files. Phase 3: Implement minimal fix. Phase 4: Verify with regression tests.",
        "assigned_workers": ["debugger", "backend", "frontend"],
    },
    {
        "skill_id": "test-driven-development",
        "name": "Test-Driven Development",
        "description": "TDD: enforce RED-GREEN-REFACTOR, write unit tests alongside code.",
        "category": "software-development",
        "instructions": "Write clean, isolated unit/integration tests covering core business logic and edge cases.",
        "assigned_workers": ["qa", "backend", "coding"],
    },
    {
        "skill_id": "simplify-code",
        "name": "Simplify & Refactor Code",
        "description": "Parallel cleanup of recent code changes, eliminate boilerplate.",
        "category": "software-development",
        "instructions": "Enforce PonyTail simplicity: fewest lines possible, stdlib over extra dependencies, zero unrequested boilerplate.",
        "assigned_workers": ["backend", "frontend", "architect"],
    },
    {
        "skill_id": "security-audit",
        "name": "Security Audit & Vulnerability Scanning",
        "description": "Audit authentication, authorization, secret handling, and input sanitization.",
        "category": "security",
        "instructions": "Check for SQL injection, path traversal, hardcoded secrets, unsafe shell calls, and missing auth checks.",
        "assigned_workers": ["security", "backend"],
    },
    {
        "skill_id": "server-health-monitoring",
        "name": "Server & Container Health Monitoring",
        "description": "Monitor system health, CPU/RAM usage, process readiness.",
        "category": "devops",
        "instructions": "Verify process readiness, port availability, database connections, and memory limits.",
        "assigned_workers": ["devops", "flint", "nexus"],
    },
]


async def seed_builtin_skills(session: AsyncSession):
    """Seed built-in skills into DB if not present."""
    for s in BUILTIN_SKILLS:
        res = await session.execute(select(SkillEntry).where(SkillEntry.skill_id == s["skill_id"]))
        existing = res.scalar_one_or_none()
        if not existing:
            entry = SkillEntry(
                skill_id=s["skill_id"],
                name=s["name"],
                description=s["description"],
                category=s["category"],
                source="built-in",
                instructions=s["instructions"],
                assigned_workers=s["assigned_workers"],
                is_enabled=True,
            )
            session.add(entry)
    await session.commit()


async def list_skills(session: AsyncSession, enabled_only: bool = False) -> list[dict]:
    """List all registered skills."""
    stmt = select(SkillEntry)
    if enabled_only:
        stmt = stmt.where(SkillEntry.is_enabled == True)
    res = await session.execute(stmt)
    entries = res.scalars().all()

    return [{
        "id": s.id,
        "skill_id": s.skill_id,
        "name": s.name,
        "description": s.description,
        "category": s.category,
        "source": s.source,
        "assigned_workers": s.assigned_workers or [],
        "is_enabled": s.is_enabled,
        "instructions": s.instructions,
    } for s in entries]


async def toggle_skill(session: AsyncSession, skill_id: str, is_enabled: bool) -> bool:
    """Enable or disable a skill by skill_id."""
    res = await session.execute(select(SkillEntry).where(SkillEntry.skill_id == skill_id))
    skill = res.scalar_one_or_none()
    if not skill:
        return False
    skill.is_enabled = is_enabled
    await session.commit()
    return True


async def assign_skill_workers(session: AsyncSession, skill_id: str, workers: list[str]) -> bool:
    """Update assigned worker types for a skill."""
    res = await session.execute(select(SkillEntry).where(SkillEntry.skill_id == skill_id))
    skill = res.scalar_one_or_none()
    if not skill:
        return False
    skill.assigned_workers = workers
    await session.commit()
    return True


async def resolve_skills_for_worker(session: AsyncSession, worker_type: str) -> list[str]:
    """Resolve active skill instruction strings assigned to a specific worker type."""
    res = await session.execute(
        select(SkillEntry).where(SkillEntry.is_enabled == True)
    )
    skills = res.scalars().all()
    matching = []
    for s in skills:
        assigned = s.assigned_workers or []
        if worker_type in assigned or "all" in assigned:
            matching.append(f"{s.name} ({s.skill_id}): {s.instructions}")
    return matching
