"""Migración aditiva e idempotente para HU-21: Notificaciones y preferencias.

Crea la tabla `notification_preference`, asegura la estructura de `notification`
e indexa para consultas rápidas de historial y conteo de no leídas.

Uso:
    python -m scripts.migrar_hu21_notificaciones
"""

from sqlalchemy import text
from app.core.database import engine

DDL = [
    # 1. Asegurar tabla notification
    """CREATE TABLE IF NOT EXISTS notification (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
        notification_type VARCHAR(50) NOT NULL,
        title VARCHAR(200) NOT NULL,
        body TEXT,
        link VARCHAR(500),
        read_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    "CREATE INDEX IF NOT EXISTS ix_notification_user_id ON notification (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_notification_read_at ON notification (read_at)",
    "CREATE INDEX IF NOT EXISTS ix_notification_created_at ON notification (created_at DESC)",

    # 2. Tabla notification_preference para controlar qué notificaciones recibe cada usuario
    """CREATE TABLE IF NOT EXISTS notification_preference (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL UNIQUE REFERENCES app_user(id) ON DELETE CASCADE,
        email_notifications BOOLEAN NOT NULL DEFAULT TRUE,
        notify_stage_changes BOOLEAN NOT NULL DEFAULT TRUE,
        notify_job_matches BOOLEAN NOT NULL DEFAULT TRUE,
        notify_interview_events BOOLEAN NOT NULL DEFAULT TRUE,
        notify_messages BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    "CREATE INDEX IF NOT EXISTS ix_notif_pref_user_id ON notification_preference (user_id)",
]


def ejecutar() -> None:
    with engine.begin() as conn:
        print("[1/2] Aplicando cambios de esquema para HU-21 notificaciones y preferencias...")
        for sentencia in DDL:
            conn.execute(text(sentencia))
        print("[2/2] Tablas notification y notification_preference configuradas.")
    print("Listo: migración HU-21 aplicada exitosamente.")


if __name__ == "__main__":
    ejecutar()
