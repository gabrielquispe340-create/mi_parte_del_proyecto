"""Recomendación de vacantes al egresado (HU-23, módulo 5.1.11).

Puntúa con el motor de afinidad todas las vacantes vigentes que el egresado puede ver
(empresas habilitadas en su universidad) y las ordena de mayor a menor afinidad. Se
excluyen aquellas a las que ya está postulado, salvo que haya retirado la postulación.

Si el servicio de IA está apagado (IA_RECOMENDACIONES_ACTIVAS=false) o falla, responde
503 con un mensaje claro y el resto de la plataforma sigue funcionando (CP04).
"""

import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TypeVar

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.common.exceptions import AppException, ResourceNotFoundException, ServiceUnavailableException
from app.core.tenancy import INSTITUCION_POR_DEFECTO_ID
from app.features.ia.schema import RecomendacionesResponse, VacanteRecomendadaResponse
from app.features.ia.services import afinidad as motor_afinidad
from app.features.vacantes.repository import empresa_vinculada_a
from app.features.vacantes.schema import CriterioAfinidadResponse
from app.features.vacantes.service import VacanteService
from app.models.candidato import CandidateProfile
from app.models.empresa import Company
from app.models.postulacion import Application
from app.models.vacante import JobEducationPreference, JobPosting, JobSkill, JobStatus

logger = logging.getLogger(__name__)

MENSAJE_NO_DISPONIBLE = (
    "Las recomendaciones no están disponibles en este momento. "
    "Podés seguir buscando vacantes y postulándote con normalidad."
)
_MAX_RECOMENDACIONES = 100

T = TypeVar("T")


class RecomendacionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def vacantes_recomendadas(self, usuario_id: uuid.UUID) -> RecomendacionesResponse:
        def calcular() -> RecomendacionesResponse:
            candidato, perfil = self._perfil(usuario_id)
            stmt = self._vacantes_visibles(candidato).where(JobPosting.id.not_in(self._postuladas(candidato)))
            vacantes = self.db.scalars(stmt).unique()
            items = [self._recomendada(vacante, perfil) for vacante in vacantes]
            items.sort(
                key=lambda r: (r.afinidad, r.vacante.published_at or datetime.min.replace(tzinfo=timezone.utc)),
                reverse=True,
            )
            return RecomendacionesResponse(
                calculado_en=datetime.now(timezone.utc),
                total=len(items),
                perfil_faltantes=perfil.faltantes(),
                items=items[:_MAX_RECOMENDACIONES],
            )

        return self._con_ia(calcular)

    def detalle(self, usuario_id: uuid.UUID, vacante_id: uuid.UUID) -> VacanteRecomendadaResponse:
        """Por qué se recomienda (o no) una vacante: criterios que cumple y que le faltan."""

        def calcular() -> VacanteRecomendadaResponse:
            candidato, perfil = self._perfil(usuario_id)
            vacante = self.db.scalar(self._vacantes_visibles(candidato).where(JobPosting.id == vacante_id))
            if vacante is None:
                raise ResourceNotFoundException("La vacante no existe o ya no está disponible para tu universidad.")
            postulado = self.db.scalar(self._postuladas(candidato).where(Application.job_id == vacante_id)) is not None
            return self._recomendada(vacante, perfil, ya_postulado=postulado)

        return self._con_ia(calcular)

    # ─── Auxiliares ─────────────────────────────────────────────────────────

    @staticmethod
    def _con_ia(calcular: Callable[[], T]) -> T:
        if not motor_afinidad.ia_activa():
            raise ServiceUnavailableException(MENSAJE_NO_DISPONIBLE)
        try:
            return calcular()
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Falló el servicio de recomendaciones")
            raise ServiceUnavailableException(MENSAJE_NO_DISPONIBLE) from exc

    def _perfil(self, usuario_id: uuid.UUID) -> tuple[CandidateProfile, motor_afinidad.PerfilAfinidad]:
        candidato = self.db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == usuario_id))
        if candidato is None:
            raise ResourceNotFoundException("Completá tu perfil de egresado para recibir recomendaciones.")
        return candidato, motor_afinidad.perfiles_de_candidatos(self.db, {candidato.id})[candidato.id]

    @staticmethod
    def _vacantes_visibles(candidato: CandidateProfile):
        """Vacantes publicadas y vigentes de empresas habilitadas en la universidad del egresado."""
        institucion = candidato.institution_id or INSTITUCION_POR_DEFECTO_ID
        return (
            select(JobPosting)
            .where(
                JobPosting.status == JobStatus.PUBLISHED.value,
                or_(JobPosting.application_deadline.is_(None), JobPosting.application_deadline >= func.now()),
                empresa_vinculada_a(institucion),
            )
            .options(
                joinedload(JobPosting.company).joinedload(Company.sector),
                joinedload(JobPosting.category),
                selectinload(JobPosting.skills).joinedload(JobSkill.skill),
                selectinload(JobPosting.education_preferences).joinedload(JobEducationPreference.field_of_study),
                selectinload(JobPosting.language_requirements),
            )
        )

    @staticmethod
    def _postuladas(candidato: CandidateProfile):
        """Vacantes con una postulación vigente del egresado (las retiradas no cuentan)."""
        return select(Application.job_id).where(
            Application.candidate_id == candidato.id, Application.current_status != "withdrawn"
        )

    def _recomendada(
        self, vacante: JobPosting, perfil: motor_afinidad.PerfilAfinidad, ya_postulado: bool = False
    ) -> VacanteRecomendadaResponse:
        afinidad = motor_afinidad.evaluar(vacante, perfil)
        return VacanteRecomendadaResponse(
            vacante=VacanteService(self.db)._mapear_a_resumen_busqueda(vacante, afinidad.porcentaje),
            afinidad=afinidad.porcentaje,
            criterios=[CriterioAfinidadResponse(**vars(c)) for c in afinidad.criterios],
            ya_postulado=ya_postulado,
        )
