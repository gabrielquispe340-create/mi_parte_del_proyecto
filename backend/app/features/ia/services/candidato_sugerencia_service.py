import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.common.exceptions import BusinessException, ResourceNotFoundException
from app.features.ia.schema import (
    CandidatoSugeridoDTO,
    CriterioSugerenciaDTO,
    SugerenciasCandidatosResponse,
)
from app.features.ia.services.afinidad import (
    calcular_afinidad,
    ia_activa,
    perfiles_de_candidatos,
)
from app.models.candidato import CandidateProfile
from app.models.empresa import CompanyMember
from app.models.postulacion import Application
from app.models.vacante import JobPosting


class CandidatoSugerenciaService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _es_miembro_de(self, user_id: uuid.UUID, company_id: uuid.UUID) -> bool:
        return (
            self.db.scalar(
                select(CompanyMember.user_id).where(
                    CompanyMember.user_id == user_id,
                    CompanyMember.company_id == company_id,
                    CompanyMember.is_active.is_(True),
                )
            )
            is not None
        )

    def sugerir_candidatos_para_vacante(
        self,
        vacante_id: uuid.UUID,
        user_id: uuid.UUID,
        umbral_minimo: int = 0,
        solo_postulados: bool = True,
    ) -> SugerenciasCandidatosResponse:
        """HU-24: Genera ranking de candidatos para una vacante según afinidad calculada por IA."""
        # 1. Cargar la vacante con todos sus requisitos
        stmt_vac = (
            select(JobPosting)
            .options(
                joinedload(JobPosting.company),
                selectinload(JobPosting.education_preferences),
                selectinload(JobPosting.skills),
                selectinload(JobPosting.language_requirements),
            )
            .where(JobPosting.id == vacante_id)
        )
        vacante = self.db.scalar(stmt_vac)
        # Solo la empresa dueña de la vacante ve a sus postulantes; para cualquier
        # otra se responde lo mismo que si no existiera.
        if not vacante or not self._es_miembro_de(user_id, vacante.company_id):
            raise ResourceNotFoundException("La vacante solicitada no existe.")

        # 2. Cargar postulaciones o candidatos del pool
        stmt_apps = (
            select(Application)
            .options(
                joinedload(Application.candidate).joinedload(CandidateProfile.user),
                joinedload(Application.candidate).selectinload(CandidateProfile.educations),
            )
            .where(Application.job_id == vacante_id)
        )
        postulaciones = list(self.db.scalars(stmt_apps).all())

        candidate_ids = {app.candidate_id for app in postulaciones if app.candidate_id}
        app_by_candidate: dict[uuid.UUID, Application] = {
            app.candidate_id: app for app in postulaciones if app.candidate_id
        }

        # 3. Cargar perfiles estructurados para el cálculo de afinidad
        perfiles = perfiles_de_candidatos(self.db, candidate_ids)

        candidatos_dto: list[CandidatoSugeridoDTO] = []

        for app in postulaciones:
            cand = app.candidate
            if not cand:
                continue

            perfil = perfiles.get(cand.id)
            if perfil and ia_activa():
                afinidad = calcular_afinidad(perfil, vacante)
                score = afinidad.porcentaje
                criterios_raw = afinidad.criterios
            else:
                # Fallback neutral o cuando IA está desactivada (CP04)
                score = 50
                criterios_raw = []

            # Filtrar por umbral mínimo (CP02)
            if score < umbral_minimo:
                continue

            # Nivel de coincidencia legible
            if score >= 85:
                nivel = "Excelente coincidencia"
            elif score >= 70:
                nivel = "Alta coincidencia"
            elif score >= 50:
                nivel = "Coincidencia media"
            else:
                nivel = "Coincidencia baja"

            # Razones explicativas (RNF-20 Explicabilidad)
            razones: list[str] = []
            criterios_dto: list[CriterioSugerenciaDTO] = []
            for c in criterios_raw:
                criterios_dto.append(
                    CriterioSugerenciaDTO(
                        clave=c.clave,
                        nombre=c.nombre,
                        peso=c.peso,
                        cumplimiento=c.cumplimiento,
                        estado=c.estado,
                        detalle=c.detalle,
                        coincidencias=c.coincidencias,
                        faltantes=c.faltantes,
                    )
                )
                if c.coincidencias:
                    razones.append(f"{c.nombre}: coincide en {', '.join(c.coincidencias)}")
                elif c.estado == "cumple":
                    razones.append(f"{c.nombre}: cumple con los requisitos del puesto")

            if not razones:
                razones.append("Perfil general registrado y postulado a la vacante")

            # Obtener carrera principal
            carrera_nombre = None
            if cand.educations:
                carrera_nombre = (
                    cand.educations[0].program_name
                    or (cand.educations[0].field_of_study.name if cand.educations[0].field_of_study else None)
                )

            candidatos_dto.append(
                CandidatoSugeridoDTO(
                    candidate_id=cand.id,
                    user_id=cand.user_id,
                    application_id=app.id,
                    first_name=cand.first_name,
                    last_name=cand.last_name,
                    professional_headline=cand.professional_headline,
                    carrera_principal=carrera_nombre,
                    city=cand.city,
                    afinidad_porcentaje=score,
                    nivel_coincidencia=nivel,
                    razones_principales=razones,
                    criterios=criterios_dto,
                    current_status=app.current_status,
                    applied_at=app.applied_at,
                )
            )

        # Ordenar por afinidad descendente (ranking inteligente)
        candidatos_dto.sort(key=lambda x: x.afinidad_porcentaje, reverse=True)

        return SugerenciasCandidatosResponse(
            vacante_id=vacante.id,
            vacante_titulo=vacante.title,
            calculado_en=datetime.now(timezone.utc),
            umbral_minimo=umbral_minimo,
            total_postulantes=len(postulaciones),
            total_coincidentes=len(candidatos_dto),
            items=candidatos_dto,
        )

