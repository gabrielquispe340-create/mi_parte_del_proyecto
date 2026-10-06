import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BitacoraLogResponse(BaseModel):
    id: uuid.UUID
    usuario_id: uuid.UUID | None = None
    usuario_correo: str | None = None
    ip: str | None = None
    modulo: str
    accion: str
    detalles: str | None = None
    resultado: bool
    fecha: datetime
    cifrada: bool = False

    model_config = {"from_attributes": True}


class EstadoBitacoraResponse(BaseModel):
    cifrada: bool
    entradas_sin_cifrar: int


class AbrirBitacoraRequest(BaseModel):
    clave: str = Field(..., min_length=1, max_length=200)
