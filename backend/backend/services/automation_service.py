"""
Automation Service.

Event hooks, triggers, notifications, and scheduled task management.
"""

import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from storage.models import EventHook, Trigger, Notification


class AutomationService:
    """Event hooks, triggers, and notifications."""

    # ── Event Hooks ───────────────────────────────────────────

    @staticmethod
    async def create_hook(
        db: AsyncSession, event_type: str, name: str, action_type: str,
        action_config: dict, description: str = "",
    ) -> EventHook:
        hook = EventHook(
            event_type=event_type, name=name, action_type=action_type,
            action_config=action_config, description=description,
        )
        db.add(hook)
        await db.commit()
        await db.refresh(hook)
        return hook

    @staticmethod
    async def list_hooks(db: AsyncSession, event_type: Optional[str] = None) -> list[EventHook]:
        query = select(EventHook).where(EventHook.is_enabled == True)
        if event_type:
            query = query.where(EventHook.event_type == event_type)
        res = await db.execute(query.order_by(EventHook.name))
        return list(res.scalars().all())

    @staticmethod
    async def fire_hook(db: AsyncSession, hook_id: str) -> EventHook:
        res = await db.execute(select(EventHook).where(EventHook.id == hook_id))
        hook = res.scalars().first()
        if hook:
            hook.fire_count += 1
            hook.last_fired_at = datetime.datetime.now(datetime.timezone.utc)
            await db.commit()
            await db.refresh(hook)
        return hook

    @staticmethod
    async def fire_event(db: AsyncSession, event_type: str, context: dict = None) -> list[EventHook]:
        """Fire all hooks registered for an event type.

        Runs on its OWN session (never the passed ``db``). The runtime executor
        calls this from inside its FSM loop — if a hook committed the executor's
        session mid-loop it would poison the pending transaction (e.g. the
        pending Lease insert). Opening a dedicated session keeps the caller's
        session clean while preserving the commit/refresh behavior of the hook
        machinery.
        """
        from backend.database.session import AsyncSessionLocal
        async with AsyncSessionLocal() as hook_session:
            hooks = await AutomationService.list_hooks(hook_session, event_type)
            fired = []
            for hook in hooks:
                await AutomationService.fire_hook(hook_session, hook.id)
                # Create notification if action_type is notify
                if hook.action_type == "notify":
                    await AutomationService.create_notification(
                        hook_session,
                        title=f"Event: {event_type}",
                        message=hook.action_config.get("message", f"Hook '{hook.name}' fired"),
                        level=hook.action_config.get("level", "info"),
                        source=f"hook:{hook.id}",
                    )
                fired.append(hook)
            return fired

    @staticmethod
    async def delete_hook(db: AsyncSession, hook_id: str):
        res = await db.execute(select(EventHook).where(EventHook.id == hook_id))
        hook = res.scalars().first()
        if hook:
            await db.delete(hook)
            await db.commit()

    # ── Triggers ──────────────────────────────────────────────

    @staticmethod
    async def create_trigger(
        db: AsyncSession, name: str, condition: dict, action: dict, description: str = "",
    ) -> Trigger:
        trigger = Trigger(name=name, condition=condition, action=action, description=description)
        db.add(trigger)
        await db.commit()
        await db.refresh(trigger)
        return trigger

    @staticmethod
    async def list_triggers(db: AsyncSession) -> list[Trigger]:
        res = await db.execute(select(Trigger).where(Trigger.is_enabled == True).order_by(Trigger.name))
        return list(res.scalars().all())

    @staticmethod
    async def evaluate_trigger(db: AsyncSession, trigger_id: str, context: dict) -> bool:
        res = await db.execute(select(Trigger).where(Trigger.id == trigger_id))
        trigger = res.scalars().first()
        if not trigger:
            return False

        cond = trigger.condition
        field = cond.get("field", "")
        op = cond.get("op", "eq")
        value = cond.get("value", "")
        actual = context.get(field, "")

        met = False
        if op == "eq":
            met = str(actual) == str(value)
        elif op == "neq":
            met = str(actual) != str(value)
        elif op == "contains":
            met = str(value) in str(actual)
        elif op == "gt":
            met = float(actual) > float(value) if actual else False
        elif op == "lt":
            met = float(actual) < float(value) if actual else False

        if met:
            trigger.fire_count += 1
            trigger.last_fired_at = datetime.datetime.now(datetime.timezone.utc)
            await db.commit()

        return met

    @staticmethod
    async def delete_trigger(db: AsyncSession, trigger_id: str):
        res = await db.execute(select(Trigger).where(Trigger.id == trigger_id))
        trigger = res.scalars().first()
        if trigger:
            await db.delete(trigger)
            await db.commit()

    # ── Notifications ─────────────────────────────────────────

    @staticmethod
    async def create_notification(
        db: AsyncSession, title: str, message: str, level: str = "info",
        source: str = "", action_url: str = "",
    ) -> Notification:
        notif = Notification(
            title=title, message=message, level=level,
            source=source, action_url=action_url,
        )
        db.add(notif)
        await db.commit()
        await db.refresh(notif)
        return notif

    @staticmethod
    async def list_notifications(
        db: AsyncSession, is_read: Optional[bool] = None, limit: int = 50
    ) -> list[Notification]:
        query = select(Notification).order_by(Notification.created_at.desc()).limit(limit)
        if is_read is not None:
            query = query.where(Notification.is_read == is_read)
        res = await db.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def mark_read(db: AsyncSession, notif_id: str) -> Notification:
        res = await db.execute(select(Notification).where(Notification.id == notif_id))
        notif = res.scalars().first()
        if notif:
            notif.is_read = True
            await db.commit()
            await db.refresh(notif)
        return notif

    @staticmethod
    async def mark_all_read(db: AsyncSession):
        res = await db.execute(select(Notification).where(Notification.is_read == False))
        for n in res.scalars().all():
            n.is_read = True
        await db.commit()


automation_service = AutomationService()
