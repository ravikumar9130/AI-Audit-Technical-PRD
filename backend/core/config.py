"""
Core configuration module for Audit AI backend.
"""
import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "Audit AI"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    ALLOWED_ORIGINS: list = ["http://localhost:3000", "https://localhost:3000", "http://127.0.0.1:3000"]
    
    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL connection URL")
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Redis
    REDIS_URL: str = Field(..., description="Redis connection URL")
    REDIS_POOL_SIZE: int = 50
    
    # MinIO / S3
    MINIO_ENDPOINT: str = Field(..., description="MinIO server endpoint")
    MINIO_ACCESS_KEY: str = Field(..., description="MinIO access key")
    MINIO_SECRET_KEY: str = Field(..., description="MinIO secret key")
    MINIO_BUCKET: str = "auditai-calls"
    MINIO_SECURE: bool = False
    MINIO_REGION: str = "us-east-1"
    
    # AWS S3 Alternative
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: Optional[str] = None
    
    # JWT Authentication
    JWT_SECRET: str = Field(..., min_length=32, description="JWT signing secret")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # LLM Configuration (required only for worker; API can start without it)
    LLM_MODEL_PATH: str = Field(default="/app/ml-models/llama-3-8b-instruct-q4.gguf", description="Path to local LLM model")
    LLM_MODEL_NAME: str = "llama-3-8b-instruct"
    VLLM_GPU_MEMORY_UTILIZATION: float = 0.85
    VLLM_MAX_MODEL_LEN: int = 4096
    VLLM_TENSOR_PARALLEL_SIZE: int = 1
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2048
    LLM_MAX_TOKENS_CPU: int = 768
    LLM_TOP_P: float = 0.9
    TRANSCRIPT_MAX_CHARS: int = 12000
    
    # Audio Processing
    AUDIO_SAMPLE_RATE: int = 16000
    AUDIO_CHANNELS: int = 1
    AUDIO_FORMAT: str = "pcm_s16le"
    VAD_CONFIDENCE_THRESHOLD: float = 0.5
    VAD_HANGOVER_MS: int = 250
    
    # Security
    ENABLE_AUDIT_LOGGING: bool = True
    AUDIT_LOG_RETENTION_DAYS: int = 2555
    DATA_RETENTION_DAYS: int = 2555
    PII_REDACTION_ENABLED: bool = True
    ENCRYPTION_KEY: Optional[str] = None
    
    # Rate Limiting
    RATE_LIMIT_UPLOADS_PER_MINUTE: int = 10
    RATE_LIMIT_API_CALLS_PER_MINUTE: int = 100
    
    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_MAX_CONNECTIONS: int = 1000
    
    # Monitoring
    PROMETHEUS_ENABLED: bool = False
    SENTRY_DSN: Optional[str] = None
    
    @validator("DATABASE_URL", pre=True)
    def validate_database_url(cls, v):
        if not v:
            raise ValueError("DATABASE_URL is required")
        return v
    
    @validator("JWT_SECRET", pre=True)
    def validate_jwt_secret(cls, v):
        if not v or len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
