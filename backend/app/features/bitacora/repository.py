from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.seguridad import AuditLog


class BitacoraRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(self, log: AuditLog) -> AuditLog:
        self.db.add(log)
        self.db.flush()
        return log

    def entradas(self, desde: datetime | None = None, hasta: datetime | None = None) -> list[AuditLog]:
        """Entradas por día, de la más nueva a la más vieja.

        Con la bitácora cifrada, created_at solo tiene el día: el resto de los filtros
        (usuario, módulo, hora exacta, universidad) se aplica después de descifrar.
        """
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id)
        if desde is not None:
            stmt = stmt.where(AuditLog.created_at >= desde)
        if hasta is not None:
            stmt = stmt.where(AuditLog.created_at <= hasta)
        return list(self.db.scalars(stmt))

    def contar_sin_cifrar(self) -> int:
        return self.db.scalar(select(func.count(AuditLog.id)).where(AuditLog.payload_cifrado.is_(None))) or 0
