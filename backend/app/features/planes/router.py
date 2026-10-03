import uuid

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.common.request_context import get_client_ip
from app.core.database import get_db
from app.features.instituciones.schema import ResumenInstitucionResponse
from app.features.planes.schema import (
    AprobarSolicitudRequest,
    AprobarSolicitudResponse,
    CambiarPlanRequest,
    CheckoutResponse,
    ConfirmarPagoRequest,
    ConfirmarPagoResponse,
    InstitucionDisponibleResponse,
    PagoPlanResponse,
    PlanResponse,
    RechazarSolicitudRequest,
    SolicitudUniversidadRequest,
    SolicitudUniversidadResponse,
)
from app.features.planes.service import PlanService
from app.security.dependencies import require_roles
from app.security.tenant import AlcanceStaff, get_alcance_staff, get_superadmin

router = APIRouter(prefix="/planes", tags=["planes-saas"])

# Públicos: los usa la página "Registrá tu universidad".


@router.get("", response_model=list[PlanResponse])
def listar_planes(db: Session = Depends(get_db)):
    return PlanService(db).listar_planes()


@router.get("/instituciones-disponibles", response_model=list[InstitucionDisponibleResponse])
def instituciones_disponibles(db: Session = Depends(get_db)):
    return PlanService(db).instituciones_disponibles()


@router.post("/solicitudes", response_model=SolicitudUniversidadResponse, status_code=201)
def solicitar_alta(data: SolicitudUniversidadRequest, request: Request, db: Session = Depends(get_db)):
    return PlanService(db).crear_solicitud(data, ip=get_client_ip(request))


# Lo llama Stripe (sin sesión de usuario): la autenticidad se valida con la firma.
@router.post("/stripe/webhook", include_in_schema=False)
async def webhook_stripe(
    request: Request,
    stripe_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    PlanService(db).procesar_webhook(await request.body(), stripe_signature)
    return {"recibido": True}


# Pago del plan con tarjeta: lo inicia el admin de la universidad; al volver de Stripe
# cualquier staff de esa universidad (o el superadmin) puede confirmarlo.


@router.post(
    "/mi-universidad/checkout",
    response_model=CheckoutResponse,
    dependencies=[Depends(require_roles("platform_admin"))],
)
def iniciar_pago(alcance: AlcanceStaff = Depends(get_alcance_staff), db: Session = Depends(get_db)):
    return PlanService(db).iniciar_pago(alcance)


@router.post("/pagos/confirmar", response_model=ConfirmarPagoResponse)
def confirmar_pago(
    data: ConfirmarPagoRequest,
    alcance: AlcanceStaff = Depends(get_alcance_staff),
    db: Session = Depends(get_db),
):
    return PlanService(db).confirmar_pago(data.session_id, alcance)


@router.get("/pagos", response_model=list[PagoPlanResponse])
def listar_pagos(alcance: AlcanceStaff = Depends(get_alcance_staff), db: Session = Depends(get_db)):
    """Superadmin: los de todas las universidades. Admin de universidad: solo los suyos."""
    return PlanService(db).listar_pagos(alcance.institution_id)


# Solo el superadmin del SaaS.


@router.get("/solicitudes", response_model=list[SolicitudUniversidadResponse])
def listar_solicitudes(
    estado: str | None = Query(default="pending"),
    _: AlcanceStaff = Depends(get_superadmin),
    db: Session = Depends(get_db),
):
    return PlanService(db).listar_solicitudes(estado)


@router.post("/solicitudes/{solicitud_id}/aprobar", response_model=AprobarSolicitudResponse)
def aprobar_solicitud(
    solicitud_id: uuid.UUID,
    data: AprobarSolicitudRequest,
    request: Request,
    alcance: AlcanceStaff = Depends(get_superadmin),
    db: Session = Depends(get_db),
):
    return PlanService(db).aprobar(
        solicitud_id, data.password_admin, responsable_id=alcance.usuario.id_usuario, ip=get_client_ip(request)
    )


@router.post("/solicitudes/{solicitud_id}/rechazar", response_model=SolicitudUniversidadResponse)
def rechazar_solicitud(
    solicitud_id: uuid.UUID,
    data: RechazarSolicitudRequest,
    request: Request,
    alcance: AlcanceStaff = Depends(get_superadmin),
    db: Session = Depends(get_db),
):
    return PlanService(db).rechazar(
        solicitud_id, data.motivo, responsable_id=alcance.usuario.id_usuario, ip=get_client_ip(request)
    )


@router.put("/universidades/{institucion_id}/plan", response_model=ResumenInstitucionResponse)
def cambiar_plan(
    institucion_id: uuid.UUID,
    data: CambiarPlanRequest,
    request: Request,
    alcance: AlcanceStaff = Depends(get_superadmin),
    db: Session = Depends(get_db),
):
    return PlanService(db).cambiar_plan(
        institucion_id, data.plan, responsable_id=alcance.usuario.id_usuario, ip=get_client_ip(request)
    )


@router.post("/universidades/{institucion_id}/pago", response_model=ResumenInstitucionResponse)
def registrar_pago(
    institucion_id: uuid.UUID,
    request: Request,
    alcance: AlcanceStaff = Depends(get_superadmin),
    db: Session = Depends(get_db),
):
    return PlanService(db).registrar_pago(
        institucion_id, responsable_id=alcance.usuario.id_usuario, ip=get_client_ip(request)
    )
