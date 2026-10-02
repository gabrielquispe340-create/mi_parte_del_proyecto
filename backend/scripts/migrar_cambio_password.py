"""Migración aditiva e idempotente: obligar a cambiar la contraseña inicial.

Agrega app_user.must_change_password (por defecto false). Las cuentas que crea un
administrador desde Gestión de roles nacen con true: la persona recibe una contraseña
temporal y debe reemplazarla en su primer ingreso. El código que no conoce la columna
sigue funcionando.

Uso (desde la carpeta backend):
    python -m scripts.migrar_cambio_password
"""

from sqlalchemy import text

from app.core.database import engine

DDL = "ALTER TABLE app_user ADD COLUMN IF NOT EXISTS must_change_password boolean NOT NULL DEFAULT false"


def ejecutar() -> None:
    with engine.begin() as conn:
        conn.execute(text(DDL))
    print("Listo: columna app_user.must_change_password disponible.")


if __name__ == "__main__":
    ejecutar()
