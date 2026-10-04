import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.common.request_context import get_client_ip
from app.core.database import get_db
from app.features.entrevistas.schema import (
    EntrevistaCrear,
    EntrevistaOut,
    EntrevistaRechazar,
    EntrevistaReprogramar,
    EntrevistaRevisar,
)
from app.features.entrevistas.service import EntrevistasService
from app.security.dependencies import CurrentUser, require_roles

router = APIRouter()

_solo_empresa = require_roles("empresa", "platform_admin")
_solo_candidato = require_roles("candidate")


# ─── ENDPOINTS LADO EMPRESA (/seleccion) ─────────────────────────────────────

router_empresa = APIRouter(prefix="/seleccion", tags=["entrevistas-empresa"])


@router_empresa.get("/entrevistas", response_model=list[EntrevistaOut])
def listar_agenda_entrevistas_empresa(
    desde: datetime = Query(..., description="Inicio del rango, ISO 8601 con zona horaria"),
    hasta: datetime = Query(..., description="Fin del rango (exclusivo), como máximo 31 días después"),
    current_user: CurrentUser = Depends(_solo_empresa),
    db: Session = Depends(get_db),
) -> list[EntrevistaOut]:
    """App móvil de empresas: agenda de entrevistas de todas sus vacantes, por hora de inicio."""
    return EntrevistasService(db).listar_agenda_empresa(
        user_id=current_user.id_usuario,
        desde=desde,
        hasta=hasta,
    )


@router_empresa.post("/postulaciones/{id_postulacion}/entrevistas", response_model=EntrevistaOut, status_code=201)
def proponer_entrevista(
    id_postulacion: uuid.UUID,
    data: EntrevistaCrear,
    request: Request,
    current_user: CurrentUser = Depends(_solo_empresa),
    db: Session = Depends(get_db),
) -> EntrevistaOut:
    """CP01: La empresa propone fecha, hora y modalidad de entrevista al candidato."""
    ip = get_client_ip(request)
    return EntrevistasService(db).proponer_entrevista(
        user_id=current_user.id_usuario,
        application_id=id_postulacion,
        data=data,
        ip=ip,
    )


@router_empresa.get("/postulaciones/{id_postulacion}/entrevistas", response_model=list[EntrevistaOut])
def listar_entrevistas_postulacion_empresa(
    id_postulacion: uuid.UUID,
    current_user: CurrentUser = Depends(_solo_empresa),
    db: Session = Depends(get_db),
) -> list[EntrevistaOut]:
    """Consultar historial de entrevistas asociadas a una postulación (lado empresa)."""
    return EntrevistasService(db).listar_entrevistas_empresa(
        user_id=current_user.id_usuario,
        application_id=id_postulacion,
    )


@router_empresa.put("/entrevistas/{id_entrevista}/reprogramar", response_model=EntrevistaOut)
def reprogramar_entrevista(
    id_entrevista: uuid.UUID,
    data: EntrevistaReprogramar,
    request: Request,
    current_user: CurrentUser = Depends(_solo_empresa),
    db: Session = Depends(get_db),
) -> EntrevistaOut:
    """CP03: La empresa reprograma una entrevista rechazada o pendiente."""
    ip = get_client_ip(request)
    return EntrevistasService(db).reprogramar_entrevista(
        user_id=current_user.id_usuario,
        interview_id=id_entrevista,
        data=data,
        ip=ip,
    )


@router_empresa.post("/entrevistas/{id_entrevista}/cancelar", response_model=EntrevistaOut)
def cancelar_entrevista(
    id_entrevista: uuid.UUID,
    request: Request,
    current_user: CurrentUser = Depends(_solo_empresa),
    db: Session = Depends(get_db),
) -> EntrevistaOut:
    """CP04: La empresa cancela una entrevista propuesta o agendada."""
    ip = get_client_ip(request)
    return EntrevistasService(db).cancelar_entrevista(
        user_id=current_user.id_usuario,
        interview_id=id_entrevista,
        ip=ip,
    )


@router_empresa.post("/entrevistas/{id_entrevista}/revisar", response_model=EntrevistaOut)
def revisar_entrevista_manual(
    id_entrevista: uuid.UUID,
    data: EntrevistaRevisar,
    request: Request,
    current_user: CurrentUser = Depends(_solo_empresa),
    db: Session = Depends(get_db),
) -> EntrevistaOut:
    """Desbloqueo manual del reclutador tras acumular 3 rechazos."""
    ip = get_client_ip(request)
    return EntrevistasService(db).revisar_entrevista(
        user_id=current_user.id_usuario,
        interview_id=id_entrevista,
        data=data,
        ip=ip,
    )


# ─── ENDPOINTS LADO CANDIDATO (/postulaciones) ───────────────────────────────

router_candidato = APIRouter(prefix="/postulaciones", tags=["entrevistas-candidato"])


@router_candidato.get("/{id_postulacion}/entrevistas", response_model=list[EntrevistaOut])
def listar_entrevistas_postulacion_candidato(
    id_postulacion: uuid.UUID,
    current_user: CurrentUser = Depends(_solo_candidato),
    db: Session = Depends(get_db),
) -> list[EntrevistaOut]:
    """El candidato consulta las entrevistas propuestas para su postulación."""
    return EntrevistasService(db).listar_entrevistas_candidato(
        user_id=current_user.id_usuario,
        application_id=id_postulacion,
    )


@router_candidato.post("/entrevistas/{id_entrevista}/confirmar", response_model=EntrevistaOut)
def confirmar_entrevista_candidato(
    id_entrevista: uuid.UUID,
    request: Request,
    current_user: CurrentUser = Depends(_solo_candidato),
    db: Session = Depends(get_db),
) -> EntrevistaOut:
    """CP02: El candidato confirma la propuesta de entrevista (auto-sync Kanban a etapa 'Entrevista')."""
    ip = get_client_ip(request)
    return EntrevistasService(db).confirmar_entrevista_candidato(
        user_id=current_user.id_usuario,
        interview_id=id_entrevista,
        ip=ip,
    )


@router_candidato.post("/entrevistas/{id_entrevista}/rechazar", response_model=EntrevistaOut)
def rechazar_entrevista_candidato(
    id_entrevista: uuid.UUID,
    data: EntrevistaRechazar,
    request: Request,
    current_user: CurrentUser = Depends(_solo_candidato),
    db: Session = Depends(get_db),
) -> EntrevistaOut:
    """CP03: El candidato rechaza la propuesta de entrevista con un motivo."""
    ip = get_client_ip(request)
    return EntrevistasService(db).rechazar_entrevista_candidato(
        user_id=current_user.id_usuario,
        interview_id=id_entrevista,
        data=data,
        ip=ip,
    )


router.include_router(router_empresa)
router.include_router(router_candidato)
