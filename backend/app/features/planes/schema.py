import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field


class PlanResponse(BaseModel):
    codigo: str
    nombre: str
    precio_anual_bs: float
    max_egresados: int | None = None  # None = sin límite
    max_moderadores: int | None = None
    reportes: bool
    marca_propia: bool


class InstitucionDisponibleResponse(BaseModel):
    """Universidad del catálogo que todavía no es cliente."""

    id: uuid.UUID
    nombre: str
    ciudad: str | None = None


class SolicitudUniversidadRequest(BaseModel):
    # Universidad del catálogo; si no está en la lista se crea una nueva al aprobar.
    institucion_id: uuid.UUID | None = None
    nombre: str = Field(min_length=3, max_length=200)
    sigla: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9-]+$")
    ciudad: str | None = Field(default=None, max_length=100)
    responsable_nombre: str = Field(min_length=3, max_length=150)
    responsable_correo: EmailStr
    responsable_telefono: str | None = Field(default=None, max_length=40)
    plan: str


class SolicitudUniversidadResponse(BaseModel):
    id: uuid.UUID
    institucion_id: uuid.UUID | None = None
    nombre: str
    sigla: str
    ciudad: str | None = None
    responsable_nombre: str
    responsable_correo: str
    responsable_telefono: str | None = None
    plan: str
    plan_nombre: str
    estado: str  # pending | approved | rejected
    motivo_rechazo: str | None = None
    fecha: datetime


class AprobarSolicitudRequest(BaseModel):
    # Contraseña temporal del admin de la universidad; la cambia en su primer ingreso.
    password_admin: str = Field(min_length=8)


class AprobarSolicitudResponse(BaseModel):
    universidad_id: uuid.UUID
    universidad: str
    plan: str
    admin_correo: str
    detalle: str


class RechazarSolicitudRequest(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)


class CambiarPlanRequest(BaseModel):
    plan: str


class CheckoutResponse(BaseModel):
    """URL de Stripe Checkout a la que se redirige al administrador."""

    url: str


class ConfirmarPagoRequest(BaseModel):
    session_id: str = Field(min_length=10, max_length=255, pattern=r"^cs_[A-Za-z0-9_]+$")


class ConfirmarPagoResponse(BaseModel):
    estado: str  # paid | pending | expired
    plan_nombre: str
    pagado_hasta: date | None = None


class PagoPlanResponse(BaseModel):
    id: uuid.UUID
    universidad_id: uuid.UUID
    universidad: str
    plan: str
    plan_nombre: str
    monto_bs: float
    metodo: str  # stripe | manual
    pagado_hasta: date | None = None
    fecha: datetime
    registrado_por: str | None = None
