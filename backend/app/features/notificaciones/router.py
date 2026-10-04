import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.notificaciones.schema import (
    ContadorNoLeidasResponse,
    CrearNotificacionInternaRequest,
    EliminarDeviceTokenRequest,
    NotificacionDTO,
    NotificacionesListResponse,
    PreferenciasNotificacionDTO,
    PreferenciasNotificacionUpdateRequest,
    RegistrarDeviceTokenRequest,
    TestPushFCMRequest,
)
from app.features.notificaciones.service import NotificacionService
from app.security.dependencies import CurrentUser, get_current_user
from app.security.tenant import AlcanceStaff, get_superadmin

router = APIRouter(prefix="/notificaciones", tags=["notificaciones"])


@router.get("", response_model=NotificacionesListResponse)
def listar_notificaciones(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    solo_no_leidas: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Obtiene el historial de notificaciones del usuario autenticado con conteo de no leídas."""
    return NotificacionService(db).listar_notificaciones(
        user_id=current_user.id_usuario, limit=limit, offset=offset, solo_no_leidas=solo_no_leidas
    )


@router.get("/contador-no-leidas", response_model=ContadorNoLeidasResponse)
def contar_notificaciones_no_leidas(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Retorna la cantidad de notificaciones pendientes para la campanita del navbar."""
    return NotificacionService(db).contar_no_leidas(user_id=current_user.id_usuario)


@router.patch("/{notification_id}/leer", response_model=NotificacionDTO)
def marcar_notificacion_como_leida(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Marca una notificación específica como leída."""
    return NotificacionService(db).marcar_como_leida(
        notification_id=notification_id, user_id=current_user.id_usuario
    )


@router.post("/marcar-todas-leidas")
def marcar_todas_como_leidas(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Marca todas las notificaciones pendientes del usuario como leídas."""
    return NotificacionService(db).marcar_todas_como_leidas(user_id=current_user.id_usuario)


@router.delete("/{notification_id}")
def eliminar_notificacion(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Elimina una notificación del historial del usuario."""
    return NotificacionService(db).eliminar_notificacion(
        notification_id=notification_id, user_id=current_user.id_usuario
    )


@router.get("/preferencias", response_model=PreferenciasNotificacionDTO)
def obtener_preferencias_notificacion(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Consulta las preferencias de configuración de alertas del usuario (HU-21)."""
    return NotificacionService(db).obtener_preferencias(user_id=current_user.id_usuario)


@router.put("/preferencias", response_model=PreferenciasNotificacionDTO)
def actualizar_preferencias_notificacion(
    req: PreferenciasNotificacionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Actualiza las preferencias de notificaciones del usuario (HU-21)."""
    return NotificacionService(db).actualizar_preferencias(user_id=current_user.id_usuario, req=req)


@router.post("", response_model=NotificacionDTO | None, status_code=status.HTTP_201_CREATED)
def crear_notificacion_manual(
    req: CrearNotificacionInternaRequest,
    db: Session = Depends(get_db),
    _superadmin: AlcanceStaff = Depends(get_superadmin),
):
    """Emite una notificación manual para cualquier usuario. Solo el superadministrador:
    los avisos de mensajes, entrevistas y etapas los genera el propio backend."""
    return NotificacionService(db).crear_notificacion(req=req)


# ─── Endpoints Firebase Cloud Messaging (FCM) — HU-21 ─────────────────────────


@router.post("/fcm/registrar-token", status_code=status.HTTP_200_OK)
def registrar_token_fcm(
    req: RegistrarDeviceTokenRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Registra o actualiza el FCM token del dispositivo (Web o Móvil) para recibir Push."""
    return NotificacionService(db).registrar_fcm_token(
        user_id=current_user.id_usuario,
        fcm_token=req.fcm_token,
        device_type=req.device_type,
        device_name=req.device_name,
    )


@router.post("/fcm/eliminar-token", status_code=status.HTTP_200_OK)
def eliminar_token_fcm(
    req: EliminarDeviceTokenRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Desactiva un token FCM al cerrar sesión."""
    return NotificacionService(db).eliminar_fcm_token(fcm_token=req.fcm_token, user_id=current_user.id_usuario)


@router.post("/fcm/test-push", status_code=status.HTTP_200_OK)
def enviar_test_push_fcm(
    req: TestPushFCMRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Envía un Push de prueba vía Firebase Cloud Messaging al usuario autenticado."""
    return NotificacionService(db).enviar_test_push_fcm(
        user_id=current_user.id_usuario,
        title=req.title,
        body=req.body,
        link=req.link,
    )

