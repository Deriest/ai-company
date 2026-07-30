"""Session manager — durable, project-scoped conversations.

Sessions are:
- Durable: stored in SQLite, survive restarts
- Project-scoped: tied to a specific project directory
- Event-logged: all state changes are recorded
- Resumable: can continue from where they left off
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

from storage.models import Conversation, Message, Event as EventModel

logger = logging.getLogger("aic.session")


class SessionManager:
    """Manage durable, project-scoped sessions."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_session(
        self,
        title: str = "New Session",
        project_id: Optional[str] = None,
        agent_mode: str = "build",
    ) -> Conversation:
        """Create a new session tied to a project."""
        now = datetime.now(timezone.utc)
        conv = Conversation(
            title=title,
            project_id=project_id,
            is_archived=False,
            is_favorite=False,
            created_at=now,
            updated_at=now,
        )
        self.db.add(conv)
        await self.db.flush()
        
        # Log session creation event
        await self._log_event(
            event_type="session.created",
            target=f"session:{conv.id}",
            data={"title": title, "project_id": project_id, "agent_mode": agent_mode}
        )
        
        await self.db.commit()
        return conv
    
    async def get_session(self, session_id: str) -> Optional[Conversation]:
        """Get a session by ID."""
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == session_id)
        )
        return result.scalar_one_or_none()
    
    async def list_sessions(
        self,
        project_id: Optional[str] = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[Conversation]:
        """List sessions, optionally filtered by project."""
        query = select(Conversation).order_by(desc(Conversation.updated_at))
        if not include_archived:
            query = query.where(Conversation.is_archived == False)
        if project_id:
            query = query.where(Conversation.project_id == project_id)
        query = query.limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict = None,
    ) -> Message:
        """Add a message to a session."""
        now = datetime.now(timezone.utc)
        msg = Message(
            conversation_id=session_id,
            role=role,
            content=content,
            created_at=now,
            updated_at=now,
        )
        if metadata:
            msg.message_metadata = metadata
        self.db.add(msg)
        
        # Update session timestamp
        session = await self.get_session(session_id)
        if session:
            session.updated_at = now
        
        await self.db.flush()
        return msg
    
    async def get_messages(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Message]:
        """Get messages for a session."""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == session_id)
            .order_by(Message.created_at)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def archive_session(self, session_id: str) -> bool:
        """Archive a session."""
        session = await self.get_session(session_id)
        if not session:
            return False
        session.is_archived = True
        await self._log_event(
            event_type="session.archived",
            target=f"session:{session_id}",
            data={}
        )
        await self.db.commit()
        return True
    
    async def _log_event(
        self,
        event_type: str,
        target: str,
        data: dict,
    ) -> None:
        """Log an event to the event table."""
        event = EventModel(
            type=event_type,
            actor="system",
            target=target,
            data=data,
            severity="info",
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(event)


class SessionContext:
    """Context for a specific session — what the workers need to know."""
    
    def __init__(self, session: Conversation, messages: list[Message], project_root: str = "."):
        self.session = session
        self.messages = messages
        self.project_root = project_root
    
    @property
    def session_id(self) -> str:
        return self.session.id
    
    @property
    def project_id(self) -> Optional[str]:
        return self.session.project_id
    
    def get_recent_messages(self, limit: int = 20) -> list[dict]:
        """Get recent messages as dicts for LLM context."""
        return [
            {"role": m.role, "content": m.content}
            for m in self.messages[-limit:]
        ]
    
    def get_conversation_summary(self) -> str:
        """Get a brief summary of the conversation."""
        if not self.messages:
            return "No messages yet."
        user_msgs = [m for m in self.messages if m.role == "user"]
        asst_msgs = [m for m in self.messages if m.role == "assistant"]
        return f"{len(user_msgs)} user messages, {len(asst_msgs)} assistant responses"
