"""Bitácora del sistema (requisito general 3: bitácora confidencial).

Registra usuario, IP, fecha y hora, módulo, acción y resultado de las operaciones. Con
BITACORA_CLAVE_PUBLICA configurada cada entrada se guarda cifrada (ver
app/security/cifrado_bitacora.py) y solo se lee desde el sistema con la clave de
desarrollador. Las entradas anteriores sin cifrar se muestran igual hasta que se corre
scripts.cifrar_bitacora.
"""

import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import null, select
from sqlalchemy.orm import Session

from app.common.exceptions import AppException
from app.core.config import get_settings
from app.features.bitacora.repository import BitacoraRepository
from app.models.seguridad import AuditLog
from app.models.usuario import AppUser
from app.security import cifrado_bitacora as cifrado
from app.security.tenant import usuarios_de_institucion
from app.shared.exportacion import Tabla, a_excel, a_pdf, texto_celda

logger = logging.getLogger(__name__)

CIFRADO = "cifrado"
_COLUMNAS = ["Fecha", "Usuario", "IP", "Módulo", "Acción", "Resultado", "Detalles"]
_INTENTOS_MAXIMOS = 5
_VENTANA_INTENTOS = 15 * 60
_fallos_por_usuario: dict[str, deque[float]] = defaultdict(deque)


class BitacoraBloqueada(AppException):
    """Falta la clave de desarrollador o no es la correcta (la pantalla pide la clave)."""

    status_code = 423


class DemasiadosIntentos(AppException):
    status_code = 429


@dataclass
class EntradaBitacora:
    id: uuid.UUID
    fecha: datetime
    usuario_id: uuid.UUID | None
    ip: str | None
    modulo: str
    accion: str
    resultado: bool
    detalles: str | None
    cifrada: bool
    usuario_correo: str | None = None


@dataclass
class FiltrosBitacora:
    usuario_id: uuid.UUID | None = None
    usuario: str | None = None  # parte del correo
    modulo: str | None = None
    accion: str | None = None
    fecha_desde: datetime | None = None
    fecha_hasta: datetime | None = None
    excluir_acciones: tuple[str, ...] = ()
    limite: int | None = None


def _clave_publica() -> str | None:
    clave = get_settings().bitacora_clave_publica
    return clave.strip() if clave and clave.strip() else None


def _con_zona(valor: datetime) -> datetime:
    return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)


