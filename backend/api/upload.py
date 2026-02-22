"""
Upload API endpoints for audio files.
"""
import io
import zipfile
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status, Request, Form
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user, check_permission
from services.storage import get_storage_service
from services.audit import get_audit_service
from workers.celery_app import celery_app
from models import User, Call, Batch, ScoringTemplate

PROCESS_CALL_TASK = "workers.pipeline.process_call_task"
from schemas import UploadResponse, BulkUploadResponse

router = APIRouter(prefix="/api/upload", tags=["Upload"])

# Allowed audio formats
ALLOWED_EXTENSIONS = {'.wav', '.mp3', '.mp4', '.m4a', '.flac', '.ogg', '.webm'}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB


def validate_audio_file(filename: str, content_type: str) -> bool:
    """Validate audio file extension and content type."""
    import os
    ext = os.path.splitext(filename.lower())[1]
    return ext in ALLOWED_EXTENSIONS


@router.post("/", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_call(
    request: Request,
    template_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a single audio file for processing."""
    
    # Check permission
    if not check_permission(current_user, "calls:upload"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to upload calls"
        )
    
    # Validate template exists
    template = db.query(ScoringTemplate).filter(
        ScoringTemplate.template_id == template_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid template ID"
        )
    
    # Validate file
    if not validate_audio_file(file.filename, file.content_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max size: {MAX_FILE_SIZE / 1024 / 1024} MB"
        )
    
    try:
        # Upload to storage
        storage = get_storage_service()
        s3_key = storage.upload_file(
            io.BytesIO(content),
            file.filename,
            content_type=file.content_type
        )
        
        # Create call record
        call = Call(
            user_id=current_user.user_id,
            template_id=template_id,
            s3_path=s3_key,
            original_filename=file.filename,
            file_size_bytes=len(content),
            status="queued"
        )
        
        db.add(call)
        db.commit()
        db.refresh(call)
        
        # Queue for processing (send_task avoids importing ML stack in API process)
        celery_app.send_task(PROCESS_CALL_TASK, args=[call.call_id, s3_key, template_id])
        
        # Audit log
        get_audit_service().log_action(
            user_id=current_user.user_id,
            action_type="upload",
            resource_type="call",
            resource_id=str(call.call_id),
            request=request,
            metadata={
                "filename": file.filename,
                "size": len(content),
                "template_id": template_id
            }
        )
        
        return {
            "call_id": call.call_id,
            "status": call.status,
            "message": "File uploaded successfully and queued for processing"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process upload: {str(e)}"
        )


@router.post("/bulk", response_model=BulkUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_bulk(
    request: Request,
    template_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a ZIP file containing multiple audio files."""
    
    if not check_permission(current_user, "calls:upload"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to upload calls"
        )
    
    # Validate template
    template = db.query(ScoringTemplate).filter(
        ScoringTemplate.template_id == template_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid template ID"
        )
    
    # Validate it's a ZIP file
    if not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk upload requires a ZIP file"
        )
    
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE * 5:  # 2.5 GB for bulk
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ZIP file too large"
        )
    
    try:
        # Create batch
        batch = Batch(
            user_id=current_user.user_id,
            num_calls=0,
            status="processing"
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)
        
        # Process ZIP
        processed_count = 0
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            audio_files = [
                f for f in zf.namelist()
                if any(f.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)
                and not f.startswith('__MACOSX')
            ]
            
            for audio_file in audio_files:
                file_content = zf.read(audio_file)
                filename = audio_file.split('/')[-1]
                
                # Upload to storage
                storage = get_storage_service()
                s3_key = storage.upload_file(
                    io.BytesIO(file_content),
                    filename,
                    content_type='audio/mpeg'
                )
                
                # Create call record
                call = Call(
                    user_id=current_user.user_id,
                    template_id=template_id,
                    batch_id=batch.batch_id,
                    s3_path=s3_key,
                    original_filename=filename,
                    file_size_bytes=len(file_content),
                    status="queued"
                )
                
                db.add(call)
                db.commit()
                db.refresh(call)
                
                # Queue for processing (send_task avoids importing ML stack in API process)
                celery_app.send_task(PROCESS_CALL_TASK, args=[call.call_id, s3_key, template_id])
                processed_count += 1
        
        # Update batch
        batch.num_calls = processed_count
        db.commit()
        
        # Audit log
        get_audit_service().log_action(
            user_id=current_user.user_id,
            action_type="upload",
            resource_type="batch",
            resource_id=str(batch.batch_id),
            request=request,
            metadata={
                "filename": file.filename,
                "num_calls": processed_count,
                "template_id": template_id
            }
        )
        
        return {
            "batch_id": str(batch.batch_id),
            "num_files": processed_count,
            "status": "processing",
            "message": f"Bulk upload successful. {processed_count} files queued for processing."
        }
        
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ZIP file"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process bulk upload: {str(e)}"
        )
