import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RolResponse(BaseModel):
    id: uuid.UUID
    nombre: str
    descripcion: str | None = None


class UsuarioAdminResponse(BaseModel):
    id: uuid.UUID
    correo: str
    estado: str
    fecha_registro: datetime
    ultimo_acceso: datetime | None = None
    roles: list[str] = []
    es_miembro_empresa: bool = False
    institucion_id: uuid.UUID | None = None
    institucion: str | None = None


class AsignarRolRequest(BaseModel):
    rol: str


class CrearUsuarioStaffRequest(BaseModel):
    """Alta de personal institucional. Egresados y empresas se registran solos."""

    correo: EmailStr
    password: str = Field(min_length=8)
    rol: Literal["moderator", "platform_admin"]
    # Lo elige el superadmin; para el admin de una universidad se usa siempre la suya.
    institucion_id: uuid.UUID | None = None


class AsignarRolResponse(BaseModel):
    usuario: UsuarioAdminResponse
    rol_anterior: str | None
    detalle: str
