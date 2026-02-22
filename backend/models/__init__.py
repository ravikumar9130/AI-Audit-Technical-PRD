"""
SQLAlchemy models for Audit AI database.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, Enum, BigInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID, INET
from sqlalchemy.orm import relationship
import uuid

from core.database import Base


class User(Base):
    __tablename__ = "users"
    
    user_id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    role = Column(Enum("Agent", "Manager", "CXO", "Admin", name="user_role"), nullable=False, default="Agent")
    department = Column(String(100))
    manager_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    status = Column(Enum("active", "inactive", "suspended", name="user_status"), nullable=False, default="active")
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255))
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    calls = relationship("Call", back_populates="user")
    manager = relationship("User", remote_side=[user_id])
    templates = relationship("ScoringTemplate", back_populates="created_by_user")


class Client(Base):
    __tablename__ = "clients"
    
    client_id = Column(Integer, primary_key=True, index=True)
    org_name = Column(String(255), nullable=False)
    api_key_hash = Column(String(255))
    retention_days = Column(Integer, default=2555)
    data_classification = Column(String(50), default="standard")
    gdpr_enabled = Column(Boolean, default=True)
    hipaa_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ScoringTemplate(Base):
    __tablename__ = "scoring_templates"
    
    template_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    vertical = Column(Enum("Sales", "Support", "Collections", name="vertical_type"), nullable=False)
    system_prompt = Column(Text, nullable=False)
    user_prompt_template = Column(Text, nullable=False)
    json_schema = Column(JSONB, nullable=False)
    scoring_weights = Column(JSONB, nullable=False)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.user_id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    created_by_user = relationship("User", back_populates="templates")
    calls = relationship("Call", back_populates="template")


class Call(Base):
    __tablename__ = "calls"
    
    call_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.client_id"))
    template_id = Column(Integer, ForeignKey("scoring_templates.template_id"))
    batch_id = Column(UUID(as_uuid=True))
    s3_path = Column(String(500), nullable=False)
    original_filename = Column(String(255))
    file_size_bytes = Column(BigInteger)
    duration_seconds = Column(Integer)
    status = Column(Enum("queued", "processing", "completed", "failed", "cancelled", name="call_status"), default="queued")
    processing_started_at = Column(DateTime)
    processing_completed_at = Column(DateTime)
    error_message = Column(Text)
    extra_metadata = Column(JSONB, name="metadata")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="calls")
    template = relationship("ScoringTemplate", back_populates="calls")
    transcript_segments = relationship("Transcript", back_populates="call", cascade="all, delete-orphan")
    evaluation = relationship("EvaluationResult", back_populates="call", uselist=False, cascade="all, delete-orphan")

    @property
    def meta(self):
        return self.extra_metadata


class MediaFile(Base):
    __tablename__ = "media_files"
    
    media_id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.call_id"), nullable=False, index=True)
    s3_key = Column(String(500), nullable=False)
    file_format = Column(String(20))
    sample_rate = Column(Integer)
    channels = Column(Integer)
    duration_seconds = Column(Integer)
    file_size_bytes = Column(BigInteger)
    checksum = Column(String(64))
    encryption_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Transcript(Base):
    __tablename__ = "transcripts"
    
    transcript_id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.call_id"), nullable=False, index=True)
    speaker_label = Column(String(50), nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    text = Column(Text, nullable=False)
    confidence = Column(Float)
    emotion = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    call = relationship("Call", back_populates="transcript_segments")


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"
    
    result_id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.call_id"), nullable=False, unique=True, index=True)
    
    # Overall scores
    overall_score = Column(Float, nullable=False)
    ses_score = Column(Float)  # Sales Excellence Score
    sqs_score = Column(Float)  # Service Quality Score
    res_score = Column(Float)  # Recovery Efficiency Score
    
    # Pillar scores
    pillar_scores = Column(JSONB)
    
    # Compliance
    compliance_flags = Column(JSONB)
    fatal_flaw_detected = Column(Boolean, default=False)
    fatal_flaw_type = Column(String(100))
    
    # AI Analysis
    summary = Column(Text)
    recommendations = Column(JSONB)
    sentiment_score = Column(Float)
    
    # Raw output
    full_json_output = Column(JSONB, nullable=False)
    prompt_version = Column(Integer)
    model_used = Column(String(100))
    
    # Processing metadata
    processing_duration_seconds = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    call = relationship("Call", back_populates="evaluation")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    
    job_id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.call_id"), nullable=False, index=True)
    stage = Column(Enum("uploaded", "normalization", "vad", "diarization", 
                        "transcription", "scoring", "completed", "failed", 
                        name="pipeline_stage"), nullable=False)
    status = Column(String(50), nullable=False)
    celery_task_id = Column(String(255))
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    error_message = Column(Text)
    extra_metadata = Column(JSONB, name="metadata")
    created_at = Column(DateTime, default=datetime.utcnow)


class Batch(Base):
    __tablename__ = "batches"
    
    batch_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.client_id"))
    num_calls = Column(Integer, nullable=False)
    num_completed = Column(Integer, default=0)
    num_failed = Column(Integer, default=0)
    status = Column(String(50), default="processing")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    log_id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), index=True)
    client_id = Column(Integer, ForeignKey("clients.client_id"))
    action_type = Column(Enum("login", "logout", "upload", "view", "delete", 
                              "download", "api_call", "config_change", "data_export",
                              name="audit_action"), nullable=False)
    resource_type = Column(String(100))
    resource_id = Column(String(100))
    ip_address = Column(INET)
    user_agent = Column(Text)
    request_path = Column(String(500))
    request_method = Column(String(10))
    response_status = Column(Integer)
    extra_metadata = Column(JSONB, name="metadata")
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"
    
    metric_id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    call_id = Column(Integer, ForeignKey("calls.call_id"), index=True)
    stage = Column(String(50))
    extra_metadata = Column(JSONB, name="metadata")
    recorded_at = Column(DateTime, default=datetime.utcnow)


class RetentionSchedule(Base):
    __tablename__ = "retention_schedule"
    
    schedule_id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.call_id"), nullable=False, index=True)
    scheduled_deletion_at = Column(DateTime, nullable=False, index=True)
    reason = Column(String(100))
    status = Column(String(50), default="pending")
    executed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
