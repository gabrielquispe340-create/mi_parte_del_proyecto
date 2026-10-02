import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.seguridad import AuditLog
from app.security.tenant import usuarios_de_institucion


class BitacoraRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(self, log: AuditLog) -> AuditLog:
        self.db.add(log)
        self.db.flush()
        return log

    def listar(
        self,
        usuario_id: uuid.UUID | str | None = None,
        modulo: str | None = None,
        accion: str | None = None,
        fecha_desde: datetime | None = None,
        fecha_hasta: datetime | None = None,
        institution_id: uuid.UUID | None = None,
    ) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        if institution_id is not None:
            stmt = stmt.where(AuditLog.user_id.in_(usuarios_de_institucion(institution_id)))
        if usuario_id is not None:
            stmt = stmt.where(AuditLog.user_id == usuario_id)
        if modulo is not None:
            stmt = stmt.where(AuditLog.entity_type == modulo)
        if accion is not None:
            stmt = stmt.where(AuditLog.action == accion)
        if fecha_desde is not None:
            stmt = stmt.where(AuditLog.created_at >= fecha_desde)
        if fecha_hasta is not None:
            stmt = stmt.where(AuditLog.created_at <= fecha_hasta)
        return list(self.db.scalars(stmt))
