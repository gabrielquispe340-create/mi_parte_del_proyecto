import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserGroup(Base):
    """Grupo de usuarios del personal de una universidad (requisito general 2).

    Los permisos del grupo son códigos del catálogo de componentes de la interfaz
    (app/security/permisos.py): menús, formularios, botones y etiquetas.
    """

    __tablename__ = "user_group"
    __table_args__ = (UniqueConstraint("institution_id", "name", name="uq_user_group_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("educational_institution.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    miembros: Mapped[list["UserGroupMember"]] = relationship(cascade="all, delete-orphan")
    permisos: Mapped[list["UserGroupPermission"]] = relationship(cascade="all, delete-orphan")


class UserGroupMember(Base):
    __tablename__ = "user_group_member"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_group.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserGroupPermission(Base):
    __tablename__ = "user_group_permission"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_group.id", ondelete="CASCADE"), primary_key=True
    )
    permission_code: Mapped[str] = mapped_column(String(80), primary_key=True)
