from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from backend.database.session import Base
import uuid
from datetime import datetime, timezone

def generate_uuid():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)

class ConversationFolder(Base):
    __tablename__ = "conversation_folders"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), onupdate=utcnow)

class ConversationTag(Base):
    __tablename__ = "conversation_tags"

    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    tag = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now())

class ConversationPin(Base):
    __tablename__ = "conversation_pins"

    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    pinned_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now())


# Conversation folders, tags, pins, and attachments are still owned by the
# backend metadata. Keep this lightweight table mapping so their foreign keys
# resolve. Message persistence is intentionally canonicalized in storage.models.
class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, nullable=False, default="New Conversation")
    folder_id = Column(String, ForeignKey("conversation_folders.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = Column(String, nullable=True, index=True)
    is_archived = Column(Boolean, default=False, index=True)
    is_favorite = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), onupdate=utcnow, index=True)

class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(String, primary_key=True, default=generate_uuid)
    # Messages are canonical storage models, so attachment cleanup is handled
    # by application routes rather than a cross-registry foreign key.
    message_id = Column(String, nullable=False, index=True)
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False) # images, pdf, markdown, json, text, code, binary
    mime_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    attachment_metadata = Column(JSON, nullable=True) # width, height, pages, etc.
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now())
