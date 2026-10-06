from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class OrdenReporte(BaseModel):
    columna: str = Field(..., max_length=60)
    direccion: Literal["asc", "desc"] = "asc"


class ConsultaReporte(BaseModel):
    """Lo que eligió el usuario: fuente, columnas (en orden), filtros y orden."""

    fuente: str = Field(..., max_length=40)
    columnas: list[str] = Field(..., min_length=1, max_length=30)
    # texto: "abc" · opciones: ["a", "b"] · fechas: {"desde": "2026-10-01", "hasta": null}
    # · números: {"min": 1, "max": 10}
    filtros: dict[str, Any] = Field(default_factory=dict)
    orden: list[OrdenReporte] = Field(default_factory=list, max_length=3)
    titulo: str | None = Field(None, max_length=120)


class ExportarReporte(ConsultaReporte):
    formato: Literal["excel", "pdf", "html"]


class EnviarReporte(ExportarReporte):
    destinatarios: list[EmailStr] = Field(..., min_length=1, max_length=10)
    mensaje: str | None = Field(None, max_length=1000)


class OpcionFiltro(BaseModel):
    valor: str
    etiqueta: str


class ColumnaCatalogo(BaseModel):
    clave: str
    etiqueta: str
    tipo: str
    por_defecto: bool = False


class FiltroCatalogo(BaseModel):
    clave: str
    etiqueta: str
    tipo: str
    opciones: list[OpcionFiltro] = []


class FuenteCatalogo(BaseModel):
    clave: str
    nombre: str
    descripcion: str
    columnas: list[ColumnaCatalogo]
    filtros: list[FiltroCatalogo]
    orden: list[OrdenReporte]


class CatalogoReportes(BaseModel):
    fuentes: list[FuenteCatalogo]
    correo_disponible: bool
    plan_permite: bool = True
    mensaje_plan: str | None = None


class VistaPreviaReporte(BaseModel):
    columnas: list[ColumnaCatalogo]
    filas: list[list[Any]]
    total: int
    pagina: int
    tamanio: int
    descripcion: list[str]


class EnvioReporteResponse(BaseModel):
    mensaje: str
    destinatarios: list[str]
