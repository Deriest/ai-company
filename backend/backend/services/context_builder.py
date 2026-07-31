"""Auto-adaptive context management for workers.

Adjusts context size based on model capabilities:
- Large context models (100K+): full context (50 messages, 30 files, 150K tokens)
- Medium context models (32K): balanced context (16 messages, 15 files, 60K tokens)
- Small context models (8K): minimal context (5 messages, 5 files, 6K tokens)

Context structure:
1. System prompt (agent identity + skills + constraints)
2. Project overview (structure, key files)
3. Recent conversation (last N messages)
4. Tool results (from current execution)
5. Active task context (what we're working on)
"""
import os
import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("aic.context")


@dataclass(frozen=True)
class ContextPolicy:
    """Policy that governs context sizing for a model tier."""
    max_history: int
    max_files: int
    max_tokens: int
    response_tokens: int
    summarization: str
    retrieval_first: bool


CONTEXT_POLICIES: dict[str, ContextPolicy] = {
    "thinker": ContextPolicy(
        max_history=50,
        max_files=30,
        max_tokens=150_000,
        response_tokens=8_192,
        summarization="minimal",
        retrieval_first=False,
    ),
    "crafter": ContextPolicy(
        max_history=20,
        max_files=15,
        max_tokens=60_000,
        response_tokens=4_096,
        summarization="periodic",
        retrieval_first=True,
    ),
    "sprinter": ContextPolicy(
        max_history=5,
        max_files=5,
        max_tokens=6_000,
        response_tokens=2_048,
        summarization="aggressive",
        retrieval_first=True,
    ),
}


def get_context_policy(model_tier: str) -> ContextPolicy:
    """Get the context policy for a model tier. Falls back to crafter."""
    return CONTEXT_POLICIES.get(model_tier, CONTEXT_POLICIES["crafter"])


