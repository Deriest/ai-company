from pydantic import BaseModel
from typing import List, Optional

class ProviderCreate(BaseModel):
    name: str
    base_url: str
    api_key: str

class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    enabled: Optional[bool] = None

class ProviderResponse(BaseModel):
    id: str
    name: str
    base_url: str
    api_key: str
    enabled: bool
    
    model_config = {"from_attributes": True}

class WorkerRuntimeUpdate(BaseModel):
    provider_id: str
    model_id: str
    temperature: float = 0.4
    top_p: float = 1.0
    max_output_tokens: Optional[int] = None

class WorkerRuntimeResponse(BaseModel):
    id: str
    role: str
    provider_id: Optional[str]
    model_id: Optional[str]
    temperature: float
    top_p: float
    max_output_tokens: Optional[int]

    model_config = {"from_attributes": True}
from typing import Optional, List
from pydantic import BaseModel

class SettingsUpdate(BaseModel):
    crash_reports: Optional[bool] = None
    diagnostics: Optional[bool] = None
    performance: Optional[bool] = None
    usage_analytics: Optional[bool] = None
    session_timeout: Optional[int] = None

class SettingsResponse(BaseModel):
    crash_reports: bool
    diagnostics: bool
    performance: bool
    usage_analytics: bool
    session_timeout: int

    model_config = {"from_attributes": True}

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None

class CompanyResponse(BaseModel):
    id: str
    name: str
    slug: str
    language: str
    timezone: str

    model_config = {"from_attributes": True}

class AuthUserResponse(BaseModel):
    id: str
    username: str
    email: str
    display_name: str
    email_verified: bool
    created_at: str

    model_config = {"from_attributes": True}

class SessionResponse(BaseModel):
    id: str
    device: str
    location: str
    os: str
    last_active: str
    current: bool

    model_config = {"from_attributes": True}
