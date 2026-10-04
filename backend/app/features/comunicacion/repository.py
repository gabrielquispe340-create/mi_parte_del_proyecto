import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.models.candidato import CandidateEducation, CandidateProfile
from app.models.comunicacion import (
    Conversation,
    ConversationMember,
    Message,
    MessageAttachment,
)
from app.models.empresa import CompanyMember
from app.models.notificacion import Notification
from app.models.postulacion import Application
from app.models.vacante import JobPosting


class ComunicacionRepository:
    def __init__(self, db: Session):
        self.db = db

    def obtener_postulacion(self, application_id: uuid.UUID) -> Optional[Application]:
        stmt = (
            select(Application)
            .options(
                joinedload(Application.job_posting).joinedload(JobPosting.company),
                joinedload(Application.candidate).joinedload(CandidateProfile.user),
                joinedload(Application.candidate)
                .joinedload(CandidateProfile.educations)
                .joinedload(CandidateEducation.field_of_study),
                joinedload(Application.current_stage),
            )
            .where(Application.id == application_id)
        )
        return self.db.scalar(stmt)

    def obtener_miembro_empresa(
        self, user_id: uuid.UUID, company_id: Optional[uuid.UUID] = None
    ) -> Optional[CompanyMember]:
        stmt = (
            select(CompanyMember)
            .options(joinedload(CompanyMember.company))
            .where(CompanyMember.user_id == user_id, CompanyMember.is_active.is_(True))
        )
        if company_id is not None:
            stmt = stmt.where(CompanyMember.company_id == company_id)
        return self.db.scalar(stmt)

    def obtener_miembros_activos_empresa(self, company_id: uuid.UUID) -> list[CompanyMember]:
        stmt = select(CompanyMember).where(
            CompanyMember.company_id == company_id,
            CompanyMember.is_active.is_(True),
        )
        return list(self.db.scalars(stmt).all())

    def obtener_perfil_candidato(self, user_id: uuid.UUID) -> Optional[CandidateProfile]:
        stmt = (
            select(CandidateProfile)
            .options(joinedload(CandidateProfile.user))
            .where(CandidateProfile.user_id == user_id)
        )
        return self.db.scalar(stmt)

    def listar_conversaciones_de_usuario(self, user_id: uuid.UUID, limite: int = 100) -> list[Conversation]:
        """Hilos de postulaciones donde el usuario es el candidato o miembro activo de la empresa."""
        empresas_del_usuario = select(CompanyMember.company_id).where(
            CompanyMember.user_id == user_id, CompanyMember.is_active.is_(True)
        )
        stmt = (
            select(Conversation)
            .join(Application, Conversation.application_id == Application.id)
            .join(JobPosting, Application.job_id == JobPosting.id)
            .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)
            .options(
                contains_eager(Conversation.application)
                .contains_eager(Application.job_posting)
                .joinedload(JobPosting.company),
                contains_eager(Conversation.application).contains_eager(Application.candidate),
            )
            .where(or_(CandidateProfile.user_id == user_id, JobPosting.company_id.in_(empresas_del_usuario)))
            .order_by(Conversation.last_message_at.desc())
            .limit(limite)
        )
        return list(self.db.scalars(stmt).all())

    def ultimos_mensajes(self, conversation_ids: list[uuid.UUID]) -> dict[uuid.UUID, Message]:
        """Último mensaje visible de cada hilo, en una sola consulta (DISTINCT ON)."""
        if not conversation_ids:
            return {}
        stmt = (
            select(Message)
            .where(Message.conversation_id.in_(conversation_ids), Message.deleted_at.is_(None))
            .order_by(Message.conversation_id, Message.created_at.desc())
            .distinct(Message.conversation_id)
        )
        return {m.conversation_id: m for m in self.db.scalars(stmt).all()}

    def contar_no_leidos(self, conversation_ids: list[uuid.UUID], user_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """Mensajes de la otra parte posteriores a la última lectura del usuario, por hilo."""
        if not conversation_ids:
            return {}
        stmt = (
            select(Message.conversation_id, func.count(Message.id))
            .outerjoin(
                ConversationMember,
                and_(
                    ConversationMember.conversation_id == Message.conversation_id,
                    ConversationMember.user_id == user_id,
                ),
            )
            .where(
                Message.conversation_id.in_(conversation_ids),
                Message.deleted_at.is_(None),
                Message.sender_id != user_id,
                or_(ConversationMember.last_read_at.is_(None), Message.created_at > ConversationMember.last_read_at),
            )
            .group_by(Message.conversation_id)
        )
        return {conv_id: total for conv_id, total in self.db.execute(stmt).all()}

    def obtener_conversacion_por_postulacion(
        self, application_id: uuid.UUID
    ) -> Optional[Conversation]:
        stmt = (
            select(Conversation)
            .options(
                joinedload(Conversation.members),
                joinedload(Conversation.messages).joinedload(Message.sender),
                joinedload(Conversation.messages).joinedload(Message.attachments),
            )
            .where(Conversation.application_id == application_id)
        )
        return self.db.scalar(stmt)

    def crear_conversacion_postulacion(
        self, application_id: uuid.UUID, user_ids: list[uuid.UUID]
    ) -> Conversation:
        ahora = datetime.now(timezone.utc)
        # Respeta el CHECK ck_conv_context de Supabase:
        # cuando application_id IS NOT NULL, candidate_id y company_id deben ser NULL.
        conv = Conversation(
            application_id=application_id,
            candidate_id=None,
            company_id=None,
            last_message_at=ahora,
            created_at=ahora,
        )
        self.db.add(conv)
        self.db.flush()

        vistos: set[uuid.UUID] = set()
        for uid in user_ids:
            if uid and uid not in vistos:
                vistos.add(uid)
                self.db.add(
                    ConversationMember(
                        conversation_id=conv.id,
                        user_id=uid,
                        last_read_at=None,
                        joined_at=ahora,
                    )
                )
        self.db.flush()
        return conv

    def asegurar_miembro(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> ConversationMember:
        stmt = select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
        )
        miembro = self.db.scalar(stmt)
        if not miembro:
            miembro = ConversationMember(
                conversation_id=conversation_id,
                user_id=user_id,
                last_read_at=None,
                joined_at=datetime.now(timezone.utc),
            )
            self.db.add(miembro)
            self.db.flush()
        return miembro

    def marcar_leido(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> None:
        miembro = self.asegurar_miembro(conversation_id, user_id)
        miembro.last_read_at = datetime.now(timezone.utc)
        self.db.flush()

    def crear_mensaje(
        self,
        conversation: Conversation,
        sender_id: uuid.UUID,
        content: str,
    ) -> Message:
        ahora = datetime.now(timezone.utc)
        msg = Message(
            conversation_id=conversation.id,
            sender_id=sender_id,
            content=content,
            created_at=ahora,
        )
        self.db.add(msg)
        conversation.last_message_at = ahora
        self.db.flush()
        return msg

    def crear_adjunto(
        self,
        message_id: uuid.UUID,
        storage_key: str,
        original_filename: str,
        mime_type: Optional[str],
        file_size: int,
    ) -> MessageAttachment:
        adjunto = MessageAttachment(
            message_id=message_id,
            storage_key=storage_key,
            original_filename=original_filename[:255],
            mime_type=(mime_type or "application/octet-stream")[:100],
            file_size=file_size,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(adjunto)
        self.db.flush()
        return adjunto

    def obtener_adjunto(self, attachment_id: uuid.UUID) -> Optional[MessageAttachment]:
        stmt = (
            select(MessageAttachment)
            .options(
                joinedload(MessageAttachment.message)
                .joinedload(Message.conversation)
                .joinedload(Conversation.application)
                .joinedload(Application.job_posting)
                .joinedload(JobPosting.company),
                joinedload(MessageAttachment.message)
                .joinedload(Message.conversation)
                .joinedload(Conversation.application)
                .joinedload(Application.candidate),
            )
            .where(MessageAttachment.id == attachment_id)
        )
        return self.db.scalar(stmt)

    def crear_notificacion(
        self,
        user_id: uuid.UUID,
        tipo: str,
        titulo: str,
        cuerpo: str,
        enlace: str | None = None,
    ) -> Notification:
        notif = Notification(
            user_id=user_id,
            notification_type=tipo,
            title=titulo,
            body=cuerpo,
            link=enlace,
        )
        self.db.add(notif)
        return notif
