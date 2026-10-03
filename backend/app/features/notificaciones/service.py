import uuid
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
        pref = self.repo.actualizar_preferencias(user_id, update_dict)
        return PreferenciasNotificacionDTO.model_validate(pref)

    def crear_notificacion(self, req: CrearNotificacionInternaRequest) -> NotificacionDTO | None:
        """Emite una notificación respetando las preferencias del destinatario."""
        notif = self.repo.crear_notificacion(
            user_id=req.user_id,
            notification_type=req.notification_type,
            title=req.title,
            body=req.body,
            link=req.link,
        )
        if not notif:
            return None

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
