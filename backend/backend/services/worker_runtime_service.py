from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func as sqlfunc, case
from backend.models.schema import WorkerRuntime, Provider, WORKER_DEFAULTS
from backend.models.ai_runtime import WorkerExecution, GenerationLog
import datetime
from typing import Optional


class WorkerMetrics:
    def __init__(self, role: str, total_executions: int = 0, completed: int = 0, errors: int = 0,
                 avg_latency_ms: float = 0.0, last_executed_at: Optional[str] = None,
                 currently_running: bool = False):
        self.role = role
        self.total_executions = total_executions
        self.completed = completed
        self.errors = errors
        self.avg_latency_ms = avg_latency_ms
        self.last_executed_at = last_executed_at
        self.currently_running = currently_running


class WorkerRuntimeService:
    @staticmethod
    async def get_worker(db: AsyncSession, role: str) -> Optional[WorkerRuntime]:
        res = await db.execute(select(WorkerRuntime).where(WorkerRuntime.role == role.lower()))
        return res.scalars().first()

    @staticmethod
    async def get_enabled_workers(db: AsyncSession) -> list[WorkerRuntime]:
        res = await db.execute(
            select(WorkerRuntime).where(WorkerRuntime.is_enabled == True).order_by(WorkerRuntime.role)
        )
        return list(res.scalars().all())

    @staticmethod
    async def get_all_workers(db: AsyncSession) -> list[WorkerRuntime]:
        await WorkerRuntimeService._ensure_defaults(db)
        res = await db.execute(select(WorkerRuntime).order_by(WorkerRuntime.role))
        return list(res.scalars().all())

    @staticmethod
    async def _ensure_defaults(db: AsyncSession) -> None:
        res = await db.execute(select(WorkerRuntime))
        existing = {w.role: w for w in res.scalars().all()}
        changed = False
        for role, meta in WORKER_DEFAULTS.items():
            if role not in existing:
                w = WorkerRuntime(
                    role=role,
                    label=meta["label"],
                    description=meta["description"],
                    system_prompt=meta["system_prompt"],
                    temperature=meta["temperature"],
                    top_p=1.0,
                    is_enabled=True,
                )
                db.add(w)
                changed = True
            else:
                w = existing[role]
                if not w.label:
                    w.label = meta["label"]
                    w.description = meta["description"]
                    changed = True
                if not w.system_prompt:
                    w.system_prompt = meta["system_prompt"]
                    changed = True
        if changed:
            await db.commit()

    @staticmethod
    async def start_execution(db: AsyncSession, role: str, conversation_id: str,
                              message_id: str, provider_id: Optional[str],
                              model_id: Optional[str]) -> WorkerExecution:
        exec_record = WorkerExecution(
            worker_role=role,
            conversation_id=conversation_id,
            message_id=message_id,
            provider_id=provider_id,
            model_id=model_id,
            status="running",
        )
        db.add(exec_record)
        await db.commit()
        await db.refresh(exec_record)
        return exec_record

    @staticmethod
    async def finish_execution(db: AsyncSession, exec_id: str, status: str = "completed"):
        res = await db.execute(select(WorkerExecution).where(WorkerExecution.id == exec_id))
        rec = res.scalars().first()
        if rec:
            rec.status = status
            rec.completed_at = datetime.datetime.now(datetime.timezone.utc)
            await db.commit()

    @staticmethod
    async def get_metrics(db: AsyncSession, role: str) -> WorkerMetrics:
        res = await db.execute(
            select(
                sqlfunc.count(WorkerExecution.id).label("total"),
                sqlfunc.sum(case((WorkerExecution.status == "completed", 1), else_=0)).label("completed"),
                sqlfunc.sum(case((WorkerExecution.status == "error", 1), else_=0)).label("errors"),
                sqlfunc.max(WorkerExecution.completed_at).label("last_run"),
                sqlfunc.sum(case((WorkerExecution.status == "running", 1), else_=0)).label("running"),
            ).where(WorkerExecution.worker_role == role)
        )
        row = res.first()
        if not row or row.total == 0:
            return WorkerMetrics(role=role)

        last_run_iso = row.last_run.isoformat() if row.last_run else None
        return WorkerMetrics(
            role=role,
            total_executions=row.total or 0,
            completed=row.completed or 0,
            errors=row.errors or 0,
            last_executed_at=last_run_iso,
            currently_running=(row.running or 0) > 0,
        )

    @staticmethod
    async def get_all_metrics(db: AsyncSession) -> dict[str, WorkerMetrics]:
        res = await db.execute(
            select(
                WorkerExecution.worker_role,
                sqlfunc.count(WorkerExecution.id).label("total"),
                sqlfunc.sum(case((WorkerExecution.status == "completed", 1), else_=0)).label("completed"),
                sqlfunc.sum(case((WorkerExecution.status == "error", 1), else_=0)).label("errors"),
                sqlfunc.max(WorkerExecution.completed_at).label("last_run"),
                sqlfunc.sum(case((WorkerExecution.status == "running", 1), else_=0)).label("running"),
            ).group_by(WorkerExecution.worker_role)
        )
        metrics: dict[str, WorkerMetrics] = {}
        for row in res.all():
            metrics[row.worker_role] = WorkerMetrics(
                role=row.worker_role,
                total_executions=row.total or 0,
                completed=row.completed or 0,
                errors=row.errors or 0,
                last_executed_at=row.last_run.isoformat() if row.last_run else None,
                currently_running=(row.running or 0) > 0,
            )
        return metrics


worker_runtime_service = WorkerRuntimeService()
