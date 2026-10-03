"""Backup/Restore de todo el sistema. Solo el superadmin del SaaS."""

import uuid

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.common.request_context import get_client_ip
from app.core.database import get_db
from app.features.respaldos.schema import (
    CrearRespaldoRequest,
    RespaldoResponse,
    RestauracionResponse,
    RestaurarRequest,
)
from app.features.respaldos.service import RespaldoService
from app.security.tenant import AlcanceStaff, get_superadmin

router = APIRouter(prefix="/admin/respaldos", tags=["respaldos"])


@router.get("", response_model=list[RespaldoResponse])
def listar(_: AlcanceStaff = Depends(get_superadmin), db: Session = Depends(get_db)):
    return RespaldoService(db).listar()


@router.post("", response_model=RespaldoResponse, status_code=201)
def crear(
    data: CrearRespaldoRequest,
    request: Request,
    alcance: AlcanceStaff = Depends(get_superadmin),
    db: Session = Depends(get_db),
):
    return RespaldoService(db).crear(alcance, ip=get_client_ip(request), nota=data.nota)


@router.post("/subir", response_model=RespaldoResponse, status_code=201)
def subir(
    request: Request,
    archivo: UploadFile = File(...),
    alcance: AlcanceStaff = Depends(get_superadmin),
    db: Session = Depends(get_db),
):
    return RespaldoService(db).subir(archivo, alcance, ip=get_client_ip(request))


@router.get("/{respaldo_id}/descargar")
def descargar(
    respaldo_id: uuid.UUID,
    request: Request,
    alcance: AlcanceStaff = Depends(get_superadmin),
    db: Session = Depends(get_db),
):
    ruta = RespaldoService(db).archivo_para_descargar(respaldo_id, alcance, ip=get_client_ip(request))
    return FileResponse(ruta, media_type="application/zip", filename=ruta.name)


@router.post("/{respaldo_id}/restaurar", response_model=RestauracionResponse)
def restaurar(
    respaldo_id: uuid.UUID,
    data: RestaurarRequest,
    request: Request,
    alcance: AlcanceStaff = Depends(get_superadmin),
    db: Session = Depends(get_db),
):
    """Con simulacro=true comprueba la copia y deshace todo; sin él reemplaza los datos."""
    return RespaldoService(db).restaurar(respaldo_id, data, alcance, ip=get_client_ip(request))


@router.delete("/{respaldo_id}", status_code=204)
def eliminar(
    respaldo_id: uuid.UUID,
    request: Request,
    alcance: AlcanceStaff = Depends(get_superadmin),
    db: Session = Depends(get_db),
):
    RespaldoService(db).eliminar(respaldo_id, alcance, ip=get_client_ip(request))
