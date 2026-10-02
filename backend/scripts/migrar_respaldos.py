"""Migración aditiva e idempotente: catálogo de copias de seguridad (Backup/Restore).

- system_backup: una fila por copia (manual, subida o automática antes de restaurar). Los
  datos viven en un .zip en STORAGE_LOCAL_PATH/respaldos; esta tabla guarda el resumen y el
  hash para verificar que el archivo no se alteró.

No tiene claves foráneas a propósito: la restauración vacía y recarga el resto de las
tablas, y este catálogo debe sobrevivir intacto para poder volver atrás.

Uso (desde la carpeta backend):
    python -m scripts.migrar_respaldos
"""

from sqlalchemy import text

from app.core.database import engine

DDL = [
    """CREATE TABLE IF NOT EXISTS system_backup (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        file_name varchar(200) NOT NULL,
        size_bytes bigint NOT NULL,
        sha256 varchar(64) NOT NULL,
        tables_count integer NOT NULL,
        rows_count bigint NOT NULL,
        kind varchar(30) NOT NULL DEFAULT 'manual',
        note varchar(300),
        created_by uuid,
        created_by_email varchar(255),
        created_at timestamptz NOT NULL DEFAULT now(),
        last_restored_at timestamptz,
        CONSTRAINT ck_system_backup_kind CHECK (kind IN ('manual', 'previa_restauracion', 'subido'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_system_backup_created ON system_backup (created_at DESC)",
    "ALTER TABLE system_backup ENABLE ROW LEVEL SECURITY",
]


def ejecutar() -> None:
    with engine.begin() as conn:
        for sentencia in DDL:
            conn.execute(text(sentencia))
    print("Listo: tabla system_backup disponible.")


if __name__ == "__main__":
    ejecutar()