async def get_model_context_window(
    db: AsyncSession,
    provider_id: str,
    model_id: str,
) -> int | None:
    """Get the actual context window for a specific model from the provider registry.

    Returns the context_window from the provider_models table if found,
    otherwise None (caller should fall back to tier-based defaults).
    """
    from backend.models.schema import ProviderModel

    stmt = select(ProviderModel.context_window).where(
        ProviderModel.provider_id == provider_id,
        ProviderModel.model_id == model_id,
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    return row


def get_context_policy_for_window(context_window: int) -> ContextPolicy:
    """Derive a ContextPolicy from an actual model context window (in tokens).

    Reserves ~20% of the window for the response, then allocates the rest
    to history, files, and token budget.
    """
    response_tokens = min(max(context_window // 5, 2_048), 16_384)
    usable = context_window - response_tokens

    if context_window >= 200_000:
        return ContextPolicy(
            max_history=50,
            max_files=30,
            max_tokens=usable,
            response_tokens=response_tokens,
            summarization="minimal",
            retrieval_first=False,
        )
    elif context_window >= 64_000:
        return ContextPolicy(
            max_history=30,
            max_files=20,
            max_tokens=usable,
            response_tokens=response_tokens,
            summarization="periodic",
            retrieval_first=True,
        )
    elif context_window >= 32_000:
        return ContextPolicy(
            max_history=16,
            max_files=15,
            max_tokens=usable,
            response_tokens=response_tokens,
            summarization="periodic",
            retrieval_first=True,
        )
    else:
        return ContextPolicy(
            max_history=5,
            max_files=5,
            max_tokens=usable,
            response_tokens=response_tokens,
            summarization="aggressive",
            retrieval_first=True,
        )


@dataclass
class WorkerContext:
    """Context assembled for a worker's LLM call."""
    system_prompt: str = ""
    project_overview: str = ""
    recent_messages: list = field(default_factory=list)
    tool_results: list = field(default_factory=list)
    task_description: str = ""
    skills: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_messages(self, policy: Optional[ContextPolicy] = None, max_history: int = 20) -> tuple[list[dict], dict]:
        """Convert to LLM message format, using policy limits when provided.

        Returns ``(messages, metadata)`` where *metadata* includes an
        ``estimated_tokens`` count so callers can detect potential overflow
        before invoking the LLM.
        """
        messages = []
        history_limit = policy.max_history if policy else max_history
        tool_limit = 5 if policy and policy.max_history <= 10 else 10
        max_tokens_limit = policy.max_tokens if policy else 0

        # System prompt with all context baked in
        system_parts = [self.system_prompt]

        if self.project_overview:
            system_parts.append(f"\n\n## Project Context\n{self.project_overview}")

        if self.skills:
            skills_text = "\n".join(f"- {s}" for s in self.skills[:5])
            system_parts.append(f"\n\n## Skills\n{skills_text}")

        if self.task_description:
            system_parts.append(f"\n\n## Current Task\n{self.task_description}")

        if self.tool_results:
            tool_summary = "\n".join(
                f"- {r.get('tool', '?')}: {'✅' if r.get('success') else '❌'} {str(r.get('output', ''))[:200]}"
                for r in self.tool_results[-tool_limit:]
            )
            system_parts.append(f"\n\n## Recent Tool Results\n{tool_summary}")

        messages.append({"role": "system", "content": "\n".join(system_parts)})

        # Recent conversation history (limited by policy)
        for msg in self.recent_messages[-history_limit:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        # Conservative token estimation: ~4 chars per token with 1.3x safety buffer
        total_chars = sum(len(m.get("content", "")) for m in messages)
        estimated_tokens = int(total_chars // 4 * 1.3)

        # Token-budget trimming: drop oldest conversation messages (preserve system)
        # until estimated_tokens <= max_tokens_limit
        dropped_count = 0
        if max_tokens_limit > 0 and estimated_tokens > max_tokens_limit:
            # Keep system prompt (index 0), drop oldest non-system messages first
            for i in range(len(messages) - 1, 0, -1):
                if estimated_tokens <= max_tokens_limit:
                    break
                removed = messages.pop(i)
                dropped_count += 1
                total_chars = sum(len(m.get("content", "")) for m in messages)
                estimated_tokens = int(total_chars // 4 * 1.3)

        metadata = {
            "estimated_tokens": estimated_tokens,
            "message_count": len(messages),
            "max_history": history_limit,
            "max_tokens_budget": max_tokens_limit,
            "truncated": dropped_count > 0,
            "dropped_messages": dropped_count,
        }

        return messages, metadata


class ContextBuilder:
    """Build context for workers — simple and effective.
    
    For 200K context models:
    - System prompt: ~2-4K tokens
    - Project overview: ~5-10K tokens
    - Recent history: ~10-20K tokens
    - Tool results: ~5-10K tokens
    - Free space: ~150K tokens for LLM reasoning
    """
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = workspace_root
    
    async def build_context(
        self,
        worker_type: str,
        task_description: str,
        conversation_history: list = None,
        tool_results: list = None,
        system_prompt: str = "",
        skills: list = None,
        model_tier: str = "crafter",
        db: AsyncSession | None = None,
        provider_id: str | None = None,
        model_id: str | None = None,
    ) -> tuple[WorkerContext, ContextPolicy]:
        """Build complete context for a worker, returning context and its policy.

        When *db*, *provider_id* and *model_id* are supplied the builder
        queries the ``provider_models`` table for the model's real context
        window and derives a policy from that.  Falls back to tier-based
        defaults when the model metadata is unavailable.

        When *db* is provided, skill instructions are resolved from the
        skill engine and merged into the skills list for the worker.
        """
        policy = None

        # Try to get the real context window from the DB
        if db and provider_id and model_id:
            try:
                ctx_window = await get_model_context_window(db, provider_id, model_id)
                if ctx_window and ctx_window > 0:
                    policy = get_context_policy_for_window(ctx_window)
                    logger.info(
                        f"Using model context window: {ctx_window} tokens "
                        f"for {provider_id}/{model_id}"
                    )
            except Exception as e:
                logger.warning(f"Failed to query model context window: {e}")

        # Fallback to tier-based defaults
        if policy is None:
            policy = get_context_policy(model_tier)

        # Resolve skills from skill engine if db is provided
        resolved_skills = list(skills) if skills else []
        if db:
            try:
                from backend.skill_engine import resolve_skills_for_worker
                db_skills = await resolve_skills_for_worker(db, worker_type)
                if db_skills:
                    resolved_skills.extend(db_skills)
                    logger.info(f"Resolved {len(db_skills)} skills for worker '{worker_type}'")
            except Exception as e:
                logger.warning(f"Failed to resolve skills for worker '{worker_type}': {e}")

        ctx = WorkerContext(
            system_prompt=system_prompt or self._default_system_prompt(worker_type),
            task_description=task_description,
            recent_messages=(conversation_history or [])[-policy.max_history:],
            tool_results=tool_results or [],
            skills=resolved_skills,
        )

        # Extract keywords from task description for smart file selection
        task_keywords = self._extract_keywords(task_description) if task_description else None

        ctx.project_overview = await self._build_project_overview(
            max_files=policy.max_files,
            task_keywords=task_keywords,
            max_tokens=policy.max_tokens // 4,  # Reserve 25% of budget for overview
        )

        return ctx, policy
    
    def _default_system_prompt(self, worker_type: str) -> str:
        """Get default system prompt for a worker type."""
        prompts = {
            "backend": "You are Hugo, the Backend Engineer. You implement server-side logic, APIs, and data processing. You write clean, correct, testable code. Use tools to read files before modifying them.",
            "frontend": "You are Leo, the Frontend Engineer. You implement UI components, styles, and client-side logic. Use tools to read existing code before making changes.",
            "qa": "You are Eve, the QA Engineer. You verify deliverables by running tests and inspecting code. You are skeptical and thorough.",
            "security": "You are Sentinel, the Security Engineer. You find vulnerabilities and recommend fixes. Think like an attacker.",
            "architect": "You are Atlas, the Architect. You design system architecture and break complex work into subtasks.",
            "research": "You are Sage, the Researcher. You find facts, evaluate trade-offs, and provide evidence-based recommendations.",
            "pm": "You are Aria, the Product Manager. You translate user intent into clear requirements.",
            "database": "You are Nova, the Data Engineer. You design schemas and optimize queries.",
            "devops": "You are Nexus, the Integration Engineer. You ensure components work together.",
        }
        return prompts.get(worker_type, "You are a specialized AI worker. Use tools to complete your task.")
    
    async def _build_project_overview(
        self,
        max_files: int = 50,
        task_keywords: list[str] | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Build project overview with smart file selection.

        When *task_keywords* is provided, files whose names or paths match
        any keyword are ranked higher.  Content previews are included for
        the top 3 most relevant files.  The total output is clamped to
        *max_tokens* (estimated at ~4 chars/token) when specified.
        """
        try:
            scored_files: list[tuple[float, str, str]] = []  # (score, rel_path, abs_path)
            for root, dirs, files in os.walk(self.workspace_root):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {
                    'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', '.git'
                }]
                depth = root.replace(self.workspace_root, '').count(os.sep)
                if depth > 3:
                    continue
                for f in files:
                    if f.startswith('.'):
                        continue
                    rel_path = os.path.relpath(os.path.join(root, f), self.workspace_root)
                    abs_path = os.path.join(root, f)
                    score = self._file_relevance_score(rel_path, task_keywords)
                    scored_files.append((score, rel_path, abs_path))

            # Sort by relevance (highest first), then alphabetically
            scored_files.sort(key=lambda x: (-x[0], x[1]))
            top_files = scored_files[:max_files]

            # Build directory tree from selected files
            lines: list[str] = []
            seen_dirs: set[str] = set()
            for _, rel_path, _ in top_files:
                parts = rel_path.split(os.sep)
                # Add parent directories
                for i in range(len(parts) - 1):
                    dir_key = os.sep.join(parts[: i + 1])
                    if dir_key not in seen_dirs:
                        seen_dirs.add(dir_key)
                        indent = '  ' * i
                        lines.append(f"{indent}{parts[i]}/")
                # Add file
                indent = '  ' * (len(parts) - 1)
                lines.append(f"{indent}{parts[-1]}")

            # Include content preview for top 3 most relevant files
            content_preview_lines: list[str] = []
            for score, rel_path, abs_path in top_files[:3]:
                if score <= 0:
                    break
                preview = self._read_file_preview(abs_path, max_lines=20)
                if preview:
                    content_preview_lines.append(f"\n--- {rel_path} ---\n{preview}")

            result = "\n".join(lines)
            if content_preview_lines:
                result += "\n\n## Relevant File Previews" + "\n".join(content_preview_lines)

            # Clamp to max_tokens if specified
            if max_tokens:
                max_chars = max_tokens * 4
                if len(result) > max_chars:
                    result = result[:max_chars] + "\n... (truncated to fit context budget)"

            return result
        except Exception as e:
            logger.warning(f"Failed to build project overview: {e}")
            return ""

    @staticmethod
    def _extract_keywords(task_description: str) -> list[str]:
        """Extract meaningful keywords from a task description.

        Filters out common stop words and returns words longer than 2 chars.
        Also extracts quoted identifiers and file extensions mentioned.
        """
        import re
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
            'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were',
            'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this',
            'that', 'these', 'those', 'it', 'its', 'not', 'no', 'so', 'if',
            'then', 'than', 'too', 'very', 'just', 'about', 'up', 'out', 'all',
            'new', 'also', 'use', 'used', 'using', 'make', 'made', 'add',
            'added', 'fix', 'update', 'change', 'set', 'get', 'run', 'file',
            'code', 'test', 'need', 'should', 'must', 'please', 'implement',
        }
        words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_.-]{2,}', task_description)
        keywords = []
        for w in words:
            wl = w.lower()
            if wl not in stop_words and len(wl) > 2:
                keywords.append(w)
        # Also extract file extensions mentioned (e.g. ".py", ".ts")
        exts = re.findall(r'\.\w{1,5}', task_description)
        keywords.extend(exts)
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for k in keywords:
            kl = k.lower()
            if kl not in seen:
                seen.add(kl)
                unique.append(k)
        return unique

    @staticmethod
    def _file_relevance_score(rel_path: str, task_keywords: list[str] | None) -> float:
        """Score a file's relevance to the task keywords.

        Scoring:
        - +10 for each keyword found in the file path (case-insensitive)
        - +5 for keyword in filename only
        - +2 for common source file extensions
        - +1 for being in a ``src/`` or ``backend/`` directory
        """
        if not task_keywords:
            return 0.0

        path_lower = rel_path.lower().replace(os.sep, '/')
        filename = os.path.basename(rel_path).lower()
        score = 0.0

        for kw in task_keywords:
            kw_lower = kw.lower()
            if kw_lower in path_lower:
                score += 10.0
            elif kw_lower in filename:
                score += 5.0

        # Bonus for source files
        src_exts = {'.py', '.ts', '.tsx', '.js', '.jsx', '.rs', '.go', '.java'}
        if os.path.splitext(filename)[1] in src_exts:
            score += 2.0

        # Bonus for key directories
        if '/src/' in path_lower or '/backend/' in path_lower:
            score += 1.0

        return score

    @staticmethod
    def _read_file_preview(abs_path: str, max_lines: int = 20) -> str:
        """Read the first *max_lines* of a file, skipping binaries."""
        try:
            # Skip large or binary files
            if os.path.getsize(abs_path) > 100_000:
                return ""
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append("... (truncated)")
                        break
                    lines.append(line.rstrip())
            return "\n".join(lines)
        except (OSError, UnicodeDecodeError):
            return ""
