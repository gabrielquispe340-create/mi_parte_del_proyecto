from datetime import datetime

from pydantic import BaseModel

from app.features.vacantes.schema import CriterioAfinidadResponse, VacanteResumenResponse


class VacanteRecomendadaResponse(BaseModel):
    vacante: VacanteResumenResponse
    afinidad: int
    # Vacío cuando la vacante no detalla requisitos comparables (afinidad neutral).
    criterios: list[CriterioAfinidadResponse]
    ya_postulado: bool = False


class RecomendacionesResponse(BaseModel):
    calculado_en: datetime
    total: int
    # Secciones vacías del perfil que bajan la afinidad.
    perfil_faltantes: list[str]
    items: list[VacanteRecomendadaResponse]
