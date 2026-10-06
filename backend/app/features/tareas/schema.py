from datetime import datetime

from pydantic import BaseModel


class CorridaResponse(BaseModel):
    id: str
    tarea: str
    disparador: str  # automatico | manual
    estado: str  # running | success | failure
    resumen: str | None = None
    autor: str | None = None
    inicio: datetime
    fin: datetime | None = None

    model_config = {"from_attributes": True}


class TareaResponse(BaseModel):
    clave: str
    nombre: str
    descripcion: str
    horario: str
    proxima: datetime | None = None
    ultima: CorridaResponse | None = None
    historial: list[CorridaResponse]


class TareasResponse(BaseModel):
    planificador_activo: bool
    hora_diaria: int
    tareas: list[TareaResponse]
