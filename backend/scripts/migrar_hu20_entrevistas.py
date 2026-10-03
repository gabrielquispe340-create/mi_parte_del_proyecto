"""Migración aditiva e idempotente para HU-20: Agenda de entrevistas.

Crea la tabla `interview` e índices necesarios si no existen.

Uso:
    python -m scripts.migrar_hu20_entrevistas
"""

from sqlalchemy import text
from app.core.database import engine

DDL = [
    """CREATE TABLE IF NOT EXISTS interview (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        application_id UUID NOT NULL REFERENCES application(id) ON DELETE CASCADE,
        scheduled_start TIMESTAMPTZ NOT NULL,
        scheduled_end TIMESTAMPTZ,
        modality VARCHAR(20) NOT NULL,
        location VARCHAR(300),
        meeting_url VARCHAR(500),
        notes TEXT,
        status VARCHAR(30) NOT NULL DEFAULT 'pending_confirmation',
        candidate_feedback TEXT,
        rejection_count INTEGER NOT NULL DEFAULT 0,
        requires_manual_review BOOLEAN NOT NULL DEFAULT FALSE,
        created_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT ck_interview_modality CHECK (modality IN ('onsite', 'virtual')),
        CONSTRAINT ck_interview_status CHECK (status IN ('pending_confirmation', 'confirmed', 'rejected', 'cancelled', 'completed'))
    )""",
    # La Supabase compartida ya tenía una tabla `interview` del diseño original (sin estas
    # columnas y con otros estados), así que el CREATE TABLE de arriba no la modifica.
    "ALTER TABLE interview ADD COLUMN IF NOT EXISTS notes TEXT",
    "ALTER TABLE interview ADD COLUMN IF NOT EXISTS candidate_feedback TEXT",
    "ALTER TABLE interview ADD COLUMN IF NOT EXISTS rejection_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE interview ADD COLUMN IF NOT EXISTS requires_manual_review BOOLEAN NOT NULL DEFAULT FALSE",
    # Estados de HU-20 sin dejar de aceptar los del diseño original (aditivo).
    "ALTER TABLE interview DROP CONSTRAINT IF EXISTS ck_iv_status",
    """ALTER TABLE interview ADD CONSTRAINT ck_iv_status CHECK (status IN (
        'pending_confirmation', 'confirmed', 'rejected', 'cancelled', 'completed', 'scheduled', 'no_show'
    ))""",
    "CREATE INDEX IF NOT EXISTS ix_interview_application_id ON interview (application_id)",
    "CREATE INDEX IF NOT EXISTS ix_interview_status ON interview (status)",
]


def ejecutar() -> None:
    with engine.begin() as conn:
        print("[1/2] Aplicando cambios de esquema para HU-20 entrevistas...")
        for sentencia in DDL:
            conn.execute(text(sentencia))
        print("[2/2] Índices y tabla interview listos.")
    print("Listo: migración HU-20 aplicada exitosamente.")


if __name__ == "__main__":
    ejecutar()
