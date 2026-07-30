"""AIC Platform — Audit log recording and querying.

Append-only audit trail of actor actions against resources, backed by the
``audit_logs`` table. All methods are async.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from storage.database import async_session
from storage.models import AuditLog


class AuditRecorder:
    """Async audit recorder backed by the ``audit_logs`` table."""

    async def record(
        self,
        actor: str,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        result: str = "success",
        details: dict | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        async with async_session() as session:
            entry = AuditLog(
                actor=actor,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                result=result,
                details=details or {},
                ip_address=ip_address,
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
            return entry

    async def query(
        self,
        actor: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[AuditLog]:
        stmt = select(AuditLog)
        if actor is not None:
            stmt = stmt.where(AuditLog.actor == actor)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        if resource_type is not None:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if since is not None:
            stmt = stmt.where(AuditLog.created_at >= since)
        stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
        async with async_session() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())


audit = AuditRecorder()
