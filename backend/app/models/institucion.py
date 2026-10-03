import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SaasPlan(Base):
    """Plan del SaaS (scripts/migrar_planes.py). Límites en NULL = sin límite."""

    __tablename__ = "saas_plan"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    audience: Mapped[str] = mapped_column(String(20), nullable=False, default="university")
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    price_bs_year: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    max_graduates: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_moderators: Mapped[int | None] = mapped_column(Integer, nullable=True)
    employability_reports: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    custom_branding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    @property
    def es_pago(self) -> bool:
        return self.price_bs_year > 0


class Institution(Base):
    """Universidad/institución educativa (tabla educational_institution).

    Es el tenant del SaaS: las que tienen is_tenant=true son clientes de la
    plataforma, con sus propios egresados y administradores. El resto se usa solo
    como catálogo de formación académica.
    """

    __tablename__ = "educational_institution"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    institution_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, default="unverified")
    slug: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_tenant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Plan contratado (NULL = Básico) y hasta cuándo está pagado.
    plan_code: Mapped[str | None] = mapped_column(String(30), ForeignKey("saas_plan.code"), nullable=True)
    plan_paid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UniversitySignupRequest(Base):
    """Solicitud de alta de una universidad desde la página pública."""

    __tablename__ = "university_signup_request"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Universidad del catálogo elegida por el solicitante, o la creada al aprobar.
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("educational_institution.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    acronym: Mapped[str] = mapped_column(String(20), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    plan_code: Mapped[str] = mapped_column(String(30), ForeignKey("saas_plan.code"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlanPayment(Base):
    """Pago anual del plan de una universidad: con tarjeta (Stripe Checkout) o manual."""

    __tablename__ = "plan_payment"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("educational_institution.id", ondelete="CASCADE"), nullable=False
    )
    plan_code: Mapped[str] = mapped_column(String(30), ForeignKey("saas_plan.code"), nullable=False)
    amount_bs: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)  # stripe | manual
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending | paid | expired
    stripe_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    # Vencimiento del plan que dejó este pago al acreditarse.
    paid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CompanyInstitution(Base):
    """Habilitación de una empresa (global) para reclutar egresados de una universidad."""

    __tablename__ = "company_institution"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id", ondelete="CASCADE"), primary_key=True
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("educational_institution.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    institution: Mapped[Institution] = relationship()
    company = relationship("Company")
