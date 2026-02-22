"""
Call management API endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc

from core.database import get_db
from core.security import get_current_user, check_permission
from services.audit import get_audit_service
from models import User, Call, Transcript, EvaluationResult, ProcessingJob
from schemas import (
    CallResponse, CallListResponse, TranscriptResponse, 
    TranscriptSegment, EvaluationResponse
)

router = APIRouter(prefix="/api/calls", tags=["Calls"])


@router.get("/", response_model=CallListResponse)
def list_calls(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status"),
    template_id: Optional[int] = Query(None, description="Filter by template"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List calls with RBAC filtering."""
    
    query = db.query(Call)
    
    # RBAC: Agents see only their own calls
    if current_user.role == "Agent":
        query = query.filter(Call.user_id == current_user.user_id)
    # Managers see their team's calls
    elif current_user.role == "Manager":
        team_ids = [current_user.user_id]
        # Get team members
        team_members = db.query(User).filter(User.manager_id == current_user.user_id).all()
        team_ids.extend([m.user_id for m in team_members])
        query = query.filter(Call.user_id.in_(team_ids))
    # CXO and Admin see all calls
    
    # Apply filters
    if status:
        query = query.filter(Call.status == status)
    if template_id:
        query = query.filter(Call.template_id == template_id)
    
    # Order by creation date
    query = query.order_by(desc(Call.created_at))
    
    # Pagination
    total = query.count()
    calls = query.offset((page - 1) * page_size).limit(page_size).all()
    
    # Audit log
    get_audit_service().log_action(
        user_id=current_user.user_id,
        action_type="view",
        resource_type="calls",
        request=request
    )
    
    return {
        "calls": calls,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/{call_id}", response_model=CallResponse)
def get_call(
    request: Request,
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get call details by ID."""
    
    call = db.query(Call).filter(Call.call_id == call_id).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # RBAC check
    if current_user.role == "Agent" and call.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if current_user.role == "Manager":
        team_ids = [current_user.user_id]
        team_members = db.query(User).filter(User.manager_id == current_user.user_id).all()
        team_ids.extend([m.user_id for m in team_members])
        if call.user_id not in team_ids:
            raise HTTPException(status_code=403, detail="Access denied")
    
    get_audit_service().log_action(
        user_id=current_user.user_id,
        action_type="view",
        resource_type="call",
        resource_id=str(call_id),
        request=request
    )
    
    return call


@router.get("/{call_id}/transcript", response_model=TranscriptResponse)
def get_transcript(
    request: Request,
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get transcript for a call."""
    
    call = db.query(Call).filter(Call.call_id == call_id).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # RBAC check
    if current_user.role == "Agent" and call.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    transcripts = db.query(Transcript).filter(
        Transcript.call_id == call_id
    ).order_by(Transcript.start_time).all()
    
    segments = [
        TranscriptSegment(
            transcript_id=t.transcript_id,
            speaker_label=t.speaker_label,
            start_time=t.start_time,
            end_time=t.end_time,
            text=t.text,
            confidence=t.confidence,
            emotion=t.emotion
        )
        for t in transcripts
    ]
    
    full_text = "\n".join([f"[{s.speaker_label}] {s.text}" for s in segments])
    
    get_audit_service().log_action(
        user_id=current_user.user_id,
        action_type="view",
        resource_type="transcript",
        resource_id=str(call_id),
        request=request
    )
    
    return {
        "call_id": call_id,
        "segments": segments,
        "full_text": full_text
    }


@router.get("/{call_id}/results", response_model=EvaluationResponse)
def get_results(
    request: Request,
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get evaluation results for a call."""
    
    call = db.query(Call).filter(Call.call_id == call_id).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    if call.status != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Call processing not completed. Status: {call.status}"
        )
    
    # RBAC check
    if current_user.role == "Agent" and call.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = db.query(EvaluationResult).filter(
        EvaluationResult.call_id == call_id
    ).first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Evaluation results not found")
    
    get_audit_service().log_action(
        user_id=current_user.user_id,
        action_type="view",
        resource_type="evaluation",
        resource_id=str(call_id),
        request=request
    )
    
    return result


@router.get("/{call_id}/jobs")
def get_processing_jobs(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get processing pipeline jobs for a call."""
    
    call = db.query(Call).filter(Call.call_id == call_id).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # RBAC check
    if current_user.role == "Agent" and call.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    jobs = db.query(ProcessingJob).filter(
        ProcessingJob.call_id == call_id
    ).order_by(ProcessingJob.created_at).all()
    
    return {
        "call_id": call_id,
        "jobs": [
            {
                "job_id": j.job_id,
                "stage": j.stage,
                "status": j.status,
                "started_at": j.started_at,
                "finished_at": j.finished_at,
                "error_message": j.error_message
            }
            for j in jobs
        ]
    }


@router.delete("/{call_id}")
def delete_call(
    request: Request,
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a call and associated data."""
    
    if not check_permission(current_user, "calls:delete"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    call = db.query(Call).filter(Call.call_id == call_id).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Only allow deletion by owner, manager, or admin
    if current_user.role == "Agent" and call.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Delete from storage
    from services.storage import get_storage_service
    storage = get_storage_service()
    storage.delete_file(call.s3_path)
    
    # Delete from database (cascade will handle related records)
    db.delete(call)
    db.commit()
    
    get_audit_service().log_action(
        user_id=current_user.user_id,
        action_type="delete",
        resource_type="call",
        resource_id=str(call_id),
        request=request
    )
    
    return {"message": "Call deleted successfully"}
