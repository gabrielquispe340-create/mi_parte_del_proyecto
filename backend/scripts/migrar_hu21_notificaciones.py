"""Migración aditiva e idempotente para HU-21: Notificaciones y preferencias.

Crea o altera la tabla `notification_preference`, asegura la estructura de `notification`
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

    # 2. Asegurar columnas en notification_preference
    """CREATE TABLE IF NOT EXISTS notification_preference (
        user_id UUID PRIMARY KEY REFERENCES app_user(id) ON DELETE CASCADE,
        email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        push_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        in_app_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        notify_stage_changes BOOLEAN NOT NULL DEFAULT TRUE,
        notify_job_matches BOOLEAN NOT NULL DEFAULT TRUE,
        notify_interview_events BOOLEAN NOT NULL DEFAULT TRUE,
        notify_messages BOOLEAN NOT NULL DEFAULT TRUE,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    "ALTER TABLE notification_preference ADD COLUMN IF NOT EXISTS email_enabled BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE notification_preference ADD COLUMN IF NOT EXISTS push_enabled BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE notification_preference ADD COLUMN IF NOT EXISTS in_app_enabled BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE notification_preference ADD COLUMN IF NOT EXISTS notify_stage_changes BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE notification_preference ADD COLUMN IF NOT EXISTS notify_job_matches BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE notification_preference ADD COLUMN IF NOT EXISTS notify_interview_events BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE notification_preference ADD COLUMN IF NOT EXISTS notify_messages BOOLEAN NOT NULL DEFAULT TRUE",
    # 3. Asegurar tabla user_device_token para Firebase Cloud Messaging (FCM)
    """CREATE TABLE IF NOT EXISTS user_device_token (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
        fcm_token VARCHAR(500) UNIQUE NOT NULL,
        device_type VARCHAR(20) NOT NULL DEFAULT 'web',
        device_name VARCHAR(100),
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    "CREATE INDEX IF NOT EXISTS ix_user_device_token_user_id ON user_device_token (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_user_device_token_fcm_token ON user_device_token (fcm_token)",
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

