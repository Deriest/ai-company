from pydantic import BaseModel
from typing import List, Optional, Any

class ModelCapabilities(BaseModel):
    contextWindow: int
    vision: bool
    toolCalling: bool
    streaming: bool
    reasoning: bool
    functionCalling: bool
    jsonMode: bool
    embedding: bool
    maxOutputTokens: int

class ModelInfo(BaseModel):
    id: str
    name: str
    capabilities: ModelCapabilities

class ProviderTestResponse(BaseModel):
    ok: bool
    latencyMs: Optional[int] = None
    version: Optional[str] = None
    healthNotes: Optional[List[str]] = None
    error: Optional[str] = None
    models: Optional[List[ModelInfo]] = None

class ProviderModelResponse(BaseModel):
    id: str
    name: str
    capabilities: ModelCapabilities

    model_config = {"from_attributes": True}

class ProviderWithModelsResponse(BaseModel):
    id: str
    name: str
    endpoint: str
    apiKey: str
    enabled: bool
    status: str
    latencyMs: int
    version: str
    healthNotes: List[str]
    models: List[ModelInfo]
    modelsCachedAt: Optional[str] = None
    lastRefreshAt: Optional[str] = None

class ProviderCreate(BaseModel):
    name: str
    endpoint: str
    apiKey: str
    latencyMs: Optional[int] = 0
    version: Optional[str] = "1.0"
    healthNotes: Optional[List[str]] = []
    models: Optional[List[Any]] = []
    
class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    endpoint: Optional[str] = None
    apiKey: Optional[str] = None
    enabled: Optional[bool] = None
    status: Optional[str] = None
    latencyMs: Optional[int] = None
    lastRefreshAt: Optional[str] = None
    modelsCachedAt: Optional[str] = None
    healthNotes: Optional[List[str]] = None
    models: Optional[List[Any]] = None

class WorkerRuntimeUpdate(BaseModel):
    providerId: Optional[str] = None
    modelId: Optional[str] = None
    temperature: Optional[float] = None
    topP: Optional[float] = None
    maxOutputTokens: Optional[int] = None
    systemPrompt: Optional[str] = None
    isEnabled: Optional[bool] = None

class WorkerMetricsResponse(BaseModel):
    role: str
    totalExecutions: int = 0
    completed: int = 0
    errors: int = 0
    avgLatencyMs: float = 0.0
    lastExecutedAt: Optional[str] = None
    currentlyRunning: bool = False

class WorkerRuntimeResponse(BaseModel):
    id: str
    role: str
    label: str = ""
    description: str = ""
    systemPrompt: str = ""
    providerId: str
    modelId: str
    temperature: float
    topP: float
    maxOutputTokens: Optional[int] = None
    isEnabled: bool = True
    metrics: Optional[WorkerMetricsResponse] = None

    model_config = {"from_attributes": True}
