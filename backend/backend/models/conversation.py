from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Float, JSON, Index, Table, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database.session import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class ConversationFolder(Base):
    __tablename__ = "conversation_folders"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ConversationTag(Base):
    __tablename__ = "conversation_tags"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    tag = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ConversationPin(Base):
    __tablename__ = "conversation_pins"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    pinned_at = Column(DateTime(timezone=True), server_default=func.now())

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, nullable=False, default="New Conversation")
    folder_id = Column(String, ForeignKey("conversation_folders.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = Column(String, nullable=True, index=True)
    is_archived = Column(Boolean, default=False, index=True)
    is_favorite = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False, index=True) # user, assistant, system, tool, developer
    content = Column(String, nullable=False)
    message_metadata = Column("metadata", JSON, nullable=True)  # maps to 'metadata' column in DB
    token_count = Column(Integer, nullable=True)
    model_id = Column(String, nullable=True)
    provider_id = Column(String, nullable=True)
    status = Column(String, default="completed") # pending, streaming, completed, error
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

class Attachment(Base):
    __tablename__ = "attachments"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    message_id = Column(String, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False) # images, pdf, markdown, json, text, code, binary
    mime_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    attachment_metadata = Column(JSON, nullable=True) # width, height, pages, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
