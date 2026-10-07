import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ComponenteResponse(BaseModel):
    codigo: str
    tipo: str
    modulo: str
    nombre: str
    descripcion: str
    por_defecto: list[str]
    asignable_a: list[str]


class CatalogoPermisosResponse(BaseModel):
    componentes: list[ComponenteResponse]
    siempre_admin: list[str]


class MiembroGrupo(BaseModel):
    id: uuid.UUID
    correo: str
    rol: str


class GrupoResponse(BaseModel):
    id: uuid.UUID
    nombre: str
    descripcion: str | None
    institucion_id: uuid.UUID
    institucion: str | None
    permisos: list[str]
    miembros: list[MiembroGrupo]
    actualizado: datetime


class GuardarGrupoRequest(BaseModel):
    nombre: str = Field(min_length=3, max_length=80)
    descripcion: str | None = Field(default=None, max_length=300)
    # Solo lo indica el superadmin; el admin de una universidad siempre crea en la suya.
    institucion_id: uuid.UUID | None = None
    permisos: list[str] = []
    miembros: list[uuid.UUID] = []


class PersonalResponse(BaseModel):
    """Personal de la universidad que puede pertenecer a grupos, con lo que ve hoy."""

    id: uuid.UUID
    correo: str
    rol: str
    grupos: list[str]
    permisos: list[str]


class MisPermisosResponse(BaseModel):
    permisos: list[str]
    superadmin: bool
