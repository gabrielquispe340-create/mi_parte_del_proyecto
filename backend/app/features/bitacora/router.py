import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.bitacora.schema import BitacoraLogResponse
from app.security.tenant import AlcanceStaff, get_alcance_staff
from app.features.bitacora.service import BitacoraService

router = APIRouter(prefix="/bitacora", tags=["bitacora"])

# El admin de una universidad solo ve la actividad de su staff y sus egresados;
# el superadmin ve la bitácora completa.


@router.get("", response_model=list[BitacoraLogResponse])
def listar_bitacora(
    usuario_id: uuid.UUID | None = None,
    modulo: str | None = None,
    accion: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    alcance: AlcanceStaff = Depends(get_alcance_staff),
    db: Session = Depends(get_db),
):
    return BitacoraService(db).listar(
        usuario_id=usuario_id,
        modulo=modulo,
        accion=accion,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        institution_id=alcance.institution_id,
    )


@router.get("/export/excel")
def exportar_excel(
    usuario_id: uuid.UUID | None = None,
    modulo: str | None = None,
    accion: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    alcance: AlcanceStaff = Depends(get_alcance_staff),
    db: Session = Depends(get_db),
):
    service = BitacoraService(db)
    logs = service.listar(
        usuario_id=usuario_id,
        modulo=modulo,
        accion=accion,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        institution_id=alcance.institution_id,
    )
    contenido = service.exportar_excel(logs)
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=bitacora.xlsx"},
    )


@router.get("/export/pdf")
def exportar_pdf(
    usuario_id: uuid.UUID | None = None,
    modulo: str | None = None,
    accion: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    alcance: AlcanceStaff = Depends(get_alcance_staff),
    db: Session = Depends(get_db),
):
    service = BitacoraService(db)
    logs = service.listar(
        usuario_id=usuario_id,
        modulo=modulo,
        accion=accion,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        institution_id=alcance.institution_id,
    )
    contenido = service.exportar_pdf(logs)
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=bitacora.pdf"},
    )
