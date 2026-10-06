"""Cambios de esquema aditivos e idempotentes que el backend asegura al arrancar.

Solo agregan lo que falta (nunca borran datos) y antes de cada ALTER se consulta el
catálogo, así un arranque normal no toma candados sobre tablas con tráfico. Sirve para que
un despliegue no dependa de que alguien haya corrido antes la migración a mano.
"""

from sqlalchemy import Connection, text

_TAREAS = """CREATE TABLE IF NOT EXISTS scheduled_task_run (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task varchar(50) NOT NULL,
    trigger varchar(20) NOT NULL DEFAULT 'automatico',
    status varchar(20) NOT NULL DEFAULT 'running',
    summary varchar(500),
    triggered_by_email varchar(255),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    CONSTRAINT ck_task_run_trigger CHECK (trigger IN ('automatico', 'manual')),
    CONSTRAINT ck_task_run_status CHECK (status IN ('running', 'success', 'failure'))
)"""


def asegurar_esquema_requisitos(conn: Connection) -> list[str]:
    """Bitácora cifrada, copias automáticas y tareas programadas. Devuelve lo que cambió."""
    cambios: list[str] = []

    # En una base nueva las tablas todavía no existen: las crea después create_all con todo.
    existe_bitacora = conn.execute(text("SELECT to_regclass('public.audit_log')")).scalar() is not None
    tiene_payload = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'audit_log' AND column_name = 'payload_cifrado'"
        )
    ).first()
    if existe_bitacora and tiene_payload is None:
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS payload_cifrado text"))
        cambios.append("audit_log.payload_cifrado")

    regla = conn.execute(
        text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'ck_system_backup_kind'")
    ).scalar()
    if regla is not None and "automatica" not in regla:
        conn.execute(text("ALTER TABLE system_backup DROP CONSTRAINT ck_system_backup_kind"))
        conn.execute(
            text(
                "ALTER TABLE system_backup ADD CONSTRAINT ck_system_backup_kind "
                "CHECK (kind IN ('manual', 'previa_restauracion', 'subido', 'automatica'))"
            )
        )
        cambios.append("system_backup.kind admite 'automatica'")

    if conn.execute(text("SELECT to_regclass('public.scheduled_task_run')")).scalar() is None:
        conn.execute(text(_TAREAS))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_task_run_task_started ON scheduled_task_run (task, started_at DESC)")
        )
        conn.execute(text("ALTER TABLE scheduled_task_run ENABLE ROW LEVEL SECURITY"))
        cambios.append("scheduled_task_run")
    return cambios
