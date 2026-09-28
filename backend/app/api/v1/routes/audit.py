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
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("ADMIN", "AUDITOR")),
):
    query = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if q:
        like = f"%{q}%"
        query = query.filter((AuditLog.action.ilike(like)) | (AuditLog.entity.ilike(like)))
    return [serialize_audit(db, item) for item in query.limit(200).all()]
