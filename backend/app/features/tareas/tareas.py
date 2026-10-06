"""Tareas automáticas diarias de la plataforma.

- respaldo_diario: copia de seguridad completa de la base (Backup automático, requisito 6).
- cierre_vacantes: cierra las vacantes publicadas cuya fecha límite ya pasó y avisa a la empresa.
- boletin_ofertas: avisa a cada egresado verificado las ofertas publicadas en las últimas 24 horas
  que coinciden con su perfil (motor de afinidad de HU-23), por la campana y por push.

Cada tarea recibe su propia sesión, hace commit y devuelve un resumen para el historial.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.tenancy import INSTITUCION_POR_DEFECTO_ID
from app.features.bitacora.service import BitacoraService
from app.features.ia.services import afinidad as motor_afinidad
from app.features.moderacion.reglas import no_oculta_por_denuncias
from app.features.notificaciones.emisor import emitir_notificacion
from app.features.respaldos.service import RespaldoService
from app.features.vacantes.repository import empresa_no_suspendida
from app.models.candidato import CandidateProfile
from app.models.empresa import CompanyMember
from app.models.institucion import CompanyInstitution
from app.models.postulacion import Application
from app.models.vacante import JobEducationPreference, JobPosting, JobSkill, JobStatus

_MODULO = "tareas"
# Afinidad mínima para avisar una oferta nueva en el boletín (la neutral, sin datos, es 50).
UMBRAL_BOLETIN = 60


@dataclass(frozen=True)
class Tarea:
    clave: str
    nombre: str
    descripcion: str
    ejecutar: Callable[[Session], str]


def _corto(texto: str, largo: int = 80) -> str:
    return texto if len(texto) <= largo else texto[: largo - 1].rstrip() + "…"


def respaldo_diario(db: Session) -> str:
    respaldo, eliminadas = RespaldoService(db).generar_automatico()
    resumen = f"Copia {respaldo.file_name}: {respaldo.tables_count} tablas y {respaldo.rows_count} filas."
    if eliminadas:
        resumen += f" Se borraron {eliminadas} copias automáticas viejas."
    return resumen


def cierre_vacantes(db: Session) -> str:
    ahora = datetime.now(timezone.utc)
    vencidas = db.scalars(
        select(JobPosting)
        .where(
            JobPosting.status == JobStatus.PUBLISHED.value,
            JobPosting.application_deadline.is_not(None),
            JobPosting.application_deadline < ahora,
        )
        .with_for_update(skip_locked=True)
    ).all()
    if not vencidas:
        return "No había vacantes vencidas."

    miembros: dict = defaultdict(list)
    filas = db.execute(
        select(CompanyMember.company_id, CompanyMember.user_id).where(
            CompanyMember.company_id.in_({v.company_id for v in vencidas}), CompanyMember.is_active.is_(True)
        )
    )
    for company_id, user_id in filas:
        miembros[company_id].append(user_id)

    for vacante in vencidas:
        vacante.status = JobStatus.CLOSED.value
        vacante.closed_at = ahora
        for user_id in miembros[vacante.company_id]:
            emitir_notificacion(
                db,
                user_id,
                "vacante_cerrada",
                f"Tu vacante cerró: {_corto(vacante.title)}",
                "Llegó a su fecha límite y dejó de recibir postulaciones. "
                "Los postulantes siguen en tu proceso de selección.",
                "/vacantes/mis-vacantes",
            )
    BitacoraService(db).registrar(
        modulo=_MODULO, accion="cerrar_vacantes_vencidas", detalles=f"cerradas={len(vencidas)}"
    )
    db.commit()
    return f"Se cerraron {len(vencidas)} vacantes vencidas y se avisó a sus empresas."


def boletin_ofertas(db: Session) -> str:
    if not motor_afinidad.ia_activa():
        return "El servicio de IA está apagado: hoy no se envió el boletín."
    ahora = datetime.now(timezone.utc)
    nuevas = (
        db.scalars(
            select(JobPosting)
            .where(
                JobPosting.status == JobStatus.PUBLISHED.value,
                JobPosting.published_at >= ahora - timedelta(hours=24),
                or_(JobPosting.application_deadline.is_(None), JobPosting.application_deadline >= ahora),
                empresa_no_suspendida(),
                no_oculta_por_denuncias(),
            )
            .options(
                joinedload(JobPosting.company),
                selectinload(JobPosting.skills).joinedload(JobSkill.skill),
                selectinload(JobPosting.education_preferences).joinedload(JobEducationPreference.field_of_study),
                selectinload(JobPosting.language_requirements),
            )
        )
        .unique()
        .all()
    )
    if not nuevas:
        return "No hubo ofertas nuevas en las últimas 24 horas."

    ids_nuevas = {v.id for v in nuevas}
    # Una oferta solo se avisa a egresados de universidades donde la empresa está habilitada.
    habilitadas = set(
        db.execute(
            select(CompanyInstitution.company_id, CompanyInstitution.institution_id).where(
                CompanyInstitution.company_id.in_({v.company_id for v in nuevas}),
                CompanyInstitution.status == "approved",
            )
        ).tuples()
    )
    postuladas = set(
        db.execute(
            select(Application.candidate_id, Application.job_id).where(Application.job_id.in_(ids_nuevas))
        ).tuples()
    )
    candidatos = db.scalars(select(CandidateProfile).where(CandidateProfile.verification_status == "verified")).all()
    perfiles = motor_afinidad.perfiles_de_candidatos(db, {c.id for c in candidatos})

    avisados = 0
    for candidato in candidatos:
        universidad = candidato.institution_id or INSTITUCION_POR_DEFECTO_ID
        coincidencias = sorted(
            (
                (motor_afinidad.evaluar(vacante, perfiles[candidato.id]).porcentaje, vacante)
                for vacante in nuevas
                if (vacante.company_id, universidad) in habilitadas and (candidato.id, vacante.id) not in postuladas
            ),
            key=lambda par: par[0],
            reverse=True,
        )
        coincidencias = [par for par in coincidencias if par[0] >= UMBRAL_BOLETIN]
        if not coincidencias:
            continue
        afinidad, mejor = coincidencias[0]
        empresa = mejor.company.trade_name or mejor.company.legal_name
        cuerpo = f"{_corto(mejor.title, 60)} en {empresa} ({afinidad}% de afinidad)"
        if len(coincidencias) > 1:
            cuerpo += f" y {len(coincidencias) - 1} más"
        titulo = "1 oferta nueva para vos" if len(coincidencias) == 1 else f"{len(coincidencias)} ofertas nuevas para vos"
        emitir_notificacion(db, candidato.user_id, "job_match", titulo, cuerpo + ".", "/recomendaciones")
        avisados += 1

    BitacoraService(db).registrar(
        modulo=_MODULO, accion="boletin_ofertas", detalles=f"ofertas={len(nuevas)} egresados_avisados={avisados}"
    )
    db.commit()
    return f"{len(nuevas)} ofertas nuevas en las últimas 24 horas; se avisó a {avisados} egresados."


TAREAS: dict[str, Tarea] = {
    t.clave: t
    for t in (
        Tarea(
            "respaldo_diario",
            "Copia de seguridad automática",
            "Genera una copia completa de la base de datos y conserva las últimas copias automáticas.",
            respaldo_diario,
        ),
        Tarea(
            "cierre_vacantes",
            "Cierre de vacantes vencidas",
            "Cierra las vacantes publicadas cuya fecha límite ya pasó y avisa a la empresa.",
            cierre_vacantes,
        ),
        Tarea(
            "boletin_ofertas",
            "Boletín diario de ofertas",
            "Avisa a cada egresado verificado las ofertas nuevas del día que coinciden con su perfil.",
            boletin_ofertas,
        ),
    )
}
