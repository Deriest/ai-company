"""Context Source Adapters — Unified interface for context sources.

Provides abstract base class and concrete adapters for:
- Memory (multi-scope memory entries)
- RAG (document retrieval)
- Knowledge (project knowledge base)
- Workspace (file context)
- Conversation (message history)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("aic.context.sources")


@dataclass
class ContextChunk:
    """A single piece of context from any source."""
    source: str  # memory, rag, knowledge, workspace, conversation
    content: str
    relevance: float = 1.0  # 0.0-1.0
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SourceResult:
    """Result from a context source query."""
    source: str
    chunks: list[ContextChunk] = field(default_factory=list)
    total_tokens: int = 0
    query_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ContextSource(ABC):
    """Abstract base class for context sources."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Source name identifier."""
        ...

    @property
    @abstractmethod
    def priority(self) -> int:
        """Source priority (lower = higher priority)."""
        ...

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> SourceResult:
        """Retrieve context chunks for a query.

        Args:
            query: Search query or context description
            max_tokens: Maximum tokens to return
            **kwargs: Source-specific parameters

        Returns:
            SourceResult with chunks
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if this source is available."""
        ...


class MemorySource(ContextSource):
    """Memory context source — multi-scope memory entries."""

    def __init__(self, db: Any, scope: str = "conversation", scope_id: str | None = None):
        self.db = db
        self.scope = scope
        self.scope_id = scope_id

    @property
    def name(self) -> str:
        return "memory"

    @property
    def priority(self) -> int:
        return 20  # Medium priority

    async def retrieve(
        self,
        query: str,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> SourceResult:
        """Retrieve memory entries matching query."""
        import time
        start = time.time()

        from backend.services.memory_service import MemoryService

        entries = await MemoryService.retrieve(
            self.db,
            scope=self.scope,
            scope_id=self.scope_id,
            limit=20,
        )

        chunks = []
        total_tokens = 0
        query_lower = query.lower()

        for entry in entries:
            # Simple relevance scoring based on keyword match
            value_str = str(entry.value)
            relevance = 0.5
            if query_lower in entry.key.lower() or query_lower in value_str.lower():
                relevance = 0.9

            token_count = len(value_str.split())
            if total_tokens + token_count > max_tokens:
                break

            chunks.append(ContextChunk(
                source="memory",
                content=f"{entry.key}: {value_str}",
                relevance=relevance * entry.importance,
                token_count=token_count,
                metadata={
                    "scope": entry.scope,
                    "scope_id": entry.scope_id,
                    "category": entry.category,
                    "importance": entry.importance,
                },
            ))
            total_tokens += token_count

        elapsed = (time.time() - start) * 1000
        return SourceResult(
            source="memory",
            chunks=chunks,
            total_tokens=total_tokens,
            query_time_ms=elapsed,
        )

    async def is_available(self) -> bool:
        return self.db is not None


class RAGSource(ContextSource):
    """RAG context source — document retrieval."""

    def __init__(self, db: Any):
        self.db = db

    @property
    def name(self) -> str:
        return "rag"

    @property
    def priority(self) -> int:
        return 10  # High priority (most relevant)

    async def retrieve(
        self,
        query: str,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> SourceResult:
        """Retrieve RAG context for query."""
        import time
        start = time.time()

        from backend.services.rag_service import RAGService

        result = await RAGService.build_context(
            self.db,
            query=query,
            top_k=kwargs.get("top_k", 5),
            max_tokens=max_tokens,
        )

        chunks = []
        if result.get("context"):
            chunks.append(ContextChunk(
                source="rag",
                content=result["context"],
                relevance=0.8,
                token_count=result.get("totalTokens", 0),
                metadata={
                    "citations": result.get("citations", []),
                    "chunks_used": result.get("chunksUsed", 0),
                },
            ))

        elapsed = (time.time() - start) * 1000
        return SourceResult(
            source="rag",
            chunks=chunks,
            total_tokens=result.get("totalTokens", 0),
            query_time_ms=elapsed,
        )

    async def is_available(self) -> bool:
        return self.db is not None


class KnowledgeSource(ContextSource):
    """Knowledge context source — project knowledge base."""

    def __init__(self, db: Any, project_id: str | None = None):
        self.db = db
        self.project_id = project_id

    @property
    def name(self) -> str:
        return "knowledge"

    @property
    def priority(self) -> int:
        return 15  # Medium-high priority

    async def retrieve(
        self,
        query: str,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> SourceResult:
        """Retrieve knowledge entries matching query."""
        import time
        start = time.time()

        from context.engine import ContextEngine

        engine = ContextEngine(self.db)
        entries = await engine.search_knowledge(query, domain=kwargs.get("domain"))

        chunks = []
        total_tokens = 0

        for entry in entries:
            token_count = len(entry.value.split())
            if total_tokens + token_count > max_tokens:
                break

            chunks.append(ContextChunk(
                source="knowledge",
                content=f"[{entry.domain}] {entry.key}: {entry.value}",
                relevance=entry.confidence,
                token_count=token_count,
                metadata={
                    "domain": entry.domain,
                    "source": entry.source,
                    "confidence": entry.confidence,
                },
            ))
            total_tokens += token_count

        elapsed = (time.time() - start) * 1000
        return SourceResult(
            source="knowledge",
            chunks=chunks,
            total_tokens=total_tokens,
            query_time_ms=elapsed,
        )

    async def is_available(self) -> bool:
        return self.db is not None


class ConversationSource(ContextSource):
    """Conversation context source — message history."""

    def __init__(self, db: Any, conversation_id: str | None = None):
        self.db = db
        self.conversation_id = conversation_id

    @property
    def name(self) -> str:
        return "conversation"

    @property
    def priority(self) -> int:
        return 5  # Highest priority (most recent)

    async def retrieve(
        self,
        query: str,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> SourceResult:
        """Retrieve recent conversation messages."""
        import time
        start = time.time()

        if not self.conversation_id:
            return SourceResult(source="conversation")

        from sqlalchemy import select
        from storage.models import Message

        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == self.conversation_id)
            .order_by(Message.created_at.desc())
            .limit(kwargs.get("limit", 20))
        )
        messages = list(reversed(result.scalars().all()))

        chunks = []
        total_tokens = 0

        for msg in messages:
            content = msg.content or ""
            token_count = len(content.split())
            if total_tokens + token_count > max_tokens:
                break

            chunks.append(ContextChunk(
                source="conversation",
                content=f"[{msg.role}] {content}",
                relevance=0.7,
                token_count=token_count,
                metadata={
                    "role": msg.role,
                    "message_id": msg.id,
                },
            ))
            total_tokens += token_count

        elapsed = (time.time() - start) * 1000
        return SourceResult(
            source="conversation",
            chunks=chunks,
            total_tokens=total_tokens,
            query_time_ms=elapsed,
        )

    async def is_available(self) -> bool:
        return self.db is not None and self.conversation_id is not None


class WorkspaceSource(ContextSource):
    """Workspace context source — reads project files for context."""

    def __init__(self, workspace_path: str | None = None):
        self.workspace_path = workspace_path

    @property
    def name(self) -> str:
        return "workspace"

    @property
    def priority(self) -> int:
        return 25  # Lower priority

    async def retrieve(
        self,
        query: str,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> SourceResult:
        """Retrieve workspace context by reading relevant project files."""
        import os
        import time

        start = time.monotonic()
        chunks: list[ContextChunk] = []

        if not self.workspace_path or not os.path.isdir(self.workspace_path):
            return SourceResult(
                source="workspace",
                chunks=[],
                total_tokens=0,
                query_time_ms=(time.monotonic() - start) * 1000,
                metadata={"status": "no_workspace"},
            )

        # Read common project files for context
        context_files = [
            "README.md", "README.rst", "README.txt",
            "package.json", "pyproject.toml", "setup.py", "setup.cfg",
            "Cargo.toml", "go.mod", "Makefile", "Dockerfile",
            ".env.example", "docker-compose.yml",
        ]

        total_tokens = 0
        for filename in context_files:
            if total_tokens >= max_tokens:
                break
            filepath = os.path.join(self.workspace_path, filename)
            if os.path.isfile(filepath):
                try:
                    with open(filepath, "r", errors="ignore") as f:
                        content = f.read(4000)  # Limit per file
                    tokens = len(content) // 4
                    if total_tokens + tokens > max_tokens:
                        content = content[: (max_tokens - total_tokens) * 4]
                        tokens = len(content) // 4
                    chunks.append(ContextChunk(
                        source="workspace",
                        content=f"[{filename}]\n{content}",
                        token_count=tokens,
                        relevance=0.6,
                        metadata={"file": filename},
                    ))
                    total_tokens += tokens
                except (OSError, PermissionError):
                    continue

        return SourceResult(
            source="workspace",
            chunks=chunks,
            total_tokens=total_tokens,
            query_time_ms=(time.monotonic() - start) * 1000,
            metadata={"status": "active", "files_read": len(chunks)},
        )

    async def is_available(self) -> bool:
        import os
        return self.workspace_path is not None and os.path.isdir(self.workspace_path)


class CodeContextSource(ContextSource):
    """Reads actual source files from the project workspace."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    @property
    def name(self) -> str:
        return "code"

    @property
    def priority(self) -> int:
        return 30

    async def retrieve(self, query: str, max_tokens: int = 2000, **kwargs: Any) -> SourceResult:
        import os
        import time as _time

        start = _time.monotonic()
        chunks: list[ContextChunk] = []
        project_root = self.config.get("project_root", "")
        if not project_root or not os.path.isdir(project_root):
            return SourceResult(source="code", chunks=[], query_time_ms=(_time.monotonic() - start) * 1000)

        extensions = {'.py', '.js', '.ts', '.tsx', '.jsx', '.go', '.rs', '.java'}
        skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build'}
        total_tokens = 0

        for root, dirs, files in os.walk(project_root):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for f in files:
                if any(f.endswith(ext) for ext in extensions):
                    fpath = os.path.join(root, f)
                    rel = os.path.relpath(fpath, project_root)
                    try:
                        with open(fpath, 'r', errors='replace') as fh:
                            content = fh.read(4000)
                        token_count = len(content) // 4
                        if total_tokens + token_count > max_tokens:
                            break
                        chunks.append(ContextChunk(
                            content=f"```{f.split('.')[-1]} {rel}\n{content}\n```",
                            source="code",
                            relevance=0.5,
                            token_count=token_count,
                        ))
                        total_tokens += token_count
                    except (OSError, PermissionError):
                        pass
            if total_tokens > max_tokens:
                break

        elapsed = (_time.monotonic() - start) * 1000
        return SourceResult(source="code", chunks=chunks[:10], total_tokens=total_tokens, query_time_ms=elapsed)

    async def is_available(self) -> bool:
        import os
        project_root = self.config.get("project_root", "")
        return bool(project_root) and os.path.isdir(project_root)


class ToolHistorySource(ContextSource):
    """Includes recent tool executions in context."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    @property
    def name(self) -> str:
        return "tool_history"

    @property
    def priority(self) -> int:
        return 35

    async def retrieve(self, query: str, max_tokens: int = 2000, **kwargs: Any) -> SourceResult:
        import time as _time

        start = _time.monotonic()
        chunks: list[ContextChunk] = []
        tool_calls = self.config.get("recent_tool_calls", [])

        for tc in tool_calls[-10:]:
            content = f"Tool: {tc.get('type', 'unknown')} — {tc.get('label', '')}\nResult: {tc.get('output', '')[:500]}"
            chunks.append(ContextChunk(
                content=content,
                source="tool_history",
                relevance=0.6,
                token_count=len(content) // 4,
            ))

        elapsed = (_time.monotonic() - start) * 1000
        total_tokens = sum(c.token_count for c in chunks)
        return SourceResult(source="tool_history", chunks=chunks, total_tokens=total_tokens, query_time_ms=elapsed)

    async def is_available(self) -> bool:
        return bool(self.config.get("recent_tool_calls"))


def create_default_sources(
    db: Any,
    conversation_id: str | None = None,
    project_id: str | None = None,
) -> list[ContextSource]:
    """Create default set of context sources.

    Args:
        db: Database session
        conversation_id: Optional conversation ID
        project_id: Optional project ID

    Returns:
        List of context sources sorted by priority
    """
    sources: list[ContextSource] = [
        ConversationSource(db, conversation_id),
        RAGSource(db),
        KnowledgeSource(db, project_id),
        MemorySource(db, "conversation", conversation_id),
        MemorySource(db, "project", project_id),
        WorkspaceSource(),
    ]

    # Sort by priority (lower = higher priority)
    sources.sort(key=lambda s: s.priority)
    return sources
