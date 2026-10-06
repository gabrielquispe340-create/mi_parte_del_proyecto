"""Cifra las entradas de bitácora que quedaron en claro (anteriores a la bitácora confidencial).

Usa la clave pública de BITACORA_CLAVE_PUBLICA, la misma que el servidor. Cada entrada
pasa entera al campo cifrado y sus columnas en claro quedan vacías; created_at conserva
solo el día. Todo ocurre en una sola transacción: si algo falla, no cambia nada.

No se puede deshacer sin la clave de desarrollador: conviene hacer antes una copia de
seguridad desde Copias de seguridad.

Uso (desde la carpeta backend):
    python -m scripts.cifrar_bitacora              muestra cuántas entradas se cifrarían
    python -m scripts.cifrar_bitacora --confirmar  las cifra
"""

import json
import sys
from datetime import timezone

from sqlalchemy import null, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.features.bitacora.service import CIFRADO
from app.models.seguridad import AuditLog
from app.security.cifrado_bitacora import cifrar


def _detalle(log: AuditLog) -> str | None:
    if not log.details_json:
        return None
    if set(log.details_json) == {"detalle"}:
        valor = log.details_json["detalle"]
        return str(valor) if valor is not None else None
    return json.dumps(log.details_json, ensure_ascii=False)


def main() -> None:
    clave = (get_settings().bitacora_clave_publica or "").strip()
    if not clave:
        sys.exit("Falta BITACORA_CLAVE_PUBLICA en el .env (python -m scripts.clave_bitacora).")
    confirmar = "--confirmar" in sys.argv[1:]
    with SessionLocal() as db:
        pendientes = list(db.scalars(select(AuditLog).where(AuditLog.payload_cifrado.is_(None))))
        print(f"Entradas sin cifrar: {len(pendientes)}")
        if not confirmar:
            print("Nada cambió. Para cifrarlas: python -m scripts.cifrar_bitacora --confirmar")
            return
        for log in pendientes:
            fecha = log.created_at.astimezone(timezone.utc)
            log.payload_cifrado = cifrar(
                {
                    "u": str(log.user_id) if log.user_id else None,
                    "ip": log.ip_address,
                    "m": log.entity_type,
                    "a": log.action,
                    "r": log.result == "success",
                    "d": _detalle(log),
                    "f": fecha.isoformat(),
                },
                clave,
            )
            log.user_id = None
            log.ip_address = None
            log.details_json = null()
            log.entity_type = CIFRADO
            log.action = CIFRADO
            log.result = "success"
            log.created_at = fecha.replace(hour=0, minute=0, second=0, microsecond=0)
        db.commit()
        print(f"Listo: {len(pendientes)} entradas cifradas.")


if __name__ == "__main__":
    main()
