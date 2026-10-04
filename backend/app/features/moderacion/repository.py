import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload

from app.features.vacantes.repository import empresa_vinculada_a
from app.models.candidato import CandidateProfile
from app.models.empresa import CompanyMember
from app.models.moderacion import ModerationReport
from app.models.vacante import JobPosting


class DenunciaRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_vacante_bloqueada(self, vacante_id: uuid.UUID) -> JobPosting | None:
        """Bloquea la fila de la vacante: dos denuncias simultáneas no cruzan el umbral a la vez."""
        return self.db.scalar(
            select(JobPosting)
            .options(joinedload(JobPosting.company))
            .where(JobPosting.id == vacante_id)
            .with_for_update(of=JobPosting)
        )

    def es_miembro_de(self, user_id: uuid.UUID, company_id: uuid.UUID) -> bool:
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

    def miembros_de(self, company_id: uuid.UUID) -> list[uuid.UUID]:
        return list(
            self.db.scalars(
                select(CompanyMember.user_id).where(
                    CompanyMember.company_id == company_id, CompanyMember.is_active.is_(True)
                )
            )
        )

    def pendiente_de(self, reporter_id: uuid.UUID, vacante_id: uuid.UUID) -> ModerationReport | None:
        return self.db.scalar(
            select(ModerationReport).where(
                ModerationReport.reporter_id == reporter_id,
                ModerationReport.job_id == vacante_id,
                ModerationReport.status == "pending",
            )
        )

    def crear(self, denuncia: ModerationReport) -> ModerationReport:
        self.db.add(denuncia)
        self.db.flush()
        return denuncia

    def _vacantes_con_pendientes(self, institution_id: uuid.UUID | None):
        stmt = (
            select(ModerationReport.job_id, func.max(ModerationReport.created_at).label("ultima"))
            .join(JobPosting, JobPosting.id == ModerationReport.job_id)
            .where(ModerationReport.status == "pending")
            .group_by(ModerationReport.job_id)
        )
        if institution_id is not None:
            stmt = stmt.where(empresa_vinculada_a(institution_id))
        return stmt

    def listar_vacantes_con_pendientes(
        self, institution_id: uuid.UUID | None, page: int, page_size: int
    ) -> tuple[list[tuple[JobPosting, datetime]], int]:
        """Vacantes con denuncias pendientes, la más recientemente denunciada primero."""
        base = self._vacantes_con_pendientes(institution_id)
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        filas = self.db.execute(
            base.order_by(func.max(ModerationReport.created_at).desc()).offset((page - 1) * page_size).limit(page_size)
        ).all()
        if not filas:
            return [], total
        vacantes = {
            v.id: v
            for v in self.db.scalars(
                select(JobPosting)
                .options(joinedload(JobPosting.company))
                .where(JobPosting.id.in_([f.job_id for f in filas]))
            )
        }
        return [(vacantes[f.job_id], f.ultima) for f in filas], total

    def vacante_en_alcance(self, vacante_id: uuid.UUID, institution_id: uuid.UUID | None) -> bool:
        stmt = select(JobPosting.id).where(JobPosting.id == vacante_id)
        if institution_id is not None:
            stmt = stmt.where(empresa_vinculada_a(institution_id))
        return self.db.scalar(stmt) is not None

    def pendientes_de_vacantes(self, vacante_ids: list[uuid.UUID]) -> list[ModerationReport]:
        return list(
            self.db.scalars(
                select(ModerationReport)
                .options(joinedload(ModerationReport.reporter))
                .where(ModerationReport.job_id.in_(vacante_ids), ModerationReport.status == "pending")
                .order_by(ModerationReport.created_at.desc())
            )
        )

    def nombres_de_egresados(self, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not user_ids:
            return {}
        filas = self.db.execute(
            select(CandidateProfile.user_id, CandidateProfile.first_name, CandidateProfile.last_name).where(
                CandidateProfile.user_id.in_(user_ids)
            )
        )
        return {f.user_id: f"{f.first_name or ''} {f.last_name or ''}".strip() for f in filas}

    def cerrar_pendientes(self, vacante_id: uuid.UUID, nuevo_estado: str, ahora: datetime) -> list[uuid.UUID]:
        """Cierra las denuncias pendientes de la vacante; devuelve quiénes las habían hecho."""
        filas = self.db.execute(
            update(ModerationReport)
            .where(ModerationReport.job_id == vacante_id, ModerationReport.status == "pending")
            .values(status=nuevo_estado, resolved_at=ahora)
            .returning(ModerationReport.reporter_id)
        )
        return [f[0] for f in filas]
