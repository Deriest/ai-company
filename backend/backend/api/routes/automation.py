from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from backend.database.session import get_db

router = APIRouter()

from backend.services.automation_service import automation_service


# ── Automation Endpoints ─────────────────────────────────────

@router.post("/hooks")
async def create_hook(payload: dict, db: AsyncSession = Depends(get_db)):
    event_type = payload.get("event_type")
    name = payload.get("name")
    action_type = payload.get("action_type")
    if not event_type or not name or not action_type:
        raise HTTPException(status_code=400, detail="event_type, name and action_type are required")
    hook = await automation_service.create_hook(
        db, event_type=event_type, name=name,
        action_type=action_type, action_config=payload.get("action_config", {}),
        description=payload.get("description", ""),
    )
    return {"id": hook.id, "name": hook.name, "eventType": hook.event_type, "actionType": hook.action_type}

@router.get("/hooks")
async def list_hooks(event_type: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    hooks = await automation_service.list_hooks(db, event_type)
    return [
        {"id": h.id, "name": h.name, "eventType": h.event_type, "actionType": h.action_type,
         "isEnabled": h.is_enabled, "fireCount": h.fire_count}
        for h in hooks
    ]

@router.delete("/hooks/{hook_id}")
async def delete_hook(hook_id: str, db: AsyncSession = Depends(get_db)):
    await automation_service.delete_hook(db, hook_id)
    return {"status": "ok"}

@router.post("/hooks/fire/{event_type}")
async def fire_event(event_type: str, db: AsyncSession = Depends(get_db)):
    fired = await automation_service.fire_event(db, event_type)
    return {"fired": len(fired)}

@router.post("/triggers")
async def create_trigger(payload: dict, db: AsyncSession = Depends(get_db)):
    name = payload.get("name")
    condition = payload.get("condition")
    action = payload.get("action")
    if not name or not condition or not action:
        raise HTTPException(status_code=400, detail="name, condition and action are required")
    trigger = await automation_service.create_trigger(
        db, name=name, condition=condition,
        action=action, description=payload.get("description", ""),
    )
    return {"id": trigger.id, "name": trigger.name}

@router.get("/triggers")
async def list_triggers(db: AsyncSession = Depends(get_db)):
    triggers = await automation_service.list_triggers(db)
    return [
        {"id": t.id, "name": t.name, "condition": t.condition, "action": t.action,
         "isEnabled": t.is_enabled, "fireCount": t.fire_count}
        for t in triggers
    ]

@router.delete("/triggers/{trigger_id}")
async def delete_trigger(trigger_id: str, db: AsyncSession = Depends(get_db)):
    await automation_service.delete_trigger(db, trigger_id)
    return {"status": "ok"}

@router.get("/notifications")
async def list_notifications(is_read: Optional[bool] = Query(None), db: AsyncSession = Depends(get_db)):
    notifs = await automation_service.list_notifications(db, is_read)
    return [
        {"id": n.id, "title": n.title, "message": n.message, "level": n.level,
         "source": n.source, "isRead": n.is_read, "createdAt": n.created_at.isoformat()}
        for n in notifs
    ]

@router.patch("/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: str, db: AsyncSession = Depends(get_db)):
    notif = await automation_service.mark_read(db, notif_id)
    return {"id": notif.id, "isRead": notif.is_read}

@router.post("/notifications/read-all")
async def mark_all_notifications_read(db: AsyncSession = Depends(get_db)):
    await automation_service.mark_all_read(db)
    return {"status": "ok"}
