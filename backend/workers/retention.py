"""
Data retention and GDPR compliance tasks.
"""
from datetime import datetime, timedelta

from celery import shared_task

from core.database import get_db_context
from core.config import get_settings
from models import Call, Client, RetentionSchedule
from services.storage import get_storage_service

settings = get_settings()


@shared_task
def enforce_data_retention():
    """
    Scheduled task to enforce data retention policies.
    Runs daily via Celery Beat.
    """
    deleted_count = 0
    
    with get_db_context() as db:
        # Get all clients with retention policies
        clients = db.query(Client).all()
        
        for client in clients:
            cutoff_date = datetime.utcnow() - timedelta(days=client.retention_days)
            
            # Find calls to delete
            old_calls = db.query(Call).filter(
                Call.client_id == client.client_id,
                Call.created_at < cutoff_date
            ).all()
            
            storage = get_storage_service()
            
            for call in old_calls:
                try:
                    # Delete from storage
                    storage.delete_file(call.s3_path)
                    
                    # Delete from database (cascade handles related records)
                    db.delete(call)
                    deleted_count += 1
                    
                except Exception as e:
                    print(f"Failed to delete call {call.call_id}: {e}")
        
        db.commit()
    
    return {"deleted_calls": deleted_count}


@shared_task
def process_retention_schedule():
    """
    Process scheduled deletions (e.g., user right-to-be-forgotten requests).
    """
    with get_db_context() as db:
        # Get pending deletions
        pending = db.query(RetentionSchedule).filter(
            RetentionSchedule.status == "pending",
            RetentionSchedule.scheduled_deletion_at <= datetime.utcnow()
        ).all()
        
        storage = get_storage_service()
        
        for schedule in pending:
            try:
                call = db.query(Call).filter(
                    Call.call_id == schedule.call_id
                ).first()
                
                if call:
                    # Delete from storage
                    storage.delete_file(call.s3_path)
                    
                    # Delete from database
                    db.delete(call)
                
                # Mark schedule as executed
                schedule.status = "executed"
                schedule.executed_at = datetime.utcnow()
                
            except Exception as e:
                schedule.status = "failed"
                print(f"Failed to process retention schedule {schedule.schedule_id}: {e}")
        
        db.commit()
    
    return {"processed_schedules": len(pending)}


@shared_task
def anonymize_old_data():
    """
    Anonymize personal data in old transcripts for GDPR compliance.
    Keeps aggregate data but removes PII.
    """
    # TODO: Implement PII redaction in old transcripts
    pass
