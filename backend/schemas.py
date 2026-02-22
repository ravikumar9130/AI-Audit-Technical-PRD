"""
Pydantic schemas for API request/response validation.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from enum import Enum


# Enums
class UserRole(str, Enum):
    AGENT = "Agent"
    MANAGER = "Manager"
    CXO = "CXO"
    ADMIN = "Admin"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class CallStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VerticalType(str, Enum):
    SALES = "Sales"
    SUPPORT = "Support"
    COLLECTIONS = "Collections"


# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    department: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None


class UserResponse(UserBase):
    user_id: int
    status: UserStatus
    last_login: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# Auth Schemas
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    type: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    mfa_code: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


# Call Schemas
class CallCreate(BaseModel):
    template_id: int
    metadata: Optional[Dict[str, Any]] = None


class CallResponse(BaseModel):
    call_id: int
    user_id: int
    template_id: Optional[int]
    batch_id: Optional[str]
    s3_path: str
    original_filename: Optional[str]
    file_size_bytes: Optional[int]
    duration_seconds: Optional[int]
    status: CallStatus
    processing_started_at: Optional[datetime]
    processing_completed_at: Optional[datetime]
    error_message: Optional[str]
    meta: Optional[Dict[str, Any]] = Field(default=None, serialization_alias="metadata")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CallListResponse(BaseModel):
    calls: List[CallResponse]
    total: int
    page: int
    page_size: int


# Transcript Schemas
class TranscriptSegment(BaseModel):
    transcript_id: int
    speaker_label: str
    start_time: float
    end_time: float
    text: str
    confidence: Optional[float]
    emotion: Optional[str]


class TranscriptResponse(BaseModel):
    call_id: int
    segments: List[TranscriptSegment]
    full_text: str


# Evaluation Schemas
class EvaluationResponse(BaseModel):
    result_id: int
    call_id: int
    overall_score: float
    ses_score: Optional[float]
    sqs_score: Optional[float]
    res_score: Optional[float]
    pillar_scores: Optional[Dict[str, float]]
    compliance_flags: Optional[Dict[str, Any]]
    fatal_flaw_detected: bool
    fatal_flaw_type: Optional[str]
    summary: Optional[str]
    recommendations: Optional[List[str]]
    sentiment_score: Optional[float]
    full_json_output: Dict[str, Any]
    model_used: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Template Schemas
class ScoringTemplateCreate(BaseModel):
    name: str
    vertical: VerticalType
    system_prompt: str
    user_prompt_template: str
    json_schema: Dict[str, Any]
    scoring_weights: Dict[str, float]


class ScoringTemplateUpdate(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    json_schema: Optional[Dict[str, Any]] = None
    scoring_weights: Optional[Dict[str, float]] = None
    is_active: Optional[bool] = None


class ScoringTemplateResponse(BaseModel):
    template_id: int
    name: str
    vertical: VerticalType
    system_prompt: str
    user_prompt_template: str
    json_schema: Dict[str, Any]
    scoring_weights: Dict[str, float]
    version: int
    is_active: bool
    created_by: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Dashboard Schemas
class DashboardMetrics(BaseModel):
    total_calls: int
    avg_score: float
    completed_calls: int
    failed_calls: int
    processing_calls: int


class AgentDashboard(BaseModel):
    user: UserResponse
    metrics: DashboardMetrics
    recent_calls: List[CallResponse]
    trend_data: List[Dict[str, Any]]


class ManagerDashboard(BaseModel):
    user: UserResponse
    team_metrics: DashboardMetrics
    team_members: List[UserResponse]
    calls_by_agent: List[Dict[str, Any]]
    risk_alerts: List[Dict[str, Any]]
    skill_heatmap: Dict[str, Any]


class CXODashboard(BaseModel):
    user: UserResponse
    company_metrics: DashboardMetrics
    vertical_breakdown: Dict[str, Any]
    revenue_forecast: Optional[Dict[str, Any]]
    compliance_summary: Dict[str, Any]
    top_issues: List[Dict[str, Any]]


# Upload Schemas
class UploadResponse(BaseModel):
    call_id: int
    status: CallStatus
    message: str


class BulkUploadResponse(BaseModel):
    batch_id: str
    num_files: int
    status: str
    message: str


# WebSocket Schemas
class WSMessage(BaseModel):
    type: str
    call_id: Optional[int]
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Audit Log Schemas
class AuditLogResponse(BaseModel):
    log_id: int
    user_id: Optional[int]
    action_type: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    ip_address: Optional[str]
    timestamp: datetime
    
    class Config:
        from_attributes = True


# Error Schemas
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
