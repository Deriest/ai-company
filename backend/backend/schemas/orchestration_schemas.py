from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class OrchestrationSessionCreate(BaseModel):
    conversation_id: str
    mode: str = "sequential"  # sequential, parallel


class OrchestrationTaskCreate(BaseModel):
    worker_role: str
    title: str
    description: str = ""
    input_context: Optional[Dict[str, Any]] = None
    depends_on: Optional[List[str]] = None


class ApprovalResolve(BaseModel):
    approved: bool
    notes: str = ""
