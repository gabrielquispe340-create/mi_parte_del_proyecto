"""Motor de afinidad egresado ↔ vacante (HU-23, módulo 5.1.11).

Compara el perfil profesional del egresado con los requisitos de una vacante en cuatro
criterios (carrera, habilidades, experiencia e idiomas), calcula un porcentaje y explica
qué cumple y qué le falta. Lo usan las recomendaciones, la búsqueda de vacantes (HU-13) y
el pipeline de selección de la empresa, para que el porcentaje sea el mismo en todos lados.

Regla de la HU: solo se usan datos profesionales. El motor nunca lee edad, género, foto,
documento, ciudad ni ningún otro dato personal del egresado.

El cálculo se hace en cada consulta con el perfil vigente, así que se actualiza solo
cuando el egresado edita su perfil.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import Date, String, cast, literal, null, select, union_all
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.candidato import CandidateEducation, CandidateLanguage, CandidateSkill, WorkExperience
from app.models.catalogo import FieldOfStudy
from app.models.vacante import JobPosting

# Peso de cada criterio sobre el 100% (solo cuentan los que la vacante especifica).
PESOS = {"carrera": 30, "habilidades": 40, "experiencia": 15, "idiomas": 15}
NOMBRES = {"carrera": "Carrera", "habilidades": "Habilidades", "experiencia": "Experiencia", "idiomas": "Idiomas"}
# Sin requisitos comparables la afinidad es neutral.
AFINIDAD_NEUTRAL = 50

_NIVEL_HABILIDAD = {"basic": 1, "intermediate": 2, "advanced": 3, "expert": 4}
_NIVEL_IDIOMA = {"basic": 1, "intermediate": 2, "advanced": 3, "native": 4}
_TEXTO_NIVEL = {
    "basic": "básico",
    "intermediate": "intermedio",
    "advanced": "avanzado",
    "expert": "experto",
    "native": "nativo",
}
_PESO_IMPORTANCIA = {"required": 3, "preferred": 2, "optional": 1}
# Años esperables cuando la vacante no indica la experiencia mínima.
_ANIOS_POR_SENIORITY = {"mid": 2, "senior": 5, "lead": 7}
_TEXTO_SENIORITY = {"mid": "Semi senior", "senior": "Senior", "lead": "Líder"}


def ia_activa() -> bool:
    return get_settings().ia_recomendaciones_activas


@dataclass
class PerfilAfinidad:
    """Datos profesionales del egresado que entran en el cálculo (y nada más)."""

    carreras: dict[uuid.UUID, str] = field(default_factory=dict)  # field_of_study_id -> nombre
    habilidades: dict[uuid.UUID, str | None] = field(default_factory=dict)  # skill_id -> nivel
    idiomas: dict[uuid.UUID, str] = field(default_factory=dict)  # language_id -> nivel
    anios_experiencia: float = 0.0

    def faltantes(self) -> list[str]:
        """Secciones vacías del perfil que bajan la afinidad."""
        avisos = []
        if not self.carreras:
            avisos.append("Agregá tu carrera en Formación académica.")
        if not self.habilidades:
            avisos.append("Agregá tus habilidades.")
        if self.anios_experiencia == 0:
            avisos.append("Agregá tu experiencia laboral (pasantías y trabajos).")
        if not self.idiomas:
            avisos.append("Agregá los idiomas que manejás.")
        return avisos


@dataclass
class Criterio:
    clave: str
    nombre: str
    peso: int
    cumplimiento: int  # 0-100
    estado: str  # cumple | parcial | no_cumple
    detalle: str
    coincidencias: list[str] = field(default_factory=list)
    faltantes: list[str] = field(default_factory=list)


@dataclass
class Afinidad:
    porcentaje: int
    criterios: list[Criterio]


# ─── Carga del perfil ────────────────────────────────────────────────────────


def perfiles_de_candidatos(db: Session, candidate_ids: set[uuid.UUID]) -> dict[uuid.UUID, PerfilAfinidad]:
    """Perfiles de afinidad de varios egresados en una sola consulta."""
    perfiles = {cid: PerfilAfinidad() for cid in candidate_ids}
    if not candidate_ids:
        return perfiles

    sin_uuid = cast(null(), UUID(as_uuid=True))
    sin_texto = cast(null(), String)
    sin_fecha = cast(null(), Date)
    carreras = (
        select(
            CandidateEducation.candidate_id,
            literal("carrera").label("tipo"),
            CandidateEducation.field_of_study_id.label("ref"),
            FieldOfStudy.name.label("texto"),
            sin_fecha.label("desde"),
            sin_fecha.label("hasta"),
        )
        .join(FieldOfStudy, FieldOfStudy.id == CandidateEducation.field_of_study_id)
        .where(CandidateEducation.candidate_id.in_(candidate_ids))
    )
    habilidades = select(
        CandidateSkill.candidate_id,
        literal("habilidad"),
        CandidateSkill.skill_id,
        CandidateSkill.proficiency_level,
        sin_fecha,
        sin_fecha,
    ).where(CandidateSkill.candidate_id.in_(candidate_ids))
    idiomas = select(
        CandidateLanguage.candidate_id,
        literal("idioma"),
        CandidateLanguage.language_id,
        CandidateLanguage.proficiency_level,
        sin_fecha,
        sin_fecha,
    ).where(CandidateLanguage.candidate_id.in_(candidate_ids))
    experiencias = select(
        WorkExperience.candidate_id,
        literal("experiencia"),
        sin_uuid,
        sin_texto,
        WorkExperience.start_date,
        WorkExperience.end_date,
    ).where(WorkExperience.candidate_id.in_(candidate_ids))

    periodos: dict[uuid.UUID, list[tuple[date, date]]] = {cid: [] for cid in candidate_ids}
    hoy = date.today()
    for cid, tipo, ref, texto, desde, hasta in db.execute(union_all(carreras, habilidades, idiomas, experiencias)):
        perfil = perfiles[cid]
        if tipo == "carrera":
            perfil.carreras[ref] = texto
        elif tipo == "habilidad":
            perfil.habilidades[ref] = texto
        elif tipo == "idioma":
            perfil.idiomas[ref] = texto
        elif desde is not None:
            periodos[cid].append((desde, min(hasta or hoy, hoy)))
    for cid, lista in periodos.items():
        perfiles[cid].anios_experiencia = _anios_sin_superposicion(lista)
    return perfiles


def _anios_sin_superposicion(periodos: list[tuple[date, date]]) -> float:
    """Suma los períodos trabajados sin contar dos veces los que se superponen."""
    dias = 0
    fin_actual: date | None = None
    for desde, hasta in sorted(periodos):
        if hasta <= desde:
            continue
        if fin_actual is not None and desde < fin_actual:
            desde = fin_actual
        if hasta > desde:
            dias += (hasta - desde).days
            fin_actual = hasta
    return round(dias / 365.25, 1)


# ─── Cálculo ─────────────────────────────────────────────────────────────────


def evaluar(vacante: JobPosting, perfil: PerfilAfinidad) -> Afinidad:
    """Necesita cargadas skills→skill, education_preferences y language_requirements."""
    criterios = [
        c
        for c in (
            _criterio_carrera(vacante, perfil),
            _criterio_habilidades(vacante, perfil),
            _criterio_experiencia(vacante, perfil),
            _criterio_idiomas(vacante, perfil),
        )
        if c is not None
    ]
    if not criterios:
        return Afinidad(AFINIDAD_NEUTRAL, [])
    total_peso = sum(c.peso for c in criterios)
    porcentaje = round(sum(c.cumplimiento * c.peso for c in criterios) / total_peso)
    return Afinidad(porcentaje, criterios)


def calcular_afinidad(perfil: PerfilAfinidad, vacante: JobPosting) -> Afinidad:
    """Alias para evaluar afinidad candidato ↔ vacante."""
    return evaluar(vacante, perfil)


def _criterio(clave: str, fraccion: float, detalle: str, coincidencias=None, faltantes=None) -> Criterio:
    cumplimiento = round(max(0.0, min(1.0, fraccion)) * 100)
    estado = "cumple" if cumplimiento >= 100 else "parcial" if cumplimiento > 0 else "no_cumple"
    return Criterio(
        clave=clave,
        nombre=NOMBRES[clave],
        peso=PESOS[clave],
        cumplimiento=cumplimiento,
        estado=estado,
        detalle=detalle,
        coincidencias=coincidencias or [],
        faltantes=faltantes or [],
    )


def _criterio_carrera(vacante: JobPosting, perfil: PerfilAfinidad) -> Criterio | None:
    pedidas = {
        ep.field_of_study_id: ep.field_of_study.name
        for ep in vacante.education_preferences
        if ep.field_of_study_id and ep.field_of_study
    }
    if not pedidas:
        return None
    coinciden = [pedidas[c] for c in pedidas if c in perfil.carreras]
    if coinciden:
        return _criterio("carrera", 1, f"Tu carrera ({', '.join(coinciden)}) es una de las que busca la vacante.", coinciden)
    return _criterio(
        "carrera", 0, f"La vacante busca: {', '.join(pedidas.values())}.", faltantes=list(pedidas.values())
    )


def _criterio_habilidades(vacante: JobPosting, perfil: PerfilAfinidad) -> Criterio | None:
    pedidas = [js for js in vacante.skills if js.skill]
    if not pedidas:
        return None
    # Si la empresa ponderó todas las habilidades se usa su peso; si no, la importancia.
    usar_peso = all(js.weight for js in pedidas)
    puntos = total = 0.0
    coincidencias: list[str] = []
    faltantes: list[str] = []
    for js in pedidas:
        peso = js.weight if usar_peso else _PESO_IMPORTANCIA.get(js.importance or "required", 3)
        total += peso
        if js.skill_id not in perfil.habilidades:
            faltantes.append(js.skill.name + (" (obligatoria)" if (js.importance or "required") == "required" else ""))
            continue
        nivel = perfil.habilidades[js.skill_id]
        if js.min_proficiency and nivel and _NIVEL_HABILIDAD.get(nivel, 0) < _NIVEL_HABILIDAD.get(js.min_proficiency, 0):
            puntos += peso * 0.5
            coincidencias.append(f"{js.skill.name} (pide nivel {_TEXTO_NIVEL.get(js.min_proficiency, js.min_proficiency)})")
        else:
            puntos += peso
            coincidencias.append(js.skill.name)
    detalle = f"Tenés {len(coincidencias)} de {len(pedidas)} habilidades que pide la vacante."
    return _criterio("habilidades", puntos / total, detalle, coincidencias, faltantes)


def _criterio_experiencia(vacante: JobPosting, perfil: PerfilAfinidad) -> Criterio | None:
    pedidos = vacante.min_years_experience or _ANIOS_POR_SENIORITY.get(vacante.seniority_level)
    if not pedidos:
        return None
    origen = (
        ""
        if vacante.min_years_experience
        else f" (estimado por ser un puesto {_TEXTO_SENIORITY.get(vacante.seniority_level, vacante.seniority_level)})"
    )
    tenes = (
        f"tenés {_texto_anios(perfil.anios_experiencia)}"
        if perfil.anios_experiencia > 0
        else "no registraste experiencia en tu perfil"
    )
    detalle = f"Pide {_texto_anios(pedidos)} de experiencia{origen}; {tenes}."
    return _criterio("experiencia", perfil.anios_experiencia / pedidos, detalle)


def _criterio_idiomas(vacante: JobPosting, perfil: PerfilAfinidad) -> Criterio | None:
    pedidos = [r for r in vacante.language_requirements if r.language]
    if not pedidos:
        return None
    puntos = total = 0.0
    coincidencias: list[str] = []
    faltantes: list[str] = []
    for req in pedidos:
        peso = 2 if req.is_required else 1
        total += peso
        nombre = f"{req.language.name} {_TEXTO_NIVEL.get(req.proficiency_level, req.proficiency_level)}"
        nivel = perfil.idiomas.get(req.language_id)
        if nivel is None:
            faltantes.append(nombre)
        elif _NIVEL_IDIOMA.get(nivel, 0) >= _NIVEL_IDIOMA.get(req.proficiency_level, 0):
            puntos += peso
            coincidencias.append(nombre)
        else:
            puntos += peso * 0.5
            coincidencias.append(f"{req.language.name} (tenés nivel {_TEXTO_NIVEL.get(nivel, nivel)})")
    detalle = f"Cumplís {len(coincidencias)} de {len(pedidos)} idiomas que pide la vacante."
    if any("(tenés nivel" in c for c in coincidencias):
        detalle += " En alguno tu nivel es menor al pedido."
    return _criterio("idiomas", puntos / total, detalle, coincidencias, faltantes)


def _texto_anios(anios: float) -> str:
    if anios < 1:
        meses = max(1, round(anios * 12))
        return f"{meses} {'mes' if meses == 1 else 'meses'}"
    texto = f"{anios:.1f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{texto} {'año' if texto == '1' else 'años'}"
