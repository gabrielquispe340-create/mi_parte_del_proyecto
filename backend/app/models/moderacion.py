import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ModerationReport(Base):
    """Denuncia de un usuario sobre una vacante o una empresa (tabla moderation_report) — HU-22.

    La tabla ya existe en Supabase: la HU-22 solo usa las denuncias de vacantes (job_id).
    Una denuncia apunta a una vacante o a una empresa, nunca a ambas (ck_mr_target).
    """

    __tablename__ = "moderation_report"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_posting.id", ondelete="SET NULL"), nullable=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id", ondelete="SET NULL"), nullable=True
    )
    # fraud, inappropriate, spam, fake_information, discrimination, other (ck_mr_category)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # pending, investigating, resolved, dismissed (ck_mr_status)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reporter = relationship("AppUser")
    job_posting = relationship("JobPosting")
