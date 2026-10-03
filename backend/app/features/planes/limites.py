"""Plan vigente de cada universidad y control de sus límites.

Regla: con un plan pago cuyo pago está pendiente o vencido rigen los límites del Básico.
Los límites solo frenan altas nuevas; lo que ya existe no se borra al bajar de plan.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.exceptions import ConflictException
from app.core.tenancy import condicion_institucion
from app.models.candidato import CandidateProfile
from app.models.institucion import Institution, SaasPlan
from app.models.usuario import AppUser, Role, UserRole

PLAN_GRATUITO = "basico"
# Bolivia no tiene horario de verano: UTC-4 todo el año.
_ZONA_BOLIVIA = timezone(timedelta(hours=-4))


def hoy_bolivia() -> date:
    return datetime.now(_ZONA_BOLIVIA).date()


@dataclass
class PlanDeUniversidad:
    contratado: SaasPlan
    vigente: SaasPlan  # el que fija los límites
    estado_pago: str  # gratis | al_dia | pendiente | vencido


def resolver_plan(institucion: Institution, planes: dict[str, SaasPlan]) -> PlanDeUniversidad:
    contratado = planes.get(institucion.plan_code or PLAN_GRATUITO) or planes[PLAN_GRATUITO]
    if not contratado.es_pago:
        estado = "gratis"
    elif institucion.plan_paid_until is None:
        estado = "pendiente"
    elif institucion.plan_paid_until < hoy_bolivia():
        estado = "vencido"
    else:
        estado = "al_dia"
    vigente = contratado if estado in ("gratis", "al_dia") else planes[PLAN_GRATUITO]
    return PlanDeUniversidad(contratado, vigente, estado)


def planes_por_codigo(db: Session) -> dict[str, SaasPlan]:
    return {plan.code: plan for plan in db.scalars(select(SaasPlan))}


def contar_egresados(db: Session, institution_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count(CandidateProfile.id)).where(
            condicion_institucion(CandidateProfile.institution_id, institution_id)
        )
    ) or 0


def contar_moderadores(db: Session, institution_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count(AppUser.id))
        .join(UserRole, UserRole.user_id == AppUser.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.name == "moderator", AppUser.institution_id == institution_id, AppUser.deleted_at.is_(None))
    ) or 0


def _plan_vigente(db: Session, institution_id: uuid.UUID) -> tuple[Institution, SaasPlan] | None:
    institucion = db.get(Institution, institution_id)
    if institucion is None:
        return None
    return institucion, resolver_plan(institucion, planes_por_codigo(db)).vigente


def verificar_cupo_egresados(db: Session, institution_id: uuid.UUID) -> None:
    datos = _plan_vigente(db, institution_id)
    if datos is None:
        return
    institucion, plan = datos
    if plan.max_graduates is not None and contar_egresados(db, institution_id) >= plan.max_graduates:
        raise ConflictException(
            f"{institucion.name} alcanzó el límite de {plan.max_graduates} egresados de su plan. "
            "Avisale a la administración de tu universidad."
        )


def verificar_cupo_moderadores(db: Session, institution_id: uuid.UUID) -> None:
    datos = _plan_vigente(db, institution_id)
    if datos is None:
        return
    _, plan = datos
    if plan.max_moderators is not None and contar_moderadores(db, institution_id) >= plan.max_moderators:
        raise ConflictException(
            f"El plan {plan.name} permite hasta {plan.max_moderators} moderador(es). "
            "Para agregar más, la universidad tiene que subir de plan."
        )
