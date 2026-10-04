"""Módulo 5.1.7 — Comunicación interna entre empresa y candidato (HU-19)."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.common.request_context import get_client_ip
from app.core.database import get_db
from app.features.comunicacion.schema import ConversacionPostulacionOut, ConversacionResumenOut, MensajeOut
from app.features.comunicacion.service import ComunicacionService
from app.security.dependencies import CurrentUser, require_roles

router = APIRouter(prefix="/comunicacion", tags=["comunicacion"])

_roles_mensajeria = require_roles("empresa", "candidate", "egresado", "candidato", "platform_admin")


@router.get("/_status")
def estado_modulo() -> dict:
    return {"modulo": "comunicacion_y_entrevistas", "sprint_previsto": 2, "activo": True}


@router.get("/conversaciones", response_model=list[ConversacionResumenOut])
def listar_conversaciones(
    current_user: CurrentUser = Depends(_roles_mensajeria),
    db: Session = Depends(get_db),
) -> list[ConversacionResumenOut]:
    """Bandeja de mensajes: hilos del usuario con su último mensaje y los no leídos."""
    return ComunicacionService(db).listar_conversaciones(current_user.id_usuario)


@router.get(
    "/postulaciones/{id_postulacion}/mensajes",
    response_model=ConversacionPostulacionOut,
)
def obtener_mensajes_postulacion(
    id_postulacion: uuid.UUID,
    current_user: CurrentUser = Depends(_roles_mensajeria),
    db: Session = Depends(get_db),
) -> ConversacionPostulacionOut:
    """Obtiene el hilo y el historial completo de mensajes asociados a una postulación."""
    return ComunicacionService(db).obtener_conversacion_postulacion(
        user_id=current_user.id_usuario,
        application_id=id_postulacion,
        marcar_como_leido=True,
    )


@router.post(
    "/postulaciones/{id_postulacion}/mensajes",
    response_model=MensajeOut,
    status_code=201,
)
def enviar_mensaje_postulacion(
    id_postulacion: uuid.UUID,
    request: Request,
    contenido: Optional[str] = Form(default=None),
    archivo: Optional[UploadFile] = File(default=None),
    current_user: CurrentUser = Depends(_roles_mensajeria),
    db: Session = Depends(get_db),
) -> MensajeOut:
    """Envía un mensaje de texto y/o un archivo adjunto (máx. 5 MB) dentro del hilo de la postulación."""
    ip = get_client_ip(request)
    return ComunicacionService(db).enviar_mensaje(
        user_id=current_user.id_usuario,
        application_id=id_postulacion,
        contenido=contenido,
        archivo=archivo,
        ip=ip,
    )


@router.get("/adjuntos/{id_adjunto}")
def descargar_adjunto_mensaje(
    id_adjunto: uuid.UUID,
    current_user: CurrentUser = Depends(_roles_mensajeria),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Descarga segura de un archivo adjunto verificando pertenencia a la postulación."""
    ruta, nombre_original, mime_type = ComunicacionService(db).obtener_archivo_adjunto(
        user_id=current_user.id_usuario,
        attachment_id=id_adjunto,
    )
    return FileResponse(
        path=str(ruta),
        filename=nombre_original,
        media_type=mime_type,
    )
