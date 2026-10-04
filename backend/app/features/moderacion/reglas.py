"""Reglas de la HU-22: cuándo una denuncia cuenta y cuándo una vacante queda oculta.

Una vacante se oculta sola mientras tenga UMBRAL_OCULTAR denuncias pendientes con
fundamento; no hace falta guardar un estado aparte. Al resolverlas el administrador
(mantener, suspender o eliminar) dejan de estar pendientes y la condición se recalcula.

Una denuncia tiene fundamento si cuenta qué pasó (al menos MINIMO_FUNDAMENTO
caracteres). Las que solo marcan un motivo se registran y el administrador las ve,
pero no alcanzan para ocultar la oferta por sí solas.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.moderacion import ModerationReport
from app.models.vacante import JobPosting

UMBRAL_OCULTAR = 3
MINIMO_FUNDAMENTO = 20


def tiene_fundamento(descripcion: str | None) -> bool:
    return len((descripcion or "").strip()) >= MINIMO_FUNDAMENTO


def _cuenta_para_umbral():
    return (
        ModerationReport.status == "pending",
        func.length(func.btrim(func.coalesce(ModerationReport.description, ""))) >= MINIMO_FUNDAMENTO,
    )


def no_oculta_por_denuncias():
    """Condición para consultas sobre JobPosting: la vacante no está oculta por denuncias."""
    que_cuentan = (
        select(func.count(ModerationReport.id))
        .where(ModerationReport.job_id == JobPosting.id, *_cuenta_para_umbral())
        .correlate(JobPosting)
        .scalar_subquery()
    )
    return que_cuentan < UMBRAL_OCULTAR


def denuncias_que_cuentan(db: Session, vacante_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count(ModerationReport.id)).where(ModerationReport.job_id == vacante_id, *_cuenta_para_umbral())
    ) or 0


def esta_oculta(db: Session, vacante_id: uuid.UUID) -> bool:
    return denuncias_que_cuentan(db, vacante_id) >= UMBRAL_OCULTAR


def vacantes_ocultas(db: Session, vacante_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """De las vacantes dadas, las que están ocultas por denuncias (una sola consulta)."""
    if not vacante_ids:
        return set()
    filas = db.execute(
        select(ModerationReport.job_id)
        .where(ModerationReport.job_id.in_(vacante_ids), *_cuenta_para_umbral())
        .group_by(ModerationReport.job_id)
        .having(func.count(ModerationReport.id) >= UMBRAL_OCULTAR)
    )
    return {fila[0] for fila in filas}
