import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.common.request_context import get_client_ip
from app.core.database import get_db
from app.features.bitacora.schema import AbrirBitacoraRequest, BitacoraLogResponse, EstadoBitacoraResponse
from app.features.bitacora.service import BitacoraService, FiltrosBitacora, descripcion_exportacion
from app.models.usuario import AppUser
from app.security.permisos import requiere_permiso
from app.security.tenant import AlcanceStaff, get_alcance_staff

router = APIRouter(prefix="/bitacora", tags=["bitacora"])

# El admin de una universidad solo ve la actividad de su staff y sus egresados;
# el superadmin ve la bitácora completa. Con la bitácora cifrada, además, cada consulta
# trae la clave de desarrollador en el encabezado X-Clave-Desarrollador.

_ACCIONES_DE_ACCESO = ("login", "login_fallido")


def _filtros(
    usuario_id: uuid.UUID | None = None,
    usuario: str | None = Query(None, max_length=120, description="Parte del correo del usuario"),
    modulo: str | None = None,
    accion: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    limite: int | None = Query(None, ge=1, le=500),
    sin_accesos: bool = Query(False, description="Excluye los inicios de sesión (panel del administrador)"),
) -> FiltrosBitacora:
    return FiltrosBitacora(
        usuario_id=usuario_id,
        usuario=usuario,
        modulo=modulo,
        accion=accion,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        excluir_acciones=_ACCIONES_DE_ACCESO if sin_accesos else (),
        limite=limite,
    )


def _consultar(db: Session, filtros: FiltrosBitacora, alcance: AlcanceStaff, clave: str | None, request: Request):
    return BitacoraService(db).listar(
        filtros,
        institution_id=alcance.institution_id,
        clave=clave,
        usuario_id=alcance.usuario.id_usuario,
        ip=get_client_ip(request),
    )


def _descripcion(db: Session, alcance: AlcanceStaff, total: int) -> list[str]:
    usuario = db.get(AppUser, alcance.usuario.id_usuario)
    return descripcion_exportacion(usuario.email if usuario else None, total)


@router.get("/estado", response_model=EstadoBitacoraResponse)
def estado(_: AlcanceStaff = Depends(get_alcance_staff), db: Session = Depends(get_db)):
    return BitacoraService(db).estado()


@router.post("/abrir", status_code=204)
def abrir(
    data: AbrirBitacoraRequest,
    request: Request,
    alcance: AlcanceStaff = Depends(requiere_permiso("menu.bitacora", "etiqueta.dashboard.actividad")),
    db: Session = Depends(get_db),
):
    """Comprueba la clave de desarrollador antes de mostrar la bitácora (423 si no es correcta)."""
    BitacoraService(db).abrir(data.clave, alcance.usuario.id_usuario, get_client_ip(request))


@router.get("", response_model=list[BitacoraLogResponse])
def listar_bitacora(
    request: Request,
    filtros: FiltrosBitacora = Depends(_filtros),
    clave: str | None = Header(None, alias="X-Clave-Desarrollador"),
    alcance: AlcanceStaff = Depends(requiere_permiso("menu.bitacora", "etiqueta.dashboard.actividad")),
    db: Session = Depends(get_db),
):
    return _consultar(db, filtros, alcance, clave, request)


@router.get("/export/excel")
def exportar_excel(
    request: Request,
    filtros: FiltrosBitacora = Depends(_filtros),
    clave: str | None = Header(None, alias="X-Clave-Desarrollador"),
    alcance: AlcanceStaff = Depends(requiere_permiso("boton.bitacora.exportar")),
    db: Session = Depends(get_db),
):
    entradas = _consultar(db, filtros, alcance, clave, request)
    contenido = BitacoraService(db).exportar_excel(entradas, _descripcion(db, alcance, len(entradas)))
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=bitacora.xlsx"},
    )


@router.get("/export/pdf")
def exportar_pdf(
    request: Request,
    filtros: FiltrosBitacora = Depends(_filtros),
    clave: str | None = Header(None, alias="X-Clave-Desarrollador"),
    alcance: AlcanceStaff = Depends(requiere_permiso("boton.bitacora.exportar")),
    db: Session = Depends(get_db),
):
    entradas = _consultar(db, filtros, alcance, clave, request)
    contenido = BitacoraService(db).exportar_pdf(entradas, _descripcion(db, alcance, len(entradas)))
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=bitacora.pdf"},
    )
