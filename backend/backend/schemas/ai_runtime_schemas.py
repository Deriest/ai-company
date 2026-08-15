from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class ChatMessagePayload(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    conversation_id: str
    messages: List[ChatMessagePayload]
    provider_id: Optional[str] = None
    model_id: Optional[str] = None
    worker_role: Optional[str] = "thinker"
    model_tier: Optional[str] = None
    tags: Optional[list[dict]] = None  # frontend can send workflow tags (e.g., {"workflow": "bughunt"})
    attachments: Optional[List[Dict[str, Any]]] = None
    workspace: Optional[str] = None
    temperature: Optional[float] = 0.4
    top_p: Optional[float] = 1.0
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    project_id: Optional[str] = None

    model_config = {"extra": "ignore"}

class ChatCancelRequest(BaseModel):
    message_id: str

class ChatRegenerateRequest(BaseModel):
    conversation_id: str
    message_id: str

class ArtifactResponse(BaseModel):
    id: str
    conversation_id: str
    message_id: Optional[str] = None
    type: str
    title: str
    content: str
    language: Optional[str] = None
    mime_type: str
    created_at: datetime

    model_config = {"from_attributes": True}

class WorkerRuntimeUpdate(BaseModel):
    provider_id: Optional[str] = None
    model_id: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_output_tokens: Optional[int] = None

class ToolExecuteRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
