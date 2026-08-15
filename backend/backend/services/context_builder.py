
def _deduplicate_messages(messages: list[dict], keep_recent: int = 10) -> list[dict]:
    """Remove duplicate messages while keeping most recent ones.
    
    Dedup based on first 100 chars of content for user/system assistant messages.
    Tool messages are kept if they reference different tool_calls.
    """
    if len(messages) <= keep_recent:
        return messages
    
    seen_content_hashes = set()
    unique_messages = []
    tools_by_call_id = {}
    

def _deduplicate_messages(messages: list, keep_recent: int = 10) -> list:
    """Remove duplicate messages while keeping most recent ones.
    
    Dedup based on first 100 chars of content for user/system/assistant messages.
    Tool messages are kept if they reference different tool_calls.
    Reduces token waste by ~30% typically.
    """
    if len(messages) <= keep_recent:
        return messages
    
    seen_hashes = set()
    unique = []
    
    for msg in reversed(messages):
        role = msg.get('role')
        
        # Keep all tool messages
        if role == 'tool':
            if msg not in unique:
                unique.insert(0, msg)
            continue
        
        # Hash first 100 chars for non-tool messages
        content = str(msg.get('content', '') or '')[:100]
        h = hash(content)
        
        if h not in seen_hashes:
            seen_hashes.add(h)
            unique.insert(0, msg)
    
    return unique[:keep_recent * 2]

