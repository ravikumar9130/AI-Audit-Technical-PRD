"""
Scoring templates API endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc

from core.database import get_db
from core.security import get_current_user, require_role, check_permission
from services.audit import get_audit_service
from models import User, ScoringTemplate
from schemas import (
    ScoringTemplateCreate, ScoringTemplateUpdate, 
    ScoringTemplateResponse
)

router = APIRouter(prefix="/api/templates", tags=["Templates"])


@router.get("/", response_model=List[ScoringTemplateResponse])
def list_templates(
    request: Request,
    vertical: Optional[str] = Query(None, description="Filter by vertical"),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List scoring templates."""
    
    query = db.query(ScoringTemplate)
    
    if vertical:
        query = query.filter(ScoringTemplate.vertical == vertical)
    if is_active is not None:
        query = query.filter(ScoringTemplate.is_active == is_active)
    
    templates = query.order_by(desc(ScoringTemplate.created_at)).all()
    
    get_audit_service().log_action(
        user_id=current_user.user_id,
        action_type="view",
        resource_type="templates",
        request=request
    )
    
    return templates


@router.get("/{template_id}", response_model=ScoringTemplateResponse)
def get_template(
    request: Request,
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get template by ID."""
    
    template = db.query(ScoringTemplate).filter(
        ScoringTemplate.template_id == template_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    get_audit_service().log_action(
        user_id=current_user.user_id,
        action_type="view",
        resource_type="template",
        resource_id=str(template_id),
        request=request
    )
    
    return template


@router.post("/", response_model=ScoringTemplateResponse, status_code=201)
def create_template(
    request: Request,
    template_data: ScoringTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Manager", "CXO", "Admin"))
):
    """Create a new scoring template (Manager+ only)."""
    
    if not check_permission(current_user, "templates:manage"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    template = ScoringTemplate(
        name=template_data.name,
        vertical=template_data.vertical,
        system_prompt=template_data.system_prompt,
        user_prompt_template=template_data.user_prompt_template,
        json_schema=template_data.json_schema,
        scoring_weights=template_data.scoring_weights,
        created_by=current_user.user_id
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    get_audit_service().log_action(
        user_id=current_user.user_id,
        action_type="config_change",
        resource_type="template",
        resource_id=str(template.template_id),
        request=request,
        metadata={"action": "created", "name": template.name}
    )
    
    return template


@router.put("/{template_id}", response_model=ScoringTemplateResponse)
def update_template(
    request: Request,
    template_id: int,
    template_data: ScoringTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Manager", "CXO", "Admin"))
):
    """Update a scoring template (Manager+ only)."""
    
    if not check_permission(current_user, "templates:manage"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    template = db.query(ScoringTemplate).filter(
        ScoringTemplate.template_id == template_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Update version if content changes
    content_changed = any([
        template_data.system_prompt is not None and template_data.system_prompt != template.system_prompt,
        template_data.user_prompt_template is not None and template_data.user_prompt_template != template.user_prompt_template,
        template_data.json_schema is not None and template_data.json_schema != template.json_schema
    ])
    
    if content_changed:
        template.version += 1
    
    # Update fields
    for field, value in template_data.dict(exclude_unset=True).items():
        setattr(template, field, value)
    
    db.commit()
    db.refresh(template)
    
    get_audit_service().log_action(
        user_id=current_user.user_id,
        action_type="config_change",
        resource_type="template",
        resource_id=str(template_id),
        request=request,
        metadata={"action": "updated", "version": template.version}
    )
    
    return template


@router.delete("/{template_id}")
def delete_template(
    request: Request,
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("CXO", "Admin"))
):
    """Delete a scoring template (CXO/Admin only)."""
    
    template = db.query(ScoringTemplate).filter(
        ScoringTemplate.template_id == template_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Soft delete by deactivating
    template.is_active = False
    db.commit()
    
    get_audit_service().log_action(
        user_id=current_user.user_id,
        action_type="config_change",
        resource_type="template",
        resource_id=str(template_id),
        request=request,
        metadata={"action": "deactivated"}
    )
    
    return {"message": "Template deactivated successfully"}
