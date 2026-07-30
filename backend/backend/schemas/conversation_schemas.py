from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class AttachmentCreate(BaseModel):
    file_name: str
    file_type: str
    mime_type: str
    file_size: int
    attachment_metadata: Optional[Dict[str, Any]] = None

class AttachmentResponse(AttachmentCreate):
    id: str
    message_id: str
    created_at: datetime

    model_config = {"from_attributes": True}

class MessageCreate(BaseModel):
    role: str = Field(..., description="user, assistant, system, tool, developer")
    content: str
    message_metadata: Optional[Dict[str, Any]] = None
    token_count: Optional[int] = None
    model_id: Optional[str] = None
    provider_id: Optional[str] = None
    status: Optional[str] = "completed"
    attachments: Optional[List[AttachmentCreate]] = []

class MessageUpdate(BaseModel):
    content: Optional[str] = None
    message_metadata: Optional[Dict[str, Any]] = None
    token_count: Optional[int] = None
    status: Optional[str] = None

class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    message_metadata: Optional[Dict[str, Any]] = None
    token_count: Optional[int] = None
    model_id: Optional[str] = None
    provider_id: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    attachments: List[AttachmentResponse] = []

    model_config = {"from_attributes": True}

class ConversationCreate(BaseModel):
    title: Optional[str] = "New Conversation"
    folder_id: Optional[str] = None
    project_id: Optional[str] = None
    tags: Optional[List[str]] = []

class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    folder_id: Optional[str] = None
    is_archived: Optional[bool] = None
    is_favorite: Optional[bool] = None
    is_pinned: Optional[bool] = None
    tags: Optional[List[str]] = None

class ConversationResponse(BaseModel):
    id: str
    title: str
    folder_id: Optional[str] = None
    project_id: Optional[str] = None
    is_archived: bool
    is_favorite: bool
    is_pinned: bool = False
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class SearchResultItem(BaseModel):
    target_type: str # conversation or message
    target_id: str # conversation_id or message_id
    conversation_id: str
    title: str
    snippet: str
    tags: str

class ImportConversationPayload(BaseModel):
    title: str
    folder_id: Optional[str] = None
    is_archived: Optional[bool] = False
    is_favorite: Optional[bool] = False
    tags: Optional[List[str]] = []
    messages: List[MessageCreate] = []

class ExportConversationPayload(ImportConversationPayload):
    id: str
    created_at: str
    updated_at: str