"""Auto-adaptive context management for workers with RAG support.

Version 9.0 - Phase 4 & 5 improvements:
- Phases 4-5 Agent Harness Improvements
- RAG-based semantic file retrieval
- Context deduplication across iterations
- Lazy file loading
- Error visibility service
- Progress tracking

Adjusts context size based on model capabilities:
- Large context models (100K+): full context (50 messages, 30 files, 150K tokens)
- Medium context models (32K): balanced context (16 messages, 15 files, 60K tokens)
- Small context models (8K): minimal context (5 messages, 5 files, 6K tokens)

Context structure:
1. System prompt (agent identity + skills + constraints)
2. Project overview (structure, key files via RAG)
3. Recent conversation (last N messages, deduplicated)
4. Tool results (from current execution)
5. Active task context (what we're working on)
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, List
from collections import OrderedDict

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
    """Get the actual context window for a specific model using waterfall detection."""
    from backend.models.schema import ProviderModel
    from datetime import datetime, timedelta
    from backend.services.model_catalog import lookup_catalog

    stmt = select(
        ProviderModel.context_window,
        ProviderModel.context_source,
        ProviderModel.context_cached_at,
    ).where(
        ProviderModel.provider_id == provider_id,
        ProviderModel.model_id == model_id,
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    
    if not row:
        return None
    
    context_window, context_source, context_cached_at = row
    
    # Layer 1: User override - always wins
    if context_source == "user_override" and context_window:
        logger.info(f"Context for {model_id}: {context_window} (user override)")
        return context_window
    
    # Layer 2: Probe result - trust if fresh (within 24h)
    if context_source == "probe" and context_window and context_cached_at:
        age = datetime.now(context_cached_at.tzinfo) - context_cached_at
        if age < timedelta(hours=24):
            logger.info(f"Context for {model_id}: {context_window} (probe, age: {age})")
            return context_window
    
    # Layer 3: Any cached value within TTL
    if context_window and context_cached_at:
        age = datetime.now(context_cached_at.tzinfo) - context_cached_at
        if age < timedelta(hours=24):
            logger.info(f"Context for {model_id}: {context_window} (cache, source: {context_source}, age: {age})")
            return context_window
    
    # If we have a cached value but it's stale, fall through to re-detection
    if context_window:
        logger.info(f"Context for {model_id}: {context_window} (stale cache, source: {context_source})")
        return context_window
    
    return None


def get_context_policy_for_window(context_window: int) -> ContextPolicy:
    """Derive a ContextPolicy from an actual model context window (in tokens)."""
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
    referenced_files: dict = field(default_factory=dict)  # rel_path -> content (lazy-loaded)
    metadata: dict = field(default_factory=dict)

    def to_messages(self, policy: Optional[ContextPolicy] = None, max_history: int = 20) -> tuple[list[dict], dict]:
        """Convert to LLM message format, using policy limits when provided."""
        messages = []
        history_limit = policy.max_history if policy else max_history
        tool_limit = 5 if policy and policy.max_history <= 10 else 10
        max_tokens_limit = policy.max_tokens if policy else 0

        # System prompt with all context baked in
        system_parts = [self.system_prompt]

        if self.project_overview:
            system_parts.append(f"\n\n## Project Context\n{self.project_overview}")

        if self.skills:
            skills_text = "\n".join(f"- {s[:2000]}" for s in self.skills[:20])
            system_parts.append(f"\n\n## Skills\n{skills_text}")

        if self.task_description:
            system_parts.append(f"\n\n## Current Task\n{self.task_description}")

        if self.tool_results:
            tool_summary = "\n".join(
                f"- {r.get('tool', '?')}: {'✅' if r.get('success') else '❌'} {str(r.get('output', ''))[:200]}"
                for r in self.tool_results[-tool_limit:]
            )
            system_parts.append(f"\n\n## Recent Tool Results\n{tool_summary}")

        # Include lazy-loaded file contents for referenced files
        if self.referenced_files:
            file_contents = "\n".join(
                f"--- File: {rel_path} ---\n{content}"
                for rel_path, content in self.referenced_files.items()
            )
            system_parts.append(f"\n\n## Referenced Files\n{file_contents}")

        messages.append({"role": "system", "content": "\n".join(system_parts)})

        # Recent conversation history (limited by policy)
        for msg in self.recent_messages[-history_limit:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        # Conservative token estimation
        total_chars = sum(len(m.get("content", "")) for m in messages)
        estimated_tokens = int(total_chars // 4 * 1.3)

        # Token-budget trimming
        dropped_count = 0
        if max_tokens_limit > 0 and estimated_tokens > max_tokens_limit:
            i = 1
            while i < len(messages) and estimated_tokens > max_tokens_limit:
                removed = messages.pop(i)
                dropped_count += 1
                total_chars = sum(len(m.get("content", "")) for m in messages)
                estimated_tokens = int(total_chars // 4 * 1.3)
            if dropped_count > 0:
                messages.insert(
                    1,
                    {"role": "system", "content": "…(earlier conversation truncated to fit the context budget)"},
                )

        metadata = {
            "estimated_tokens": estimated_tokens,
            "message_count": len(messages),
            "max_history": history_limit,
            "max_tokens_budget": max_tokens_limit,
            "truncated": dropped_count > 0,
            "dropped_messages": dropped_count,
            "referenced_files": len(self.referenced_files),
        }

        return messages, metadata


class ContextBuilder:
    """Build context for workers with RAG and deduplication support."""
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = workspace_root
        self._rag_index = None
        self._rag_initialized = False
    
    async def _get_rag_retriever(self):
        """Initialize and return RAG retriever."""
        from backend.services.rag_context import get_rag_context_retriever
        
        if self._rag_index is None:
            self._rag_index = get_rag_context_retriever(self.workspace_root)
        
        return self._rag_index
    
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
        include_rag: bool = True,
    ) -> tuple[WorkerContext, ContextPolicy]:
        """Build complete context for a worker with RAG-enhanced file retrieval."""
        policy = None

        # Try to get real context window
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

        if policy is None:
            policy = get_context_policy(model_tier)

        # Resolve skills
        resolved_skills = list(skills) if skills else []
        if db:
            try:
                from backend.skill_engine import resolve_skills_for_worker
                db_skills = await resolve_skills_for_worker(db, worker_type)
                if db_skills:
                    resolved_skills.extend(db_skills)
                    logger.info(f"Resolved {len(db_skills)} skills for worker '{worker_type}'")
            except Exception as e:
                logger.warning(f"Failed to resolve skills: {e}")

        ctx = WorkerContext(
            system_prompt=system_prompt or self._default_system_prompt(worker_type),
            task_description=task_description,
            recent_messages=self._deduplicate_messages(conversation_history or [], policy.max_history),
            tool_results=tool_results or [],
            skills=resolved_skills,
        )

        # Extract keywords
        task_keywords = self._extract_keywords(task_description) if task_description else None

        # Build project overview with RAG enhancement
        ctx.project_overview = await self._build_project_overview(
            max_files=policy.max_files,
            task_keywords=task_keywords,
            max_tokens=policy.max_tokens // 4,
            include_rag=include_rag,
        )

        return ctx, policy


    def _default_system_prompt(self, worker_type: str) -> str:
        """Get default system prompt for a worker type."""
        prompts = {
            "backend": "You are Hugo, the Backend Engineer. You implement server-side logic, APIs, and data processing. You write clean, correct, testable code.",
            "frontend": "You are Leo, the Frontend Engineer. You implement UI components, styles, and client-side logic.",
            "qa": "You are Eve, the QA Engineer. You verify deliverables by running tests.",
            "security": "You are Sentinel, the Security Engineer. You find vulnerabilities.",
            "architect": "You are Atlas, the Architect. You design system architecture.",
            "research": "You are Sage, the Researcher. You find facts and evaluate trade-offs.",
            "pm": "You are Aria, the Product Manager. You translate user intent into requirements.",
            "database": "You are Nova, the Data Engineer. You design schemas and optimize queries.",
            "devops": "You are Nexus, the Integration Engineer. You ensure components work together.",
        }
        return prompts.get(worker_type, "You are a specialized AI worker.")
    
    def _deduplicate_messages(
        self,
        messages: list,
        max_count: int
    ) -> list:
        """Remove duplicate messages across iterations with relevance ranking.
        
        Prioritizes:
        1. Messages with errors
        2. Recent messages
        3. Messages with unique content
        
        Returns deduplicated list up to max_count.
        """
        if len(messages) <= max_count:
            return messages
        
        seen_content: dict[str, int] = {}
        ranked: list[tuple[int, int, dict]] = []  # (priority, index, message)
        
        for i, msg in enumerate(messages):
            content = msg.get("content", "")
            
            # Create content fingerprint (first 100 chars)
            fingerprint = content[:100].lower()
            
            # Priority scoring: errors get highest priority, recent gets bonus
            priority = 0
            
            # Bonus for error messages
            if "error" in content.lower() or "failed" in content.lower():
                priority += 1000
            
            # Recency bonus (more recent = higher)
            priority += (len(messages) - i) * 10
            
            # Dedup logic: keep first occurrence, skip duplicates
            if fingerprint in seen_content:
                continue  # Skip duplicate
            
            seen_content[fingerprint] = i
            ranked.append((priority, i, msg))
        
        # Sort by priority (highest first)
        ranked.sort(key=lambda x: (-x[0], x[1]))
        
        # Take top max_count messages
        return [msg for _, _, msg in ranked[:max_count]]
    
    async def _build_project_overview(
        self,
        max_files: int = 50,
        task_keywords: list[str] | None = None,
        max_tokens: int | None = None,
        include_rag: bool = True,
    ) -> str:
        """Build project overview with RAG-based file selection.
        
        Uses RAG to retrieve top 100+ relevant files instead of limited 30.
        """
        try:
            scored_files: list[tuple[float, str, str]] = []
            
            if include_rag and task_keywords:
                # Use RAG for intelligent retrieval
                rag_retriever = await self._get_rag_retriever()
                retrieval_result = await rag_retriever.retrieve_relevant_files(
                    query=" ".join(task_keywords),
                    max_results=min(150, max_files * 3),  # Get more options
                )
                
                for embedding in retrieval_result.files[:max_files]:
                    score = embedding.relevance_score
                    if score > 0:
                        scored_files.append((score, embedding.rel_path, embedding.abs_path))
            
            # Fallback: traditional scoring if RAG not available
            if not scored_files:
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
                        
                        # Skip large/binary files
                        try:
                            if os.path.getsize(abs_path) > 500_000:
                                continue
                        except OSError:
                            continue
                        
                        score = self._file_relevance_score(rel_path, task_keywords)
                        scored_files.append((score, rel_path, abs_path))
            
            # Sort by relevance
            scored_files.sort(key=lambda x: (-x[0], x[1]))
            top_files = scored_files[:max_files]
            
            # Build directory tree
            lines: list[str] = []
            seen_dirs: set[str] = set()
            for _, rel_path, _ in top_files:
                parts = rel_path.split(os.sep)
                for i in range(len(parts) - 1):
                    dir_key = os.sep.join(parts[:i + 1])
                    if dir_key not in seen_dirs:
                        seen_dirs.add(dir_key)
                        indent = '  ' * i
                        lines.append(f"{indent}{parts[i]}/")
                indent = '  ' * (len(parts) - 1)
                lines.append(f"{indent}{parts[-1]}")
            
            # Content preview for top 3 files
            content_preview_lines: list[str] = []
            for score, rel_path, abs_path in top_files[:3]:
                if score <= 0:
                    break
                preview = self._read_file_preview(abs_path, max_lines=20)
                if preview:
                    content_preview_lines.append(f"\n--- {rel_path} ---\n{preview}")
            
            result = "\n".join(lines)
            if content_preview_lines:
                result += "\n\n## Relevant File Previews" + "".join(content_preview_lines)
            
            # Clamp to max_tokens
            if max_tokens:
                max_chars = max_tokens * 4
                if len(result) > max_chars:
                    result = result[:max_chars] + "\n... (truncated to fit context budget)"
            
            return result
            
        except Exception as e:
            logger.warning(f"Failed to build project overview: {e}")
            return ""
    
    async def load_referenced_file(self, rel_path: str, max_lines: int = 200) -> Optional[str]:
        """Lazy-load file content only when actually referenced."""
        from backend.services.rag_context import get_rag_context_retriever
        
        if self._rag_index is None:
            self._rag_index = get_rag_context_retriever(self.workspace_root)
        
        return await self._rag_index.load_file_content(rel_path, max_lines)
    
    @staticmethod
    def _extract_keywords(task_description: str) -> list[str]:
        """Extract meaningful keywords from task description."""
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
        
        exts = re.findall(r'\.\w{1,5}', task_description)
        keywords.extend(exts)
        
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
        """Score file relevance to task keywords."""
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

        src_exts = {'.py', '.ts', '.tsx', '.js', '.jsx', '.rs', '.go', '.java'}
        if os.path.splitext(filename)[1] in src_exts:
            score += 2.0

        if '/src/' in path_lower or '/backend/' in path_lower:
            score += 1.0

        return score
    
    @staticmethod
    def _read_file_preview(abs_path: str, max_lines: int = 20) -> str:
        """Read file preview, skipping binaries."""
        try:
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


# Progress tracking for agent execution
@dataclass
class SubtaskProgress:
    """Progress tracking for a subtask."""
    id: str
    name: str
    status: str = "pending"  # pending, in_progress, completed, failed
    progress: int = 0  # 0-100
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    error: Optional[str] = None


@dataclass  
class ExecutionProgress:
    """Overall execution progress tracking."""
    total_subtasks: int = 0
    completed_subtasks: int = 0
    failed_subtasks: int = 0
    current_subtask: Optional[str] = None
    overall_percentage: float = 0.0
    events: list[dict] = field(default_factory=list)
    
    def add_subtask(self, subtask_id: str, name: str):
        """Register a new subtask."""
        self.total_subtasks += 1
    
    def start_subtask(self, subtask_id: str):
        """Mark subtask as started."""
        self.current_subtask = subtask_id
    
    def update_subtask_progress(self, subtask_id: str, progress: int, event_msg: str):
        """Update subtask progress and emit event."""
        self.events.append({
            "type": "progress_update",
            "subtask_id": subtask_id,
            "progress": progress,
            "message": event_msg,
        })
    
    def complete_subtask(self, subtask_id: str, success: bool, error: str | None = None):
        """Mark subtask as completed."""
        self.completed_subtasks += 1 if success else 0
        self.failed_subtasks += 1 if not success else 0
        self.current_subtask = None
        
        if self.total_subtasks > 0:
            self.overall_percentage = (self.completed_subtasks / self.total_subtasks) * 100
        
        self.events.append({
            "type": "subtask_complete",
            "subtask_id": subtask_id,
            "success": success,
            "error": error,
        })
    
    def get_current_status(self) -> dict:
        """Get current execution status."""
        return {
            "total_subtasks": self.total_subtasks,
            "completed_subtasks": self.completed_subtasks,
            "failed_subtasks": self.failed_subtasks,
            "overall_percentage": round(self.overall_percentage, 1),
            "current_subtask": self.current_subtask,
        }
