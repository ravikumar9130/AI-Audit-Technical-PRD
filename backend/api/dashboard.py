"""
Dashboard API endpoints with role-based views.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_

from core.database import get_db
from core.security import get_current_user, check_permission
from services.audit import get_audit_service
from models import User, Call, EvaluationResult, ScoringTemplate
from schemas import AgentDashboard, ManagerDashboard, CXODashboard, DashboardMetrics

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def calculate_metrics(query) -> DashboardMetrics:
    """Calculate dashboard metrics from a query."""
    total = query.count()
    completed = query.filter(Call.status == "completed").count()
    failed = query.filter(Call.status == "failed").count()
    processing = query.filter(Call.status == "processing").count()
    
    # Calculate average score
    avg_score = 0.0
    if completed > 0:
        completed_calls = query.filter(Call.status == "completed").subquery()
        avg = query.session.query(func.avg(EvaluationResult.overall_score)).join(
            completed_calls, EvaluationResult.call_id == completed_calls.c.call_id
        ).scalar()
        avg_score = float(avg) if avg else 0.0
    
    return DashboardMetrics(
        total_calls=total,
        avg_score=avg_score,
        completed_calls=completed,
        failed_calls=failed,
        processing_calls=processing
    )


@router.get("/agent", response_model=AgentDashboard)
def get_agent_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get dashboard data for agent role."""
    
    # Get agent's calls
    calls_query = db.query(Call).filter(Call.user_id == current_user.user_id)
    
    # Recent calls
    recent_calls = calls_query.order_by(desc(Call.created_at)).limit(10).all()
    
    # Metrics
    metrics = calculate_metrics(calls_query)
    
    # Trend data (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    trend_data = []
    
    daily_calls = db.query(
        func.date(Call.created_at).label('date'),
        func.count(Call.call_id).label('count'),
        func.avg(EvaluationResult.overall_score).label('avg_score')
    ).outerjoin(
        EvaluationResult, Call.call_id == EvaluationResult.call_id
    ).filter(
        Call.user_id == current_user.user_id,
        Call.created_at >= thirty_days_ago
    ).group_by(
        func.date(Call.created_at)
    ).order_by('date').all()
    
    for day in daily_calls:
        trend_data.append({
            "date": day.date.isoformat() if day.date else None,
            "call_count": day.count,
            "avg_score": float(day.avg_score) if day.avg_score else 0
        })
    
    get_audit_service().log_action(
        user_id=current_user.user_id,
        action_type="view",
        resource_type="dashboard",
        resource_id="agent",
        request=request
    )
    
    return {
        "user": current_user,
        "metrics": metrics,
        "recent_calls": recent_calls,
        "trend_data": trend_data
    }


