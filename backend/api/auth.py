"""
Authentication API endpoints.
"""
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import (
    verify_password, create_access_token, create_refresh_token,
    decode_token, get_password_hash, get_current_user
)
from core.config import get_settings
from services.audit import get_audit_service
from models import User
from schemas import (
    LoginRequest, Token, RefreshRequest, UserResponse, UserCreate
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
settings = get_settings()
security = HTTPBearer()


@router.post("/login", response_model=Token)
def login(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
) -> Any:
    """Authenticate user and return JWT tokens."""
    user = db.query(User).filter(User.email == login_data.email).first()
    
    if not user or not verify_password(login_data.password, user.password_hash):
        get_audit_service().log_action(
            user_id=None,
            action_type="login",
            request=request,
            metadata={"email": login_data.email, "success": False, "reason": "invalid_credentials"},
            response_status=401
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if user.status != "active":
        get_audit_service().log_action(
            user_id=user.user_id,
            action_type="login",
            request=request,
            metadata={"success": False, "reason": "account_inactive"},
            response_status=403
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive or suspended"
        )
    
    # Check MFA if enabled
    if user.mfa_enabled:
        if not login_data.mfa_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="MFA code required"
            )
        # TODO: Implement MFA verification
    
    # Update last login
    from datetime import datetime
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Generate tokens
    access_token = create_access_token(
        data={"sub": str(user.user_id), "role": user.role}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.user_id)}
    )
    
    get_audit_service().log_action(
        user_id=user.user_id,
        action_type="login",
        request=request,
        metadata={"success": True},
        response_status=200
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.post("/refresh", response_model=Token)
def refresh_token(
    request: Request,
    refresh_data: RefreshRequest,
    db: Session = Depends(get_db)
) -> Any:
    """Refresh access token using refresh token."""
    payload = decode_token(refresh_data.refresh_token)
    
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.user_id == int(user_id)).first()
    
    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    access_token = create_access_token(
        data={"sub": str(user.user_id), "role": user.role}
    )
    new_refresh_token = create_refresh_token(
        data={"sub": str(user.user_id)}
    )
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.post("/logout")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Logout current user (invalidate token on client side)."""
    get_audit_service().log_action(
        user_id=current_user.user_id,
        action_type="logout",
        request=request
    )
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return current_user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: Request,
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Register a new user (admin only in production)."""
    # Check if email exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        role=user_data.role,
        department=user_data.department
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    get_audit_service().log_action(
        user_id=user.user_id,
        action_type="config_change",
        resource_type="user",
        resource_id=str(user.user_id),
        request=request,
        metadata={"action": "user_created"}
    )
    
    return user
