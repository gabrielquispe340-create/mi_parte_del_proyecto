import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SystemBackup(Base):
    """Copia de seguridad de toda la base (scripts/migrar_respaldos.py).

    Sin claves foráneas: la restauración recarga el resto de las tablas y este catálogo
    tiene que quedar intacto.
    """

    __tablename__ = "system_backup"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name: Mapped[str] = mapped_column(String(200), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    tables_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rows_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")  # manual | previa_restauracion | subido
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
