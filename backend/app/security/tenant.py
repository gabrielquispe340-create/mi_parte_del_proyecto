"""Resolución del tenant (universidad) del usuario autenticado.

Se consulta siempre la base de datos en vez de confiar en el claim del token, para
que un cambio de universidad o de rol surta efecto sin esperar a que expire el JWT.
"""

import uuid

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.exceptions import ForbiddenException
from app.core.database import get_db
from app.core.tenancy import INSTITUCION_POR_DEFECTO_ID, condicion_institucion
from app.models.candidato import CandidateProfile
from app.models.institucion import CompanyInstitution
from app.models.usuario import AppUser
from app.security.dependencies import CurrentUser, require_roles

_ROLES_STAFF = {"platform_admin", "moderator"}


def institucion_de_candidato(db: Session, usuario_id: uuid.UUID) -> uuid.UUID | None:
    """Universidad del egresado; None si el usuario no tiene perfil de candidato."""
    perfil = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == usuario_id))
    if perfil is None:
        return None
    return perfil.institution_id or INSTITUCION_POR_DEFECTO_ID


def alcance_staff(db: Session, current_user: CurrentUser) -> uuid.UUID | None:
    """Universidad sobre la que actúa un admin/moderador. None = superadmin global.

    Solo un platform_admin sin universidad asignada es global; un moderador sin
    universidad cae en la institución por defecto para no quedar con acceso total.
    """
    usuario = db.get(AppUser, current_user.id_usuario)
    if usuario is not None and usuario.institution_id is not None:
        return usuario.institution_id
    if "platform_admin" in current_user.roles:
        return None
    return INSTITUCION_POR_DEFECTO_ID


def institucion_de_usuario(db: Session, current_user: CurrentUser) -> uuid.UUID | None:
    """Universidad asociada a cualquier usuario (staff o egresado); None si no aplica."""
    if _ROLES_STAFF & set(current_user.roles):
        return alcance_staff(db, current_user)
    return institucion_de_candidato(db, current_user.id_usuario)


def usuarios_de_institucion(institution_id: uuid.UUID):
    """Subconsulta con los ids del staff y los egresados de una universidad.

    Las cuentas de empresa no pertenecen a ningún tenant (las empresas son globales).
    """
    egresados = select(CandidateProfile.user_id).where(
        condicion_institucion(CandidateProfile.institution_id, institution_id)
    )
    staff = select(AppUser.id).where(AppUser.institution_id == institution_id)
    return egresados.union(staff)


def empresa_habilitada_en(db: Session, company_id: uuid.UUID, institution_id: uuid.UUID) -> bool:
    estado = db.scalar(
        select(CompanyInstitution.status).where(
            CompanyInstitution.company_id == company_id,
            CompanyInstitution.institution_id == institution_id,
        )
    )
    return estado == "approved"


class AlcanceStaff:
    """Usuario staff autenticado junto con la universidad sobre la que opera."""

    def __init__(self, usuario: CurrentUser, institution_id: uuid.UUID | None) -> None:
        self.usuario = usuario
        self.institution_id = institution_id

    @property
    def es_global(self) -> bool:
        return self.institution_id is None


def get_alcance_staff(
    current_user: CurrentUser = Depends(require_roles("platform_admin", "moderator")),
    db: Session = Depends(get_db),
) -> AlcanceStaff:
    return AlcanceStaff(current_user, alcance_staff(db, current_user))


def get_superadmin(alcance: AlcanceStaff = Depends(get_alcance_staff)) -> AlcanceStaff:
    """Solo el superadmin global del SaaS (platform_admin sin universidad)."""
    if not alcance.es_global:
        raise ForbiddenException("Solo el superadministrador de la plataforma puede hacer esto.")
    return alcance
