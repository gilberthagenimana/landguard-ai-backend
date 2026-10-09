from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.domain import AuditLogOut
from app.services.auth.service import require_roles
from app.services.serializers import serialize_audit

router = APIRouter(prefix="/audit-logs", tags=["Audit"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    q: str | None = Query(default=None),
    action: str | None = Query(default=None),
    entity: str | None = Query(default=None),
    user_id: int | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("ADMIN", "AUDITOR")),
):
    query = db.query(AuditLog)
    if q:
        like = f"%{q}%"
        query = query.filter((AuditLog.action.ilike(like)) | (AuditLog.entity.ilike(like)))
    if action:
        query = query.filter(AuditLog.action == action)
    if entity:
        query = query.filter(AuditLog.entity == entity)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    total = query.count()
    rows = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return [serialize_audit(db, item) for item in rows]


@router.get("/export")
def export_audit_logs(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("ADMIN", "AUDITOR")),
):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(1000).all()
    items = [serialize_audit(db, item) for item in rows]
    if format == "csv":
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "user_id", "user_name", "action", "entity", "entity_id", "created_at"])
        for item in items:
            writer.writerow([
                item.id, item.user_id, item.user_name, item.action,
                item.entity, item.entity_id, item.created_at
            ])
        return {"format": "csv", "data": output.getvalue(), "count": len(items)}
    return {"format": "json", "items": items, "count": len(items)}
