import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

CategoriaDenuncia = Literal["fraud", "inappropriate", "spam", "fake_information", "discrimination", "other"]
DecisionDenuncia = Literal["mantener", "suspender", "eliminar"]


class DenunciaCreateRequest(BaseModel):
    categoria: CategoriaDenuncia
    descripcion: str | None = Field(default=None, max_length=1000)


class DenunciaCreadaResponse(BaseModel):
    id: uuid.UUID
    cuenta_para_umbral: bool
    mensaje: str


class MiDenunciaResponse(BaseModel):
    denunciada: bool
    fecha: datetime | None = None


class DenunciaItem(BaseModel):
    id: uuid.UUID
    categoria: str
    descripcion: str | None
    cuenta_para_umbral: bool
    denunciante_nombre: str
    denunciante_correo: str
    created_at: datetime


class VacanteDenunciadaItem(BaseModel):
    vacante_id: uuid.UUID
    titulo: str
    ciudad: str | None
    estado_vacante: str
    empresa_id: uuid.UUID
    empresa_nombre: str
    oculta: bool
    denuncias_que_cuentan: int
    ultima_denuncia_at: datetime
    denuncias: list[DenunciaItem]


class DenunciasPendientesResponse(BaseModel):
    items: list[VacanteDenunciadaItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    umbral: int


class ResolucionDenunciaRequest(BaseModel):
    decision: DecisionDenuncia
    nota: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _nota_si_se_retira(self) -> "ResolucionDenunciaRequest":
        # La empresa recibe la nota como motivo: suspender o eliminar sin explicar no sirve.
        if self.decision != "mantener" and len((self.nota or "").strip()) < 5:
            raise ValueError("Indicá el motivo para la empresa al suspender o eliminar la oferta.")
        return self


class ResolucionDenunciaResponse(BaseModel):
    vacante_id: uuid.UUID
    decision: DecisionDenuncia
    estado_vacante: str
    denuncias_cerradas: int
