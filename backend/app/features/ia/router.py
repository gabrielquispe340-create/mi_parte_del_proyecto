"""Módulos 5.1.11 a 5.1.14 — IA: recomendación (HU-23), asistente generativo, chatbot y
análisis predictivo. Por ahora está implementada la recomendación de vacantes."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.ia.schema import RecomendacionesResponse, VacanteRecomendadaResponse
from app.features.ia.services.afinidad import ia_activa
from app.features.ia.services.recomendacion_service import RecomendacionService
from app.security.dependencies import CurrentUser, require_roles

router = APIRouter(prefix="/ia", tags=["inteligencia-artificial"])

_solo_egresado = require_roles("candidate")


@router.get("/_status")
def estado_modulo() -> dict:
    return {"modulo": "inteligencia_artificial", "recomendaciones": "activo" if ia_activa() else "apagado"}


@router.get("/recomendaciones", response_model=RecomendacionesResponse)
def vacantes_recomendadas(current_user: CurrentUser = Depends(_solo_egresado), db: Session = Depends(get_db)):
    """HU-23: vacantes vigentes ordenadas por afinidad con el perfil del egresado."""
    return RecomendacionService(db).vacantes_recomendadas(current_user.id_usuario)


@router.get("/recomendaciones/{vacante_id}", response_model=VacanteRecomendadaResponse)
def detalle_recomendacion(
    vacante_id: uuid.UUID, current_user: CurrentUser = Depends(_solo_egresado), db: Session = Depends(get_db)
):
    """HU-23 (CP02): criterios que el egresado cumple y que le faltan para una vacante."""
    return RecomendacionService(db).detalle(current_user.id_usuario, vacante_id)
