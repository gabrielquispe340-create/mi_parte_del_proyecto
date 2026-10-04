import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.common.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.core.config import get_settings
from app.features.bitacora.service import BitacoraService
from app.features.comunicacion.repository import ComunicacionRepository
from app.features.comunicacion.schema import (
    AdjuntoMensajeOut,
    ConversacionPostulacionOut,
    MensajeOut,
)
from app.models.comunicacion import Conversation, Message
from app.models.postulacion import Application

_MODULO = "comunicacion"
MAX_TAMANO_ADJUNTO_BYTES = 5 * 1024 * 1024  # 5 MB exactos (criterio de aceptación HU-19)


def carpeta_mensajes() -> Path:
    carpeta = Path(get_settings().storage_local_path) / "mensajes"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _limpiar_nombre_archivo(nombre: str) -> str:
    base = Path(nombre or "adjunto").name.strip()
    limpio = re.sub(r"[^\w.\-() ]+", "_", base)
    return limpio[:180] or "adjunto"


class ComunicacionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ComunicacionRepository(db)
        self.bitacora = BitacoraService(db)

    def _validar_acceso_postulacion(
        self, user_id: uuid.UUID, application_id: uuid.UUID
    ) -> tuple[Application, str]:
        """Verifica que la postulación exista y que el usuario sea el candidato o miembro de la empresa.

        Garantiza el criterio: 'El candidato solo puede recibir mensajes de empresas a las que se postuló'.
        """
        app = self.repo.obtener_postulacion(application_id)
        if not app:
            raise NotFoundException("La postulación indicada no existe.")

        # Caso 1: Es el candidato dueño de la postulación
        if app.candidate and app.candidate.user_id == user_id:
            return app, "candidato"

        # Caso 2: Es reclutador/miembro activo de la empresa dueña de la vacante
        if app.job_posting and app.job_posting.company_id:
            miembro = self.repo.obtener_miembro_empresa(
                user_id, app.job_posting.company_id
            )
            if miembro:
                return app, "empresa"

        raise ForbiddenException(
            "No tienes permiso para acceder a esta conversación. Solo pueden comunicarse el candidato postulado y la empresa titular de la vacante."
        )

    def _metadatos_postulacion(self, app: Application) -> tuple[str, str, str, Optional[str]]:
        vacante_titulo = app.job_posting.title if app.job_posting else "Vacante"
        empresa_nombre = "Empresa"
        if app.job_posting and app.job_posting.company:
            empresa_nombre = (
                app.job_posting.company.trade_name
                or app.job_posting.company.legal_name
                or "Empresa"
            )
        candidato_nombre = "Candidato"
        candidato_carrera: Optional[str] = None
        if app.candidate:
            candidato_nombre = f"{app.candidate.first_name} {app.candidate.last_name}".strip()
            for edu in app.candidate.educations or []:
                if edu.field_of_study and edu.field_of_study.name:
                    candidato_carrera = edu.field_of_study.name
                    break
                # CandidateEducation no tiene degree_title: el nombre de la carrera
                # cargada a mano está en program_name.
                if edu.program_name:
                    candidato_carrera = edu.program_name
                    break
        return vacante_titulo, empresa_nombre, candidato_nombre, candidato_carrera

    def _mapear_mensaje(
        self,
        msg: Message,
        current_user_id: uuid.UUID,
        candidato_user_id: Optional[uuid.UUID],
        candidato_nombre: str,
        empresa_nombre: str,
    ) -> MensajeOut:
        es_candidato = candidato_user_id is not None and msg.sender_id == candidato_user_id
        sender_rol = "candidato" if es_candidato else "empresa"
        sender_nombre = candidato_nombre if es_candidato else empresa_nombre

        adjunto_out: Optional[AdjuntoMensajeOut] = None
        if msg.attachments:
            adj = msg.attachments[0]
            adjunto_out = AdjuntoMensajeOut(
                id=adj.id,
                original_filename=adj.original_filename,
                mime_type=adj.mime_type,
                file_size=adj.file_size,
                created_at=adj.created_at,
            )

        return MensajeOut(
            id=msg.id,
            conversation_id=msg.conversation_id,
            sender_id=msg.sender_id,
            sender_nombre=sender_nombre,
            sender_rol=sender_rol,
            es_mio=(msg.sender_id == current_user_id),
            content=msg.content,
            created_at=msg.created_at,
            adjunto=adjunto_out,
        )

    def _calcular_no_leidos(
        self, conv: Optional[Conversation], user_id: uuid.UUID
    ) -> int:
        if not conv or not conv.messages:
            return 0
        last_read: Optional[datetime] = None
        for m in conv.members or []:
            if m.user_id == user_id:
                last_read = m.last_read_at
                break
        no_leidos = 0
        for msg in conv.messages:
            if msg.deleted_at is not None or msg.sender_id == user_id:
                continue
            if last_read is None or msg.created_at > last_read:
                no_leidos += 1
        return no_leidos

    def obtener_conversacion_postulacion(
        self,
        user_id: uuid.UUID,
        application_id: uuid.UUID,
        marcar_como_leido: bool = True,
    ) -> ConversacionPostulacionOut:
        app, _ = self._validar_acceso_postulacion(user_id, application_id)
        vacante_titulo, empresa_nombre, candidato_nombre, candidato_carrera = (
            self._metadatos_postulacion(app)
        )
        candidato_user_id = app.candidate.user_id if app.candidate else None

        conv = self.repo.obtener_conversacion_por_postulacion(application_id)
        if not conv:
            return ConversacionPostulacionOut(
                conversation_id=None,
                application_id=app.id,
                vacante_titulo=vacante_titulo,
                empresa_nombre=empresa_nombre,
                candidato_nombre=candidato_nombre,
                candidato_carrera=candidato_carrera,
                estado_postulacion=app.current_status,
                total_mensajes=0,
                no_leidos=0,
                mensajes=[],
            )

        no_leidos = self._calcular_no_leidos(conv, user_id)
        if marcar_como_leido:
            self.repo.marcar_leido(conv.id, user_id)
            self.db.commit()
            no_leidos = 0

        mensajes_activos = [m for m in (conv.messages or []) if m.deleted_at is None]
        mensajes_out = [
            self._mapear_mensaje(
                m,
                current_user_id=user_id,
                candidato_user_id=candidato_user_id,
                candidato_nombre=candidato_nombre,
                empresa_nombre=empresa_nombre,
            )
            for m in mensajes_activos
        ]

        return ConversacionPostulacionOut(
            conversation_id=conv.id,
            application_id=app.id,
            vacante_titulo=vacante_titulo,
            empresa_nombre=empresa_nombre,
            candidato_nombre=candidato_nombre,
            candidato_carrera=candidato_carrera,
            estado_postulacion=app.current_status,
            total_mensajes=len(mensajes_out),
            no_leidos=no_leidos,
            mensajes=mensajes_out,
        )

    def enviar_mensaje(
        self,
        user_id: uuid.UUID,
        application_id: uuid.UUID,
        contenido: Optional[str] = None,
        archivo: Optional[UploadFile] = None,
        ip: str = "127.0.0.1",
    ) -> MensajeOut:
        app, rol_emisor = self._validar_acceso_postulacion(user_id, application_id)
        texto = (contenido or "").strip()

        if not texto and not archivo:
            raise BadRequestException(
                "Debes escribir un mensaje de texto o adjuntar un archivo."
            )

        # Validar archivo adjunto antes de persistir (máx. 5 MB)
        bytes_archivo: Optional[bytes] = None
        nombre_original: Optional[str] = None
        mime_type: Optional[str] = None

        if archivo and archivo.filename:
            nombre_original = _limpiar_nombre_archivo(archivo.filename)
            mime_type = archivo.content_type or "application/octet-stream"
            bytes_archivo = archivo.file.read(MAX_TAMANO_ADJUNTO_BYTES + 1)
            if len(bytes_archivo) == 0:
                raise BadRequestException("El archivo adjunto está vacío.")
            if len(bytes_archivo) > MAX_TAMANO_ADJUNTO_BYTES:
                raise BadRequestException(
                    "El archivo adjunto supera el tamaño máximo permitido de 5 MB."
                )

        if not texto and nombre_original:
            texto = f"Archivo adjunto: {nombre_original}"

        vacante_titulo, empresa_nombre, candidato_nombre, _ = (
            self._metadatos_postulacion(app)
        )
        candidato_user_id = app.candidate.user_id if app.candidate else None

        # Obtener o crear el hilo asociado a la postulación
        conv = self.repo.obtener_conversacion_por_postulacion(application_id)
        if not conv:
            participantes: list[uuid.UUID] = [user_id]
            if candidato_user_id:
                participantes.append(candidato_user_id)
            if app.job_posting and app.job_posting.company_id:
                for m in self.repo.obtener_miembros_activos_empresa(
                    app.job_posting.company_id
                ):
                    participantes.append(m.user_id)
            conv = self.repo.crear_conversacion_postulacion(
                application_id=application_id,
                user_ids=participantes,
            )
        else:
            self.repo.asegurar_miembro(conv.id, user_id)

        msg = self.repo.crear_mensaje(
            conversation=conv,
            sender_id=user_id,
            content=texto,
        )

        # Si hay archivo adjunto, guardarlo en disco y registrar en message_attachment
        if bytes_archivo is not None and nombre_original:
            subcarpeta = carpeta_mensajes() / str(conv.id)
            subcarpeta.mkdir(parents=True, exist_ok=True)
            nombre_disco = f"{uuid.uuid4().hex[:10]}_{nombre_original}"
            ruta_destino = subcarpeta / nombre_disco
            ruta_destino.write_bytes(bytes_archivo)

            storage_key = f"mensajes/{conv.id}/{nombre_disco}"
            adj = self.repo.crear_adjunto(
                message_id=msg.id,
                storage_key=storage_key,
                original_filename=nombre_original,
                mime_type=mime_type,
                file_size=len(bytes_archivo),
            )
            msg.attachments = [adj]
        else:
            msg.attachments = []

        # Marcar como leído para el propio remitente
        self.repo.marcar_leido(conv.id, user_id)

        # Notificar a la contraparte
        extracto = texto[:100] + ("..." if len(texto) > 100 else "")
        if rol_emisor == "empresa" and candidato_user_id:
            self.repo.crear_notificacion(
                user_id=candidato_user_id,
                tipo="new_message",
                titulo=f"Nuevo mensaje de {empresa_nombre}",
                cuerpo=f"Vacante «{vacante_titulo}»: {extracto}",
                enlace="/postulaciones",
            )
        elif rol_emisor == "candidato" and app.job_posting and app.job_posting.company_id:
            for miembro in self.repo.obtener_miembros_activos_empresa(
                app.job_posting.company_id
            ):
                if miembro.user_id != user_id:
                    self.repo.crear_notificacion(
                        user_id=miembro.user_id,
                        tipo="new_message",
                        titulo=f"Nuevo mensaje de {candidato_nombre}",
                        cuerpo=f"Postulación a «{vacante_titulo}»: {extracto}",
                        enlace="/seleccion",
                    )

        self.bitacora.registrar(
            modulo=_MODULO,
            accion="enviar_mensaje",
            usuario_id=user_id,
            ip=ip,
            detalles=f"application_id={application_id} rol={rol_emisor} adjunto={bool(bytes_archivo)}",
        )
        self.db.commit()

        return self._mapear_mensaje(
            msg,
            current_user_id=user_id,
            candidato_user_id=candidato_user_id,
            candidato_nombre=candidato_nombre,
            empresa_nombre=empresa_nombre,
        )

    def obtener_archivo_adjunto(
        self, user_id: uuid.UUID, attachment_id: uuid.UUID
    ) -> tuple[Path, str, str]:
        adjunto = self.repo.obtener_adjunto(attachment_id)
        if not adjunto or not adjunto.message or not adjunto.message.conversation:
            raise NotFoundException("El archivo adjunto solicitado no existe.")

        application_id = adjunto.message.conversation.application_id
        if not application_id:
            raise NotFoundException("Conversación no vinculada a una postulación.")

        # Verifica permisos: solo candidato o empresa de la postulación
        self._validar_acceso_postulacion(user_id, application_id)

        ruta = Path(get_settings().storage_local_path) / adjunto.storage_key
        if not ruta.exists() or not ruta.is_file():
            raise NotFoundException(
                "El archivo adjunto no se encuentra disponible en el almacenamiento del servidor."
            )

        return (
            ruta,
            adjunto.original_filename,
            adjunto.mime_type or "application/octet-stream",
        )
