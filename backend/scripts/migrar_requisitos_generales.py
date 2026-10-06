"""Migración aditiva e idempotente para los requisitos generales de la materia.

- audit_log.payload_cifrado: la bitácora confidencial guarda cada entrada cifrada acá
  (requisito 3). Las entradas viejas se cifran aparte con scripts.cifrar_bitacora.
- system_backup.kind admite 'automatica': la copia diaria de las tareas programadas.
- scheduled_task_run: historial de las tareas automáticas diarias (copia de seguridad,
  cierre de vacantes vencidas y boletín de ofertas). Sin claves foráneas: igual que el
  catálogo de copias, sobrevive a una restauración.

El backend también la aplica sola al arrancar (app/core/esquema.py); este script sirve
para aplicarla a mano antes de desplegar.

Uso (desde la carpeta backend):
    python -m scripts.migrar_requisitos_generales
"""

from app.core.database import engine
from app.core.esquema import asegurar_esquema_requisitos


def ejecutar() -> None:
    with engine.begin() as conn:
        cambios = asegurar_esquema_requisitos(conn)
    print("Listo: " + (", ".join(cambios) if cambios else "el esquema ya estaba al día."))


if __name__ == "__main__":
    ejecutar()