@router.get("/manager", response_model=ManagerDashboard)
def get_manager_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get dashboard data for manager role."""
    
    if not check_permission(current_user, "calls:read-team"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get team members
    team_members = db.query(User).filter(
        User.manager_id == current_user.user_id
    ).all()
    
    team_ids = [current_user.user_id] + [m.user_id for m in team_members]
    
    # Team metrics
    calls_query = db.query(Call).filter(Call.user_id.in_(team_ids))
    metrics = calculate_metrics(calls_query)
    
    # Calls by agent
    calls_by_agent = []
    for agent in team_members + [current_user]:
        agent_calls = db.query(Call).filter(Call.user_id == agent.user_id)
        agent_metrics = calculate_metrics(agent_calls)
        calls_by_agent.append({
            "agent_id": agent.user_id,
            "agent_name": f"{agent.first_name} {agent.last_name}",
            "total_calls": agent_metrics.total_calls,
            "avg_score": agent_metrics.avg_score,
            "completed_calls": agent_metrics.completed_calls
        })
    
    # Risk alerts (low scores, compliance issues)
    risk_alerts = []
    low_score_calls = db.query(Call, EvaluationResult).join(
        EvaluationResult
    ).filter(
        Call.user_id.in_(team_ids),
        EvaluationResult.overall_score < 60
    ).order_by(desc(Call.created_at)).limit(5).all()
    
    for call, eval_result in low_score_calls:
        risk_alerts.append({
            "call_id": call.call_id,
            "agent_id": call.user_id,
            "score": eval_result.overall_score,
            "type": "low_score",
            "message": f"Call scored {eval_result.overall_score:.1f}/100"
        })
    
    # Compliance violations
    violations = db.query(Call, EvaluationResult).join(
        EvaluationResult
    ).filter(
        Call.user_id.in_(team_ids),
        EvaluationResult.fatal_flaw_detected == True
    ).order_by(desc(Call.created_at)).limit(5).all()
    
    for call, eval_result in violations:
        risk_alerts.append({
            "call_id": call.call_id,
            "agent_id": call.user_id,
            "score": eval_result.overall_score,
            "type": "compliance_violation",
            "flaw_type": eval_result.fatal_flaw_type,
            "message": f"Compliance issue: {eval_result.fatal_flaw_type}"
        })
    
    # Skill heatmap data
    skill_heatmap = {}
    templates = db.query(ScoringTemplate).filter(ScoringTemplate.is_active == True).all()
    
    for template in templates:
        template_calls = db.query(Call).filter(
            Call.template_id == template.template_id,
            Call.user_id.in_(team_ids)
        ).subquery()
        
        scores = db.query(EvaluationResult).join(
            template_calls, EvaluationResult.call_id == template_calls.c.call_id
        ).all()
        
        if scores:
            skill_scores = {}
            for score in scores:
                if score.pillar_scores:
                    for pillar, value in score.pillar_scores.items():
                        if pillar not in skill_scores:
                            skill_scores[pillar] = []
                        skill_scores[pillar].append(value)
            
            skill_heatmap[template.vertical] = {
                pillar: sum(values) / len(values) if values else 0
                for pillar, values in skill_scores.items()
            }
    
    get_audit_service().log_action(
        user_id=current_user.user_id,
        action_type="view",
        resource_type="dashboard",
        resource_id="manager",
        request=request
    )
    
    return {
        "user": current_user,
        "team_metrics": metrics,
        "team_members": team_members,
        "calls_by_agent": calls_by_agent,
        "risk_alerts": risk_alerts,
        "skill_heatmap": skill_heatmap
    }


@router.get("/cxo", response_model=CXODashboard)
def get_cxo_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get dashboard data for CXO/executive role."""
    
    if not check_permission(current_user, "analytics:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Company-wide metrics
    calls_query = db.query(Call)
    metrics = calculate_metrics(calls_query)
    
    # Vertical breakdown
    vertical_breakdown = {}
    templates = db.query(ScoringTemplate).all()
    
    for template in templates:
        template_calls = db.query(Call).filter(
            Call.template_id == template.template_id
        )
        template_metrics = calculate_metrics(template_calls)
        
        vertical_breakdown[template.vertical] = {
            "template_name": template.name,
            "total_calls": template_metrics.total_calls,
            "avg_score": template_metrics.avg_score,
            "completion_rate": (
                template_metrics.completed_calls / template_metrics.total_calls * 100
                if template_metrics.total_calls > 0 else 0
            )
        }
    
    # Compliance summary
    total_evaluations = db.query(EvaluationResult).count()
    compliance_violations = db.query(EvaluationResult).filter(
        EvaluationResult.fatal_flaw_detected == True
    ).count()
    
    compliance_summary = {
        "total_evaluated": total_evaluations,
        "violations": compliance_violations,
        "compliance_rate": (
            (total_evaluations - compliance_violations) / total_evaluations * 100
            if total_evaluations > 0 else 100
        )
    }
    
    # Top issues
    top_issues = []
    if total_evaluations > 0:
        # Find common recommendations
        all_recommendations = db.query(EvaluationResult.recommendations).filter(
            EvaluationResult.recommendations.isnot(None)
        ).all()
        
        from collections import Counter
        rec_counter = Counter()
        for recs in all_recommendations:
            if recs[0]:
                rec_counter.update(recs[0])
        
        for rec, count in rec_counter.most_common(5):
            top_issues.append({
                "issue": rec,
                "frequency": count,
                "percentage": count / total_evaluations * 100
            })
    
    # Revenue forecast (placeholder for actual ML model)
    revenue_forecast = {
        "current_month": 0,
        "forecast_next_month": 0,
        "confidence": 0.85,
        "trend": "stable"
    }
    
    get_audit_service().log_action(
        user_id=current_user.user_id,
        action_type="view",
        resource_type="dashboard",
        resource_id="cxo",
        request=request
    )
    
    return {
        "user": current_user,
        "company_metrics": metrics,
        "vertical_breakdown": vertical_breakdown,
        "revenue_forecast": revenue_forecast,
        "compliance_summary": compliance_summary,
        "top_issues": top_issues
    }
