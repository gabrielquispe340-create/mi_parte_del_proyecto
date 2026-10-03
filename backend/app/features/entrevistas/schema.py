import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class EntrevistaBase(BaseModel):
    scheduled_start: datetime
    scheduled_end: Optional[datetime] = None
    modality: str = Field(..., pattern="^(onsite|virtual)$")
    location: Optional[str] = None
    meeting_url: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validar_modalidad_y_fechas(self) -> "EntrevistaBase":
        if self.modality == "onsite" and not (self.location and self.location.strip()):
            raise ValueError("La ubicación es obligatoria para entrevistas presenciales.")
        if self.modality == "virtual" and not (self.meeting_url and self.meeting_url.strip()):
            raise ValueError("El enlace de videollamada es obligatorio para entrevistas virtuales.")
        if self.scheduled_end and self.scheduled_end <= self.scheduled_start:
            raise ValueError("La fecha/hora de fin debe ser posterior a la fecha/hora de inicio.")
        return self


class EntrevistaCrear(EntrevistaBase):
    pass


class EntrevistaReprogramar(EntrevistaBase):
    pass


class EntrevistaRechazar(BaseModel):
    motivo: str = Field(..., min_length=3, max_length=1000)


class EntrevistaRevisar(BaseModel):
    aprobado: bool = True


class EntrevistaOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    scheduled_start: datetime
    scheduled_end: Optional[datetime] = None
    modality: str
    location: Optional[str] = None
    meeting_url: Optional[str] = None
    notes: Optional[str] = None
    status: str
    candidate_feedback: Optional[str] = None
    rejection_count: int
    requires_manual_review: bool
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    # Datos contextuales útiles para el frontend
    vacante_titulo: Optional[str] = None
    candidato_nombre: Optional[str] = None
    empresa_nombre: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
