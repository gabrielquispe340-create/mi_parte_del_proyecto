import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class EtapaItem(BaseModel):
    id: uuid.UUID | None = None
    stage_number: int = Field(..., ge=1)
    name: str = Field(..., min_length=2, max_length=100)
    description: str | None = None
    is_terminal: bool = False


class EtapaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_posting_id: uuid.UUID
    stage_number: int
    name: str
    description: str | None = None
    is_terminal: bool = False
    total_candidatos: int = 0


class ConfigurarEtapasRequest(BaseModel):
    etapas: list[EtapaItem] = Field(..., min_length=1)


class VacanteResumenSeleccion(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    titulo: str
    seniority: str | None = None
    modalidad: str
    modalidad_label: str
    tipo_empleo: str
    tipo_empleo_label: str
    total_postulantes: int = 0
    total_activos: int = 0
    total_descartados: int = 0
    total_contratados: int = 0


class CandidatoPipelineItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    postulacion_id: uuid.UUID
    candidato_id: uuid.UUID
    candidato_nombre: str
    candidato_titular: str | None = None
    candidato_carrera: str | None = None
    candidato_email: str | None = None
    candidato_telefono: str | None = None
    candidato_ciudad: str | None = None
    candidato_universidad: str | None = None
    candidato_carrera_id: uuid.UUID | None = None
    candidato_afinidad: int | None = None
    estado: str
    estado_label: str
    estado_color: str
    etapa_actual_id: uuid.UUID | None = None
    etapa_actual_nombre: str | None = None
    etapa_actual_numero: int | None = None
    fecha_postulacion: datetime
    fecha_ultimo_cambio: datetime
    total_notas: int = 0
    puede_avanzar: bool = True
    puede_descartar: bool = True


class PipelineVacanteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vacante: VacanteResumenSeleccion
    etapas: list[EtapaResponse]
    candidatos: list[CandidatoPipelineItem]


class AvanzarEtapaRequest(BaseModel):
    stage_id: uuid.UUID
    observacion: str | None = None


class DescartarCandidatoRequest(BaseModel):
    motivo: str | None = None


class NotaInternaRequest(BaseModel):
    content: str = Field(..., min_length=1)


class NotaInternaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    postulacion_id: uuid.UUID
    autor_nombre: str
    autor_cargo: str | None = None
    content: str
    created_at: datetime


from app.features.perfil.schema import (
    FormacionResponse,
    ExperienciaResponse,
    IdiomaResponse,
    HabilidadResponse,
)

class CompararCandidatosRequest(BaseModel):
    postulaciones: list[uuid.UUID] = Field(..., min_length=2, max_length=3, description="IDs de las postulaciones a comparar")

class CandidatoComparacionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    postulacion_id: uuid.UUID
    candidato_id: uuid.UUID
    candidato_nombre: str
    afinidad: int | None = None
    formacion: list[FormacionResponse] = Field(default_factory=list)
    experiencia: list[ExperienciaResponse] = Field(default_factory=list)
    habilidades: list[HabilidadResponse] = Field(default_factory=list)
    idiomas: list[IdiomaResponse] = Field(default_factory=list)
