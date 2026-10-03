import uuid
from datetime import datetime, timezone
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.notificacion import Notification, NotificationPreference


class NotificacionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def listar_notificaciones(
        self, user_id: uuid.UUID, limit: int = 50, offset: int = 0, solo_no_leidas: bool = False
    ) -> tuple[list[Notification], int, int]:
        """Obtiene las notificaciones paginadas del usuario junto con el conteo total y no leídas."""
        # 1. Conteo de no leídas
        stmt_unread = (
            select(func.count(Notification.id))
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        no_leidas = self.db.scalar(stmt_unread) or 0

        # 2. Conteo total según filtro
        stmt_total = select(func.count(Notification.id)).where(Notification.user_id == user_id)
        if solo_no_leidas:
            stmt_total = stmt_total.where(Notification.read_at.is_(None))
        total = self.db.scalar(stmt_total) or 0

        # 3. Listado ordenado por fecha de creación desc
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if solo_no_leidas:
            stmt = stmt.where(Notification.read_at.is_(None))

        items = list(self.db.scalars(stmt).all())
        return items, total, no_leidas

    def contar_no_leidas(self, user_id: uuid.UUID) -> int:
        """Cuenta rápidamente las notificaciones no leídas para la campanita del navbar."""
        stmt = (
            select(func.count(Notification.id))
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        return self.db.scalar(stmt) or 0

    def obtener_notificacion_por_id(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> Notification | None:
        """Obtiene una notificación por su ID validando propiedad del usuario."""
        stmt = select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
        return self.db.scalar(stmt)

    def marcar_leida(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> Notification | None:
        """Marca una notificación específica como leída."""
        notif = self.obtener_notificacion_por_id(notification_id, user_id)
        if notif and notif.read_at is None:
            notif.read_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(notif)
        return notif

    def marcar_todas_leidas(self, user_id: uuid.UUID) -> int:
        """Marca todas las notificaciones pendientes del usuario como leídas."""
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=datetime.now(timezone.utc))
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount or 0

    def eliminar_notificacion(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Elimina una notificación del historial."""
        notif = self.obtener_notificacion_por_id(notification_id, user_id)
        if notif:
            self.db.delete(notif)
            self.db.commit()
            return True
        return False

    def obtener_o_crear_preferencias(self, user_id: uuid.UUID) -> NotificationPreference:
        """Obtiene las preferencias de notificación del usuario o crea las por defecto."""
        stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        pref = self.db.scalar(stmt)
        if not pref:
            pref = NotificationPreference(
                user_id=user_id,
                email_notifications=True,
                notify_stage_changes=True,
                notify_job_matches=True,
                notify_interview_events=True,
                notify_messages=True,
            )
            self.db.add(pref)
            self.db.commit()
            self.db.refresh(pref)
        return pref

    def actualizar_preferencias(self, user_id: uuid.UUID, update_dict: dict) -> NotificationPreference:
        """Actualiza las preferencias de notificación del usuario."""
        pref = self.obtener_o_crear_preferencias(user_id)
        for key, value in update_dict.items():
            if value is not None and hasattr(pref, key):
                setattr(pref, key, value)
        pref.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(pref)
        return pref

    def crear_notificacion(
        self,
        user_id: uuid.UUID,
        notification_type: str,
        title: str,
        body: str | None = None,
        link: str | None = None,
    ) -> Notification | None:
        """Crea una notificación en BD verificando antes las preferencias del usuario."""
        pref = self.obtener_o_crear_preferencias(user_id)

        # Validar preferencias según el tipo de notificación
        if notification_type in ("stage_change", "application_status") and not pref.notify_stage_changes:
            return None
        if notification_type in ("job_match", "vacante_afinidad") and not pref.notify_job_matches:
            return None
        if notification_type in ("interview_scheduled", "interview_confirmed", "interview_rejected") and not pref.notify_interview_events:
            return None
        if notification_type in ("message_received", "mensaje_nuevo") and not pref.notify_messages:
            return None

        notif = Notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title.strip(),
            body=body.strip() if body else None,
            link=link.strip() if link else None,
        )
        self.db.add(notif)
        self.db.commit()
        self.db.refresh(notif)
        return notif
