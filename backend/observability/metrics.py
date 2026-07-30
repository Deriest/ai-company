"""AIC Platform — Metrics collection and query.

Records numeric samples to the ``metrics`` table and exposes simple
aggregations. All methods are async and use the shared ``async_session``.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from storage.database import async_session
from storage.models import Metric

# Key metric names surfaced by ``summary``.
KEY_METRICS: tuple[str, ...] = (
    "task.created",
    "task.completed",
    "worker.execution_time",
    "worker.failure_rate",
    "dispatcher.latency",
)


class MetricsRecorder:
    """Async metrics recorder backed by the ``metrics`` table."""

    async def record(
        self,
        name: str,
        value: float,
        unit: str | None = None,
        labels: dict | None = None,
    ) -> Metric:
        async with async_session() as session:
            metric = Metric(
                name=name,
                value=float(value),
                unit=unit,
                labels=labels or {},
            )
            session.add(metric)
            await session.commit()
            await session.refresh(metric)
            return metric

    async def query(
        self,
        name: str,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Metric]:
        stmt = select(Metric).where(Metric.name == name)
        if since is not None:
            stmt = stmt.where(Metric.created_at >= since)
        stmt = stmt.order_by(Metric.created_at.desc()).limit(limit)
        async with async_session() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def summary(self) -> dict:
        """Counts and averages for each key metric (empty if none recorded)."""
        out: dict[str, dict] = {}
        async with async_session() as session:
            for name in KEY_METRICS:
                stmt = select(
                    func.count(Metric.id),
                    func.avg(Metric.value),
                ).where(Metric.name == name)
                count, avg = (await session.execute(stmt)).one()
                out[name] = {
                    "count": int(count or 0),
                    "avg": float(avg) if avg is not None else None,
                }
        return out


metrics = MetricsRecorder()
