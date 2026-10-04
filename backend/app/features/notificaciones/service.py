import uuid
from typing import Any
from sqlalchemy.orm import Session

from app.common.exceptions import ResourceNotFoundException
from app.features.notificaciones.repository import NotificacionRepository
from app.features.notificaciones.schema import (
    ContadorNoLeidasResponse,
    CrearNotificacionInternaRequest,
    NotificacionDTO,
    NotificacionesListResponse,
    PreferenciasNotificacionDTO,
    PreferenciasNotificacionUpdateRequest,
)


class NotificacionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = NotificacionRepository(db)

    def listar_notificaciones(
        self, user_id: uuid.UUID, limit: int = 50, offset: int = 0, solo_no_leidas: bool = False
    ) -> NotificacionesListResponse:
        """Obtiene la lista de notificaciones con formato DTO y estado leída."""
        items, total, no_leidas = self.repo.listar_notificaciones(
            user_id=user_id, limit=limit, offset=offset, solo_no_leidas=solo_no_leidas
        )

        dtos = [
            NotificacionDTO(
                id=item.id,
                user_id=item.user_id,
                notification_type=item.notification_type,
                title=item.title,
                body=item.body,
                link=item.link,
                read_at=item.read_at,
                created_at=item.created_at,
                leida=item.read_at is not None,
            )
            for item in items
        ]

        return NotificacionesListResponse(total=total, no_leidas=no_leidas, items=dtos)

    def contar_no_leidas(self, user_id: uuid.UUID) -> ContadorNoLeidasResponse:
        """Retorna el número de notificaciones no leídas."""
        cantidad = self.repo.contar_no_leidas(user_id)
        return ContadorNoLeidasResponse(no_leidas=cantidad)

    def marcar_como_leida(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> NotificacionDTO:
        """Marca una notificación como leída."""
        notif = self.repo.marcar_leida(notification_id, user_id)
        if not notif:
            raise ResourceNotFoundException("La notificación no existe o no pertenece al usuario.")

        return NotificacionDTO(
            id=notif.id,
            user_id=notif.user_id,
            notification_type=notif.notification_type,
            title=notif.title,
            body=notif.body,
            link=notif.link,
            read_at=notif.read_at,
            created_at=notif.created_at,
            leida=True,
        )

    def marcar_todas_como_leidas(self, user_id: uuid.UUID) -> dict[str, int]:
        """Marca todas las notificaciones pendientes como leídas."""
        afectadas = self.repo.marcar_todas_leidas(user_id)
        return {"actualizadas": afectadas}

    def eliminar_notificacion(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, bool]:
        """Elimina una notificación del historial."""
        exito = self.repo.eliminar_notificacion(notification_id, user_id)
        if not exito:
            raise ResourceNotFoundException("La notificación no existe o no pertenece al usuario.")
        return {"eliminado": True}

    def obtener_preferencias(self, user_id: uuid.UUID) -> PreferenciasNotificacionDTO:
        """Consulta la configuración de preferencias de notificaciones del usuario."""
        pref = self.repo.obtener_o_crear_preferencias(user_id)
        return PreferenciasNotificacionDTO.model_validate(pref)

    def actualizar_preferencias(
        self, user_id: uuid.UUID, req: PreferenciasNotificacionUpdateRequest
    ) -> PreferenciasNotificacionDTO:
        """Guarda los cambios en las preferencias de notificaciones del usuario."""
        update_dict = req.model_dump(exclude_unset=True)
        if "email_notifications" in update_dict and update_dict["email_notifications"] is not None:
            update_dict["email_enabled"] = update_dict.pop("email_notifications")
        pref = self.repo.actualizar_preferencias(user_id, update_dict)
        return PreferenciasNotificacionDTO.model_validate(pref)

    def crear_notificacion(self, req: CrearNotificacionInternaRequest) -> NotificacionDTO | None:
        """Emite una notificación respetando las preferencias del destinatario y envía Push FCM."""
        notif = self.repo.crear_notificacion(
            user_id=req.user_id,
            notification_type=req.notification_type,
            title=req.title,
            body=req.body,
            link=req.link,
        )
        if not notif:
            return None

        # Si el usuario tiene activo el canal Push, enviar notificación Firebase FCM
        pref = self.repo.obtener_o_crear_preferencias(req.user_id)
        if pref.push_enabled:
            from app.features.notificaciones import fcm_service

            fcm_service.enviar_push_fcm(
                db=self.db,
                user_id=req.user_id,
                title=req.title,
                body=req.body,
                link=req.link,
            )

        return NotificacionDTO(
            id=notif.id,
            user_id=notif.user_id,
            notification_type=notif.notification_type,
            title=notif.title,
            body=notif.body,
            link=notif.link,
            read_at=notif.read_at,
            created_at=notif.created_at,
            leida=False,
        )

    def registrar_fcm_token(
        self, user_id: uuid.UUID, fcm_token: str, device_type: str = "web", device_name: str | None = None
    ) -> dict[str, Any]:
        """Registra un token FCM de un dispositivo."""
        from app.features.notificaciones import fcm_service

        reg = fcm_service.registrar_token_dispositivo(
            db=self.db,
            user_id=user_id,
            fcm_token=fcm_token,
            device_type=device_type,
            device_name=device_name,
        )
        return {"registrado": True, "token_id": str(reg.id), "device_type": reg.device_type}

    def eliminar_fcm_token(self, fcm_token: str) -> dict[str, bool]:
        """Desactiva un token FCM."""
        from app.features.notificaciones import fcm_service

        exito = fcm_service.desactivar_token_dispositivo(self.db, fcm_token)
        return {"desactivado": exito}

    def enviar_test_push_fcm(
        self, user_id: uuid.UUID, title: str, body: str, link: str | None = None
    ) -> dict[str, Any]:
        """Envía un Push FCM de prueba directo al usuario."""
        from app.features.notificaciones import fcm_service

        return fcm_service.enviar_push_fcm(
            db=self.db,
            user_id=user_id,
            title=title,
            body=body,
            link=link,
        )

