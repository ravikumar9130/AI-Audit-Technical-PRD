"""
Audit logging service for SOC2 compliance.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import Request

from core.database import get_db_context
from models import AuditLog
from core.config import get_settings

settings = get_settings()


class AuditService:
    """Service for audit logging."""
    
    @staticmethod
    def log_action(
        user_id: Optional[int],
        action_type: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        request: Optional[Request] = None,
        metadata: Optional[Dict[str, Any]] = None,
        client_id: Optional[int] = None,
        response_status: Optional[int] = None
    ):
        """Log an action to the audit log."""
        if not settings.ENABLE_AUDIT_LOGGING:
            return
        
        ip_address = None
        user_agent = None
        request_path = None
        request_method = None
        
        if request:
            # Get client IP
            if request.headers.get("X-Forwarded-For"):
                ip_address = request.headers.get("X-Forwarded-For").split(",")[0].strip()
            else:
                ip_address = request.client.host if request.client else None
            
            user_agent = request.headers.get("User-Agent")
            request_path = str(request.url.path)
            request_method = request.method
        
        try:
            with get_db_context() as db:
                log_entry = AuditLog(
                    user_id=user_id,
                    client_id=client_id,
                    action_type=action_type,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_path=request_path,
                    request_method=request_method,
                    response_status=response_status,
                    extra_metadata=metadata
                )
                db.add(log_entry)
        except Exception as e:
            # Don't let audit logging failures break the application
            print(f"Failed to write audit log: {e}")


# Singleton
_audit_service: Optional[AuditService] = None


def get_audit_service() -> AuditService:
    """Get audit service singleton."""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service
