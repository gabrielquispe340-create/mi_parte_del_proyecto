"""Backup/Restore de todo el sistema (requisito general 6 de la materia).

Solo el superadmin del SaaS: una copia contiene los datos de todas las universidades.
Antes de cada restauración real se toma una copia automática para poder volver atrás.
"""

import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException, ResourceNotFoundException
from app.core.config import get_settings
from app.features.bitacora.service import BitacoraService
from app.features.respaldos import motor
from app.features.respaldos.schema import RespaldoResponse, RestauracionResponse, RestaurarRequest
from app.models.respaldo import SystemBackup
from app.models.usuario import AppUser
from app.security.password_hasher import verify_password
from app.security.tenant import AlcanceStaff

_MODULO = "respaldos"
_AUTOR_SISTEMA = "Sistema (tarea diaria)"
_CONFIRMACION = "RESTAURAR"
_MAX_SUBIDA = 200 * 1024 * 1024


def carpeta_respaldos() -> Path:
    carpeta = Path(get_settings().storage_local_path) / "respaldos"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


class RespaldoService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.bitacora = BitacoraService(db)

    def listar(self) -> list[RespaldoResponse]:
        stmt = select(SystemBackup).order_by(SystemBackup.created_at.desc())
        return [self._dto(r) for r in self.db.scalars(stmt)]

    def crear(self, alcance: AlcanceStaff, ip: str | None, nota: str | None = None) -> RespaldoResponse:
        respaldo = self._generar(alcance, kind="manual", nota=nota)
        self.bitacora.registrar(
            modulo=_MODULO,
            accion="crear_respaldo",
            usuario_id=alcance.usuario.id_usuario,
            ip=ip,
            detalles=f"archivo={respaldo.file_name} tablas={respaldo.tables_count} filas={respaldo.rows_count}",
        )
        self.db.commit()
        return self._dto(respaldo)

    def subir(self, archivo: UploadFile, alcance: AlcanceStaff, ip: str | None) -> RespaldoResponse:
        """Registra un .zip descargado antes (p. ej. de otro servidor) para poder restaurarlo."""
        nombre = Path(archivo.filename or "respaldo.zip").name
        if not nombre.lower().endswith(".zip"):
            raise BusinessException("Subí el archivo .zip que descargaste desde Respaldos.")
        destino = carpeta_respaldos() / f"subido-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}.zip"
        escrito = 0
        with destino.open("wb") as salida:
            while bloque := archivo.file.read(1024 * 1024):
                escrito += len(bloque)
                if escrito > _MAX_SUBIDA:
                    salida.close()
                    destino.unlink(missing_ok=True)
                    raise BusinessException("El archivo supera los 200 MB.")
                salida.write(bloque)
        try:
            manifiesto = motor.leer_manifiesto(destino)
        except BusinessException:
            destino.unlink(missing_ok=True)
            raise
        usuario = self._usuario(alcance)
        respaldo = SystemBackup(
            file_name=destino.name,
            size_bytes=escrito,
            sha256=motor.sha256_de(destino),
            tables_count=len(manifiesto["tablas"]),
            rows_count=sum(int(t.get("filas", 0)) for t in manifiesto["tablas"]),
            kind="subido",
            note=f"Subido: {nombre} (copia del {manifiesto.get('creado_en', '')[:10]})",
            created_by=usuario.id,
            created_by_email=usuario.email,
        )
        self.db.add(respaldo)
        self.db.flush()
        self.bitacora.registrar(
            modulo=_MODULO, accion="subir_respaldo", usuario_id=usuario.id, ip=ip, detalles=f"archivo={nombre}"
        )
        self.db.commit()
        return self._dto(respaldo)

    def archivo_para_descargar(self, respaldo_id: uuid.UUID, alcance: AlcanceStaff, ip: str | None) -> Path:
        respaldo = self._respaldo(respaldo_id)
        ruta = self._ruta_verificada(respaldo)
        self.bitacora.registrar(
            modulo=_MODULO,
            accion="descargar_respaldo",
            usuario_id=alcance.usuario.id_usuario,
            ip=ip,
            detalles=f"archivo={respaldo.file_name}",
        )
        self.db.commit()
        return ruta

    def eliminar(self, respaldo_id: uuid.UUID, alcance: AlcanceStaff, ip: str | None) -> None:
        respaldo = self._respaldo(respaldo_id)
        (carpeta_respaldos() / respaldo.file_name).unlink(missing_ok=True)
        self.db.delete(respaldo)
        self.bitacora.registrar(
            modulo=_MODULO,
            accion="eliminar_respaldo",
            usuario_id=alcance.usuario.id_usuario,
            ip=ip,
            detalles=f"archivo={respaldo.file_name}",
        )
        self.db.commit()

    def restaurar(
        self, respaldo_id: uuid.UUID, data: RestaurarRequest, alcance: AlcanceStaff, ip: str | None
    ) -> RestauracionResponse:
        usuario = self._usuario(alcance)
        if not verify_password(data.password, usuario.password_hash):
            raise BusinessException("La contraseña no es correcta.")
        if not data.simulacro and data.confirmacion.strip().upper() != _CONFIRMACION:
            raise BusinessException(f"Para restaurar escribí {_CONFIRMACION} en la confirmación.")
        respaldo = self._respaldo(respaldo_id)
        ruta = self._ruta_verificada(respaldo)
        nombre = respaldo.file_name
        usuario_id, correo = usuario.id, usuario.email

        previo = None
        if not data.simulacro:
            previo = self._generar(alcance, kind="previa_restauracion", nota=f"Automática antes de restaurar {nombre}")
            self.db.commit()

        def registrar() -> None:
            # Si el superadmin no existía en la copia, la entrada queda sin usuario.
            existe = self.db.get(AppUser, usuario_id) is not None
            self.bitacora.registrar(
                modulo=_MODULO,
                accion="verificar_respaldo" if data.simulacro else "restaurar_respaldo",
                usuario_id=usuario_id if existe else None,
                ip=ip,
                detalles=f"archivo={nombre} por={correo}",
            )

        resultado = motor.restaurar(self.db, ruta, simulacro=data.simulacro, registrar_en_bitacora=registrar)

        if data.simulacro:
            # El simulacro deshace todo, incluida su entrada: se deja constancia aparte.
            self.bitacora.registrar(
                modulo=_MODULO,
                accion="verificar_respaldo",
                usuario_id=usuario_id,
                ip=ip,
                detalles=f"archivo={nombre} filas={resultado.filas}",
            )
            mensaje = (
                f"La copia se puede restaurar sin errores: {resultado.tablas} tablas y {resultado.filas} filas. "
                "No se cambió ningún dato."
            )
        else:
            respaldo = self._respaldo(respaldo_id)
            respaldo.last_restored_at = datetime.now(timezone.utc)
            mensaje = (
                f"Sistema restaurado: {resultado.tablas} tablas y {resultado.filas} filas. "
                f"Se conservaron {resultado.bitacora_conservada} entradas de bitácora posteriores a la copia."
            )
        self.db.commit()
        return RestauracionResponse(
            simulacro=data.simulacro,
            tablas=resultado.tablas,
            filas=resultado.filas,
            bitacora_conservada=resultado.bitacora_conservada,
            vaciadas_extra=resultado.vaciadas_extra,
            respaldo_previo=self._dto(previo) if previo else None,
            mensaje=mensaje,
        )

    # ─── Auxiliares ─────────────────────────────────────────────────────────

    def generar_automatico(self) -> tuple[SystemBackup, int]:
        """Copia diaria de las tareas programadas; conserva solo las últimas automáticas.

        Devuelve la copia nueva y cuántas copias automáticas viejas se eliminaron.
        """
        respaldo = self._generar(None, kind="automatica", nota="Copia diaria automática")
        conservar = max(get_settings().respaldos_automaticos_conservar, 1)
        viejas = self.db.scalars(
            select(SystemBackup)
            .where(SystemBackup.kind == "automatica")
            .order_by(SystemBackup.created_at.desc())
            .offset(conservar)
        ).all()
        for vieja in viejas:
            (carpeta_respaldos() / vieja.file_name).unlink(missing_ok=True)
            self.db.delete(vieja)
        self.bitacora.registrar(
            modulo=_MODULO,
            accion="respaldo_automatico",
            detalles=f"archivo={respaldo.file_name} filas={respaldo.rows_count} eliminadas={len(viejas)}",
        )
        self.db.commit()
        return respaldo, len(viejas)

    def _generar(self, alcance: AlcanceStaff | None, *, kind: str, nota: str | None) -> SystemBackup:
        # Sin alcance la genera el sistema (tarea diaria), no un usuario.
        usuario = self._usuario(alcance) if alcance is not None else None
        nombre = f"egresa-respaldo-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}.zip"
        destino = carpeta_respaldos() / nombre
        # Se escribe en un temporal y se mueve al final: nunca queda un .zip a medias.
        with tempfile.NamedTemporaryFile(dir=carpeta_respaldos(), suffix=".parcial", delete=False) as tmp:
            temporal = Path(tmp.name)
        try:
            resumen = motor.generar(temporal, autor=usuario.email if usuario else _AUTOR_SISTEMA)
            shutil.move(temporal, destino)
        finally:
            temporal.unlink(missing_ok=True)
        respaldo = SystemBackup(
            file_name=nombre,
            size_bytes=resumen.tamanio,
            sha256=resumen.sha256,
            tables_count=resumen.tablas,
            rows_count=resumen.filas,
            kind=kind,
            note=nota.strip() if nota and nota.strip() else None,
            created_by=usuario.id if usuario else None,
            created_by_email=usuario.email if usuario else _AUTOR_SISTEMA,
        )
        self.db.add(respaldo)
        self.db.flush()
        return respaldo

    def _usuario(self, alcance: AlcanceStaff) -> AppUser:
        usuario = self.db.get(AppUser, alcance.usuario.id_usuario)
        if usuario is None:
            raise ResourceNotFoundException("No se encontró tu usuario.")
        return usuario

    def _respaldo(self, respaldo_id: uuid.UUID) -> SystemBackup:
        respaldo = self.db.get(SystemBackup, respaldo_id)
        if respaldo is None:
            raise ResourceNotFoundException("No se encontró la copia de seguridad.")
        return respaldo

    @staticmethod
    def _ruta_verificada(respaldo: SystemBackup) -> Path:
        ruta = carpeta_respaldos() / respaldo.file_name
        if not ruta.is_file():
            raise BusinessException(
                "El archivo de esta copia ya no está en el servidor. Subí el .zip descargado para restaurarlo."
            )
        if motor.sha256_de(ruta) != respaldo.sha256:
            raise BusinessException("El archivo de la copia fue modificado o está dañado: no se puede usar.")
        return ruta

    @staticmethod
    def _dto(r: SystemBackup) -> RespaldoResponse:
        return RespaldoResponse(
            id=r.id,
            archivo=r.file_name,
            tamanio_bytes=r.size_bytes,
            tablas=r.tables_count,
            filas=r.rows_count,
            tipo=r.kind,
            nota=r.note,
            creado_por=r.created_by_email,
            fecha=r.created_at,
            ultima_restauracion=r.last_restored_at,
            disponible=(carpeta_respaldos() / r.file_name).is_file(),
        )