class BitacoraService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = BitacoraRepository(db)

    @staticmethod
    def cifrado_activo() -> bool:
        return _clave_publica() is not None

    def registrar(
        self,
        modulo: str,
        accion: str,
        usuario_id: uuid.UUID | str | None = None,
        ip: str | None = None,
        detalles: str | None = None,
        resultado: bool = True,
    ) -> AuditLog:
        clave = _clave_publica()
        if clave is None:
            log = AuditLog(
                user_id=usuario_id,
                ip_address=ip,
                entity_type=modulo,
                action=accion,
                result="success" if resultado else "failure",
                details_json={"detalle": detalles} if detalles else None,
            )
            return self.repo.registrar(log)

        ahora = datetime.now(timezone.utc)
        datos = {
            "u": str(usuario_id) if usuario_id else None,
            "ip": ip,
            "m": modulo,
            "a": accion,
            "r": bool(resultado),
            "d": detalles,
            "f": ahora.isoformat(),
        }
        log = AuditLog(
            user_id=None,
            ip_address=None,
            entity_type=CIFRADO,
            action=CIFRADO,
            result="success",
            details_json=null(),
            payload_cifrado=cifrado.cifrar(datos, clave),
            # La base solo ve el día; la hora exacta va dentro del cifrado.
            created_at=ahora.replace(hour=0, minute=0, second=0, microsecond=0),
        )
        return self.repo.registrar(log)

    # ─── Lectura (con la clave de desarrollador) ─────────────────────────────

    def estado(self) -> dict:
        return {"cifrada": self.cifrado_activo(), "entradas_sin_cifrar": self.repo.contar_sin_cifrar()}

    def abrir(self, clave: str | None, usuario_id: uuid.UUID, ip: str | None) -> None:
        """Comprueba la clave al abrir la pantalla y deja constancia del acceso."""
        if self._lector(clave, usuario_id, ip) is not None:
            self.registrar(modulo="bitacora", accion="abrir_bitacora", usuario_id=usuario_id, ip=ip)
            self.db.commit()

    def _lector(self, clave: str | None, usuario_id: uuid.UUID, ip: str | None) -> cifrado.Lector | None:
        publica = _clave_publica()
        if publica is None:
            return None
        if not clave or not clave.strip():
            raise BitacoraBloqueada("La bitácora es confidencial: ingresá la clave de desarrollador para leerla.")
        fallos = _fallos_por_usuario[str(usuario_id)]
        ahora = time.monotonic()
        while fallos and ahora - fallos[0] > _VENTANA_INTENTOS:
            fallos.popleft()
        if len(fallos) >= _INTENTOS_MAXIMOS:
            raise DemasiadosIntentos("Demasiados intentos con una clave incorrecta. Esperá 15 minutos.")
        try:
            return cifrado.Lector(clave, publica)
        except cifrado.ClaveIncorrecta:
            fallos.append(ahora)
            self.registrar(
                modulo="bitacora", accion="clave_bitacora_incorrecta", usuario_id=usuario_id, ip=ip, resultado=False
            )
            self.db.commit()
            raise BitacoraBloqueada("La clave de desarrollador no es correcta.") from None

    def listar(
        self,
        filtros: FiltrosBitacora,
        institution_id: uuid.UUID | None,
        clave: str | None,
        usuario_id: uuid.UUID,
        ip: str | None = None,
    ) -> list[EntradaBitacora]:
        lector = self._lector(clave, usuario_id, ip)
        # created_at tiene al menos el día de la entrada: sirve para no leer de más.
        desde = _con_zona(filtros.fecha_desde) - timedelta(days=1) if filtros.fecha_desde else None
        hasta = _con_zona(filtros.fecha_hasta) + timedelta(days=1) if filtros.fecha_hasta else None
        entradas = [e for log in self.repo.entradas(desde, hasta) if (e := self._entrada(log, lector)) is not None]

        if institution_id is not None:
            del_tenant = set(self.db.scalars(usuarios_de_institucion(institution_id)))
            entradas = [e for e in entradas if e.usuario_id in del_tenant]
        entradas = [e for e in entradas if self._cumple(e, filtros)]
        self._completar_correos(entradas)
        if filtros.usuario:
            buscado = filtros.usuario.strip().lower()
            entradas = [e for e in entradas if e.usuario_correo and buscado in e.usuario_correo.lower()]
        entradas.sort(key=lambda e: e.fecha, reverse=True)
        return entradas[: filtros.limite] if filtros.limite else entradas

    @staticmethod
    def _entrada(log: AuditLog, lector: cifrado.Lector | None) -> EntradaBitacora | None:
        if log.payload_cifrado is None:
            return EntradaBitacora(
                id=log.id,
                fecha=_con_zona(log.created_at),
                usuario_id=log.user_id,
                ip=log.ip_address,
                modulo=log.entity_type,
                accion=log.action,
                resultado=log.resultado,
                detalles=log.detalles,
                cifrada=False,
            )
        if lector is None:
            return None  # cifrada pero sin clave pública configurada: no se puede leer
        try:
            datos = lector.descifrar(log.payload_cifrado)
            return EntradaBitacora(
                id=log.id,
                fecha=datetime.fromisoformat(datos["f"]),
                usuario_id=uuid.UUID(datos["u"]) if datos.get("u") else None,
                ip=datos.get("ip"),
                modulo=datos["m"],
                accion=datos["a"],
                resultado=bool(datos.get("r", True)),
                detalles=datos.get("d"),
                cifrada=True,
            )
        except Exception:
            logger.warning("No se pudo descifrar la entrada de bitácora %s", log.id)
            return None

    @staticmethod
    def _cumple(e: EntradaBitacora, f: FiltrosBitacora) -> bool:
        if f.usuario_id is not None and e.usuario_id != f.usuario_id:
            return False
        if f.modulo and f.modulo.strip().lower() not in e.modulo.lower():
            return False
        if f.accion and f.accion.strip().lower() not in e.accion.lower():
            return False
        if f.fecha_desde and e.fecha < _con_zona(f.fecha_desde):
            return False
        if f.fecha_hasta and e.fecha > _con_zona(f.fecha_hasta):
            return False
        return e.accion not in f.excluir_acciones

    def _completar_correos(self, entradas: list[EntradaBitacora]) -> None:
        ids = {e.usuario_id for e in entradas if e.usuario_id}
        if not ids:
            return
        correos = dict(self.db.execute(select(AppUser.id, AppUser.email).where(AppUser.id.in_(ids))).tuples().all())
        for e in entradas:
            e.usuario_correo = correos.get(e.usuario_id) if e.usuario_id else None

    # ─── Exportación ─────────────────────────────────────────────────────────

    @staticmethod
    def _tabla(entradas: list[EntradaBitacora], descripcion: list[str]) -> Tabla:
        return Tabla(
            titulo="Bitácora del sistema - EGRESA",
            encabezados=_COLUMNAS,
            filas=[
                [
                    e.fecha,
                    e.usuario_correo or (str(e.usuario_id) if e.usuario_id else "Sistema"),
                    e.ip or "",
                    e.modulo,
                    e.accion,
                    "Éxito" if e.resultado else "Fallo",
                    e.detalles or "",
                ]
                for e in entradas
            ],
            descripcion=descripcion,
        )

    def exportar_excel(self, entradas: list[EntradaBitacora], descripcion: list[str]) -> bytes:
        return a_excel(self._tabla(entradas, descripcion))

    def exportar_pdf(self, entradas: list[EntradaBitacora], descripcion: list[str]) -> bytes:
        return a_pdf(self._tabla(entradas, descripcion))


def descripcion_exportacion(correo: str | None, total: int) -> list[str]:
    ahora = texto_celda(datetime.now(timezone.utc))
    return [f"Generado el {ahora} (hora de Bolivia) por {correo or 'administrador'}.", f"{total} registros."]
