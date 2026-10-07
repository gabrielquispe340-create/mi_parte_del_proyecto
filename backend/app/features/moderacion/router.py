"""Módulo 5.1.9 — Moderación y antifraude: denuncia de ofertas (HU-22)."""

import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.common.request_context import get_client_ip
from app.core.database import get_db
from app.features.moderacion.schema import (
    DenunciaCreadaResponse,
    DenunciaCreateRequest,
    DenunciasPendientesResponse,
    MiDenunciaResponse,
    ResolucionDenunciaRequest,
    ResolucionDenunciaResponse,
)
from app.features.moderacion.service import DenunciaService
from app.security.dependencies import CurrentUser, get_current_user
from app.security.permisos import requiere_permiso
from app.security.tenant import AlcanceStaff

router = APIRouter(prefix="/moderacion", tags=["moderacion"])


@router.post(
    "/vacantes/{vacante_id}/denuncias",
    response_model=DenunciaCreadaResponse,
    status_code=status.HTTP_201_CREATED,
)
def denunciar_vacante(
    vacante_id: uuid.UUID,
    data: DenunciaCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """HU-22: cualquier usuario autenticado denuncia una oferta indicando el motivo."""
    return DenunciaService(db).denunciar(vacante_id, data, current_user, get_client_ip(request))


@router.get("/vacantes/{vacante_id}/mi-denuncia", response_model=MiDenunciaResponse)
def mi_denuncia(
    vacante_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Si el usuario ya tiene una denuncia pendiente sobre esta oferta."""
    return DenunciaService(db).mi_denuncia(vacante_id, current_user)


@router.get("/denuncias", response_model=DenunciasPendientesResponse)
def listar_denuncias_pendientes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    alcance: AlcanceStaff = Depends(requiere_permiso("menu.denuncias")),
    db: Session = Depends(get_db),
):
    """HU-22: ofertas con denuncias pendientes de las empresas habilitadas en la universidad."""
    return DenunciaService(db).listar_pendientes(alcance, page, page_size)


@router.post("/vacantes/{vacante_id}/resolucion", response_model=ResolucionDenunciaResponse)
def resolver_denuncias(
    vacante_id: uuid.UUID,
    data: ResolucionDenunciaRequest,
    request: Request,
    alcance: AlcanceStaff = Depends(requiere_permiso("boton.denuncias.resolver")),
    db: Session = Depends(get_db),
):
    """HU-22: mantener, suspender o eliminar la oferta denunciada; cierra sus denuncias pendientes."""
    return DenunciaService(db).resolver(vacante_id, data, alcance, get_client_ip(request))
