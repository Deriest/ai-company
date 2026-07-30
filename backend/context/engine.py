"""Context & Knowledge Intelligence — Core Engine.

Provides persistent engineering memory and context to all engines.
"""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from context.config import context_config
from context.models import ProjectContext, KnowledgeEntry, DecisionRecord

logger = logging.getLogger("aic.context")


class ContextEngine:
    """Context & Knowledge Intelligence Engine."""

    def __init__(self, session: AsyncSession | None = None):
        self.session = session
        self._knowledge: dict[str, KnowledgeEntry] = {}
        self._decisions: list[DecisionRecord] = []

    async def get_context(
        self,
        project_id: str,
        domain: str | None = None,
    ) -> ProjectContext:
        """Get project context for an engine.

        Args:
            project_id: Project ID
            domain: Optional domain filter

        Returns:
            ProjectContext with relevant knowledge
        """
        if not context_config.enabled:
            return ProjectContext(project_id=project_id)

        # Load from database if session available
        entries = []
        if self.session:
            from storage.models import KnowledgeEntry as KnowledgeEntryORM
            query = select(KnowledgeEntryORM)
            if domain:
                query = query.where(KnowledgeEntryORM.domain == domain)
            result = await self.session.execute(query)
            db_entries = result.scalars().all()
            entries = [
                KnowledgeEntry(
                    id=e.id,
                    domain=e.domain,
                    key=e.key,
                    value=e.value,
                    source=e.source,
                    confidence=e.confidence,
                )
                for e in db_entries
            ]
        else:
            # Fallback to in-memory
            entries = list(self._knowledge.values())
            if domain:
                entries = [e for e in entries if e.domain == domain]

        # Build context
        context = ProjectContext(
            project_id=project_id,
            knowledge_entries=entries,
            past_decisions=self._decisions[-10:],  # Last 10 decisions
            freshness_score=1.0,
        )

        return context

    async def add_knowledge(
        self,
        domain: str,
        key: str,
        value: str,
        source: str = "manual",
    ) -> KnowledgeEntry:
        """Add a knowledge entry.

        Args:
            domain: Knowledge domain
            key: Knowledge key
            value: Knowledge value
            source: Source of knowledge

        Returns:
            Created KnowledgeEntry
        """
        entry = KnowledgeEntry(
            domain=domain,
            key=key,
            value=value,
            source=source,
        )

        # Persist to database if session available
        if self.session:
            from storage.models import KnowledgeEntry as KnowledgeEntryORM
            db_entry = KnowledgeEntryORM(
                id=entry.id,
                domain=domain,
                key=key,
                value=value,
                source=source,
                confidence=entry.confidence,
            )
            self.session.add(db_entry)
            await self.session.flush()
        else:
            self._knowledge[entry.id] = entry

        return entry

    async def record_decision(
        self,
        decision: str,
        rationale: str,
        context: str = "",
    ) -> DecisionRecord:
        """Record an engineering decision.

        Args:
            decision: The decision made
            rationale: Why it was made
            context: Additional context

        Returns:
            Created DecisionRecord
        """
        record = DecisionRecord(
            decision=decision,
            rationale=rationale,
            context=context,
        )

        # Persist to database if session available
        if self.session:
            from storage.models import DecisionRecord as DecisionRecordORM
            db_record = DecisionRecordORM(
                id=record.id,
                decision=decision,
                rationale=rationale,
                context=context,
            )
            self.session.add(db_record)
            await self.session.flush()
        else:
            self._decisions.append(record)

        return record

    async def search_knowledge(
        self,
        query: str,
        domain: str | None = None,
    ) -> list[KnowledgeEntry]:
        """Search knowledge entries.

        Args:
            query: Search query
            domain: Optional domain filter

        Returns:
            List of matching KnowledgeEntry
        """
        results = []
        query_lower = query.lower()

        # Search database if session available
        if self.session:
            from storage.models import KnowledgeEntry as KnowledgeEntryORM
            db_query = select(KnowledgeEntryORM)
            if domain:
                db_query = db_query.where(KnowledgeEntryORM.domain == domain)
            result = await self.session.execute(db_query)
            db_entries = result.scalars().all()
            for entry in db_entries:
                if (query_lower in entry.key.lower() or
                    query_lower in entry.value.lower()):
                    results.append(KnowledgeEntry(
                        id=entry.id,
                        domain=entry.domain,
                        key=entry.key,
                        value=entry.value,
                        source=entry.source,
                        confidence=entry.confidence,
                    ))
        else:
            # Fallback to in-memory
            for entry in self._knowledge.values():
                if domain and entry.domain != domain:
                    continue
                if (query_lower in entry.key.lower() or
                    query_lower in entry.value.lower()):
                    results.append(entry)

        return results

    def get_stats(self) -> dict:
        """Get knowledge base statistics."""
        domains = {}
        for entry in self._knowledge.values():
            domains[entry.domain] = domains.get(entry.domain, 0) + 1

        return {
            "total_entries": len(self._knowledge),
            "total_decisions": len(self._decisions),
            "domains": domains,
        }


# Singleton
context_engine = ContextEngine()
