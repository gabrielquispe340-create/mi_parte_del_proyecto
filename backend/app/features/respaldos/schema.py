import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RespaldoResponse(BaseModel):
    id: uuid.UUID
    archivo: str
    tamanio_bytes: int
    tablas: int
    filas: int
    tipo: str  # manual | previa_restauracion | subido
    nota: str | None = None
    creado_por: str | None = None
    fecha: datetime
    ultima_restauracion: datetime | None = None
    # False si el .zip ya no está en el servidor (p. ej. se recreó el contenedor sin volumen).
    disponible: bool


class CrearRespaldoRequest(BaseModel):
    nota: str | None = Field(default=None, max_length=300)


class RestaurarRequest(BaseModel):
    password: str = Field(min_length=1)
    # Para restaurar de verdad hay que escribir RESTAURAR; el simulacro no lo pide.
    confirmacion: str = ""
    simulacro: bool = False


class RestauracionResponse(BaseModel):
    simulacro: bool
    tablas: int
    filas: int
    bitacora_conservada: int
    vaciadas_extra: list[str]
    respaldo_previo: RespaldoResponse | None = None
    mensaje: str
