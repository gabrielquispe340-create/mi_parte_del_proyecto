import uuid
from datetime import date, datetime

from pydantic import BaseModel


class InstitucionEmpresaResponse(BaseModel):
    """Universidad cliente y el estado de acceso de la empresa autenticada a ella."""

    id: uuid.UUID
    nombre: str
    sigla: str | None = None
    ciudad: str | None = None
    estado: str | None = None  # None = sin solicitar | pending | approved | rejected | suspended
    motivo_rechazo: str | None = None
    fecha_solicitud: datetime | None = None


class PlanDeUniversidadResponse(BaseModel):
    codigo: str  # plan contratado
    nombre: str
    precio_anual_bs: float
    estado_pago: str  # gratis | al_dia | pendiente | vencido
    pago_hasta: date | None = None
    # Límites que rigen ahora (los del Básico si el pago no está al día). None = sin límite.
    vigente: str
    max_egresados: int | None = None
    max_moderadores: int | None = None
    reportes: bool = False
    marca_propia: bool = False


class ResumenInstitucionResponse(BaseModel):
    id: uuid.UUID
    nombre: str
    sigla: str | None = None
    ciudad: str | None = None
    egresados_total: int
    egresados_verificados: int
    egresados_pendientes: int
    empresas_aprobadas: int
    empresas_pendientes: int
    vacantes_publicadas: int
    postulaciones: int
    moderadores: int = 0
    plan: PlanDeUniversidadResponse | None = None


class TotalesPanel(BaseModel):
    """Totales del alcance del admin, sin contar dos veces lo que comparten varias universidades."""

    egresados: int
    egresados_verificados: int
    empresas_habilitadas: int
    vacantes_publicadas: int
    postulaciones: int


class PendientesPanel(BaseModel):
    """Lo que espera una decisión del admin; cada número coincide con su módulo de gestión."""

    egresados: int
    empresas: int
    vacantes: int
    universidades: int = 0  # solicitudes de alta (solo las ve el superadmin)


class ActividadPanel(BaseModel):
    fecha: datetime
    usuario: str | None = None
    modulo: str
    accion: str
    detalles: str | None = None
    resultado: bool


class PanelAdminResponse(BaseModel):
    universidades: list[ResumenInstitucionResponse]
    totales: TotalesPanel
    pendientes: PendientesPanel
    accesos_hoy: int
    accesos_fallidos_hoy: int
    actividad: list[ActividadPanel]
