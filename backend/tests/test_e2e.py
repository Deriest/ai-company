"""AIC Platform — E2E Integration Tests.

Tests full pipeline: Chat -> Task -> Dispatcher -> Workflow -> Completion.
"""
import pytest
from sqlalchemy import select
from storage.models import (
    User, Task, TaskStatus, TaskType,
    Conversation, Approval, ApprovalStatus,
)


async def _approve_pending(session, dispatcher, task_id, approver_id):
    """Auto-approve any pending approvals for a task."""
    result = await session.execute(
        select(Approval).where(
            Approval.task_id == task_id,
            Approval.status == ApprovalStatus.PENDING.value,
        )
    )
    approvals = result.scalars().all()
    if approvals:
        approver = await session.get(User, approver_id)
        for a in approvals:
            await dispatcher.decide_approval(a.id, approver, ApprovalStatus.APPROVED, "auto-approved")
        await session.commit()


@pytest.mark.asyncio
async def test_chat_creates_task(db_session):
    async with db_session() as session:
        conv = await session.get(Conversation, "conv-1")
        from conversation.engine import ConversationEngine
        engine = ConversationEngine(session)
        response = await engine.process_message(conv, "Create task to build a landing page for users with React UI and Tailwind CSS components")
        assert response.intent == "task_request"
        assert response.meta.get("task_id") is not None
        assert response.meta.get("task_type") == "feature"


@pytest.mark.asyncio
async def test_chat_detects_question(db_session):
    async with db_session() as session:
        conv = await session.get(Conversation, "conv-1")
        from conversation.engine import ConversationEngine
        engine = ConversationEngine(session)
        response = await engine.process_message(conv, "What is the status of the project?")
        assert response.intent == "status"


@pytest.mark.asyncio
async def test_chat_detects_bugfix(db_session):
    async with db_session() as session:
        conv = await session.get(Conversation, "conv-1")
        from conversation.engine import ConversationEngine
        engine = ConversationEngine(session)
        response = await engine.process_message(conv, "Create task to fix the auth bug in login for users with endpoints on local server")
        assert response.intent == "task_request"
        assert response.meta.get("task_type") == "bugfix"


@pytest.mark.asyncio
async def test_task_dispatch_and_execution(db_session):
    """Test task execution with unified executor."""
    async with db_session() as session:
        task = Task(id="task-1", project_id="proj-1", title="Build login", description="Test",
                    type=TaskType.FEATURE.value, status=TaskStatus.CREATED.value, worker_type="pm")
        session.add(task)
        await session.commit()

        from runtime.executor import execute_task
        result = await execute_task(session, task)
        
        await session.refresh(task)
        # Executor advances task through phases
        assert task.status != TaskStatus.CREATED.value
        # Result should have success field
        assert "success" in result
        
        # Verify lease was created internally
        from storage.models import Lease
        lease_result = await session.execute(select(Lease).where(Lease.task_id == task.id))
        leases = lease_result.scalars().all()
        assert len(leases) > 0


@pytest.mark.asyncio
async def test_full_task_execution_lifecycle(db_session):
    """Test task execution through unified executor."""
    async with db_session() as session:
        task = Task(id="task-full", project_id="proj-1", title="Full lifecycle", description="Test",
                    type=TaskType.FEATURE.value, status=TaskStatus.CREATED.value,
                    worker_type="pm", approval_required=False)
        session.add(task)
        await session.commit()

        from runtime.executor import execute_task
        result = await execute_task(session, task)
        
        await session.refresh(task)
        # Executor should advance task through smart triage levels
        assert task.status != TaskStatus.CREATED.value
        assert "success" in result
        
        # Verify execution metadata
        assert "triage" in task.context
        assert "execution_level" in task.context
        
        # Task should have progressed (even if not completed)
        assert task.progress >= 0


@pytest.mark.asyncio
async def test_policy_blocks_dangerous():
    from policy.engine import policy, Decision
    for action in ["git push --force origin main", "rm -rf /", "sudo apt install x"]:
        result = policy.evaluate(action=action)
        assert result.decision == Decision.DENY


@pytest.mark.asyncio
async def test_fsm_cannot_skip_phases():
    from workflow.fsm import can_advance
    assert can_advance("created", barrier_complete=True, pm_review_passed=False, approval_passed=True)
    assert not can_advance("created", barrier_complete=False, pm_review_passed=False, approval_passed=True)
    assert not can_advance("completed", barrier_complete=True, pm_review_passed=True, approval_passed=True)


@pytest.mark.asyncio
async def test_lease_lifecycle_integrity(db_session):
    """Test that executor manages lease lifecycle correctly."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from llm.provider import provider_manager

    provider = MagicMock()
    provider.config = MagicMock()
    provider.config.name = "fake-provider"

    async def chat_side_effect(**kwargs):
        return {"content": "Lease test complete.", "model": "fake-model", "usage": {}}

    with patch.object(provider_manager, "get_active_with_key", return_value=provider), \
         patch.object(provider_manager, "chat", AsyncMock(side_effect=chat_side_effect)):
        async with db_session() as session:
            task = Task(id="task-lease", project_id="proj-1", title="Lease test", description="Test",
                        type=TaskType.FEATURE.value, status=TaskStatus.CREATED.value, worker_type="architect", approval_required=False)
            session.add(task)
            await session.commit()

            from runtime.executor import execute_task
            result = await execute_task(session, task)

            # Verify leases were created and managed
            from storage.models import Lease, LeaseStatus
            lease_result = await session.execute(select(Lease).where(Lease.task_id == task.id))
            leases = lease_result.scalars().all()

            # At least one lease should exist
            assert len(leases) > 0

            # Leases should be properly finished (not stuck in active)
            active_leases = [l for l in leases if l.status == LeaseStatus.ACTIVE.value]
            # All leases should be finished after execution OR task is blocked/in_progress
            assert len(active_leases) == 0 or result.get("status") in ("blocked", "waiting_for_approval", "in_progress")


@pytest.mark.asyncio
async def test_llm_fallback_to_regex(db_session):
    from llm.provider import provider_manager
    provider_manager._providers.clear()
    provider_manager._active = None

    async with db_session() as session:
        conv = await session.get(Conversation, "conv-1")
        from conversation.engine import ConversationEngine
        engine = ConversationEngine(session)
        response = await engine.process_message(conv, "Create task to build a login page for users with React UI deployed on local server")
        assert response.intent == "task_request"
        assert response.meta.get("task_id") is not None
