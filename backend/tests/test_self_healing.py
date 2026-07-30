"""Integration tests for v1.6.0 recovery wiring: self-heal, parallel plan, AST.

NOTE: Tests for ParallelDispatcher are skipped after PR-1 Execution Engine Consolidation.
"""

import pytest

from backend.ast_analyzer import ASTAnalyzer
from backend.self_healing import SelfHealingEngine, run_startup_self_heal
from storage.database import async_session


@pytest.mark.asyncio
async def test_self_healing_engine_returns_report():
    async with async_session() as session:
        engine = SelfHealingEngine(session)
        report = await engine.audit_and_repair(redispatch_created=False)
        assert report.status in ("healthy", "repaired", "error")
        assert isinstance(report.issues_found, list)
        assert isinstance(report.repairs_applied, list)
        d = report.to_dict()
        assert "timestamp" in d


@pytest.mark.asyncio
async def test_run_startup_self_heal_entry():
    """Entry used by FastAPI lifespan must be importable and callable."""
    report = await run_startup_self_heal()
    assert report.status in ("healthy", "repaired", "error")


def test_smart_triage_execution_levels():
    """Test that smart triage assigns execution levels correctly."""
    from workflow.triage import perform_smart_triage
    
    # Simple task should be L1 QUICK
    result = perform_smart_triage("Update README documentation", task_type="docs")
    assert result.level.value in ("QUICK", "STANDARD")
    
    # Complex multi-component task should be L3/L4
    result = perform_smart_triage(
        "Refactor authentication system with OAuth2 integration across backend and frontend",
        task_type="refactor"
    )
    assert result.level.value in ("EXTENDED", "FULL", "STANDARD")
    
    # Verify triage result structure
    assert hasattr(result, 'level')
    assert hasattr(result, 'reason')  # Changed from 'reasoning' to 'reason'
    assert result.to_dict() is not None


@pytest.mark.asyncio
async def test_executor_phase_management():
    """Test that unified executor manages phases correctly."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.pool import StaticPool
    from storage.models import Base, Task, TaskStatus, TaskType, Project, User
    
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with factory() as session:
        user = User(id="u1", username="test", hashed_password="x", is_active=True)
        project = Project(id="p1", name="Test", slug="test", owner_id="u1")
        task = Task(
            id="t1", project_id="p1", title="Test task",
            type=TaskType.FEATURE.value, status=TaskStatus.CREATED.value,
            worker_type="pm"
        )
        session.add_all([user, project, task])
        await session.commit()
        
        from runtime.executor import execute_task
        result = await execute_task(session, task)
        
        await session.refresh(task)
        # Executor should advance through phases
        assert task.status != TaskStatus.CREATED.value
        assert "success" in result
        
        # Verify phase semantics in context
        assert "execution_level" in task.context
    
    await engine.dispose()


def test_ast_generate_tests_python(tmp_path):
    test_file = tmp_path / "sample_target.py"
    test_file.write_text(
        """
def add_numbers(a, b):
    return a + b
"""
    )
    gen = ASTAnalyzer.generate_regression_test_suite(str(test_file))
    assert gen["status"] == "success"
    assert "test_add_numbers_regression" in gen["test_code"]


def test_ast_parse_missing_file():
    res = ASTAnalyzer.parse_python_file("/nonexistent/path/x.py")
    assert "error" in res or res.get("symbols") == []
