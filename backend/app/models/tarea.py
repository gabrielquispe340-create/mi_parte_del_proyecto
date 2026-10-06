import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ScheduledTaskRun(Base):
    """Una ejecución de una tarea automática diaria (scripts/migrar_requisitos_generales.py).

    Sin claves foráneas, igual que system_backup: el historial sobrevive a una restauración.
    """

    __tablename__ = "scheduled_task_run"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="automatico")  # automatico | manual
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")  # running | success | failure
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    triggered_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
