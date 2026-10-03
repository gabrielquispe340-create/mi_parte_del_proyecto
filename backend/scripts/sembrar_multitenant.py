"""Siembra datos de demostración del modelo multitenant (SaaS multi-universidad).

Crea un superadmin global, un admin por universidad cliente, 5 empresas globales
habilitadas en distintas universidades (con estados variados), sus vacantes y
egresados de cada universidad con postulaciones. Es idempotente: se puede correr
varias veces sin duplicar datos (busca por correo, NIT y título de vacante).

Requiere haber corrido antes scripts.migrar_multitenant.

Uso (desde la carpeta backend):
    python -m scripts.sembrar_multitenant
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

import app.models  # noqa: F401 - registra todos los modelos
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.features.perfil.repository import EgresadoRepository
from app.models.candidato import CandidateEducation, CandidateProfile, CandidateSkill
from app.models.empresa import Company, CompanyMember
from app.models.institucion import CompanyInstitution
from app.models.postulacion import Application, ApplicationStageHistory, ApplicationStatusHistory
from app.models.usuario import AppUser, Role, UserRole
from app.models.vacante import (
    JobEducationPreference,
    JobPosting,
    JobSelectionStage,
    JobSkill,
    ScreeningOption,
    ScreeningQuestion,
)
from app.security.password_hasher import hash_password

# La contraseña de las cuentas demo no se versiona (el repositorio es público): se define
# en DEMO_PASSWORD dentro de backend/.env y se comparte por el grupo del equipo.
PASSWORD_DEMO = get_settings().demo_password

UAGRM = uuid.UUID("50000000-0000-0000-0000-000000000001")
UMSS = uuid.UUID("50000000-0000-0000-0000-000000000002")
UMSA = uuid.UUID("50000000-0000-0000-0000-000000000003")
UNIFRANZ = uuid.UUID("50000000-0000-0000-0000-000000000005")

CARRERA = {
    "sistemas": uuid.UUID("60000000-0000-0000-0000-000000000001"),
    "informatica": uuid.UUID("60000000-0000-0000-0000-000000000002"),
    "industrial": uuid.UUID("60000000-0000-0000-0000-000000000004"),
    "administracion": uuid.UUID("60000000-0000-0000-0000-000000000007"),
    "contaduria": uuid.UUID("60000000-0000-0000-0000-000000000008"),
    "economia": uuid.UUID("60000000-0000-0000-0000-000000000009"),
    "redes": uuid.UUID("60000000-0000-0000-0000-000000000012"),
}

SKILL = {
    "sql": uuid.UUID("20000000-0000-0000-0000-000000000001"),
    "python": uuid.UUID("20000000-0000-0000-0000-000000000002"),
    "javascript": uuid.UUID("20000000-0000-0000-0000-000000000003"),
    "typescript": uuid.UUID("20000000-0000-0000-0000-000000000004"),
    "angular": uuid.UUID("20000000-0000-0000-0000-000000000005"),
    "react": uuid.UUID("20000000-0000-0000-0000-000000000006"),
    "node": uuid.UUID("20000000-0000-0000-0000-000000000007"),
    "docker": uuid.UUID("20000000-0000-0000-0000-000000000008"),
    "git": uuid.UUID("20000000-0000-0000-0000-000000000009"),
    "java": uuid.UUID("20000000-0000-0000-0000-000000000010"),
    "powerbi": uuid.UUID("20000000-0000-0000-0000-000000000012"),
    "excel": uuid.UUID("20000000-0000-0000-0000-000000000013"),
    "comunicacion": uuid.UUID("20000000-0000-0000-0000-000000000015"),
    "equipo": uuid.UUID("20000000-0000-0000-0000-000000000016"),
    "proyectos": uuid.UUID("20000000-0000-0000-0000-000000000017"),
    "problemas": uuid.UUID("20000000-0000-0000-0000-000000000018"),
}

SECTOR = {
    "tecnologia": uuid.UUID("40000000-0000-0000-0000-000000000001"),
    "finanzas": uuid.UUID("40000000-0000-0000-0000-000000000004"),
    "comercio": uuid.UUID("40000000-0000-0000-0000-000000000006"),
    "agro": uuid.UUID("40000000-0000-0000-0000-000000000008"),
}

CATEGORIA = {
    "tecnologia": uuid.UUID("70000000-0000-0000-0000-000000000001"),
    "finanzas": uuid.UUID("70000000-0000-0000-0000-000000000004"),
    "ingenieria": uuid.UUID("70000000-0000-0000-0000-000000000005"),
    "logistica": uuid.UUID("70000000-0000-0000-0000-000000000010"),
    "administracion": uuid.UUID("70000000-0000-0000-0000-000000000002"),
}

SUPERADMIN = ("superadmin@egresa.bo", "platform_admin", None)
ADMINS_UNIVERSIDAD = [
    ("admin@umss.egresa.bo", "platform_admin", UMSS),
    ("admin@umsa.egresa.bo", "platform_admin", UMSA),
    ("admin@unifranz.egresa.bo", "platform_admin", UNIFRANZ),
    ("moderador@umss.egresa.bo", "moderator", UMSS),
]

ETAPAS = [
    ("Revisión de CV", "Filtro inicial de hojas de vida", False),
    ("Preselección", "Entrevista telefónica breve", False),
    ("Entrevista técnica", "Entrevista con el área solicitante", False),
    ("Contratación", "Oferta y firma de contrato", True),
]

# (clave, datos de empresa, correo del responsable, cargo, {universidad: (estado, motivo)}, vacantes)
EMPRESAS = [
    {
        "clave": "andes",
        "legal_name": "Andes Digital S.R.L.",
        "trade_name": "Andes Digital",
        "tax_id": "3012456019",
        "sector": "tecnologia",
        "size": "medium",
        "city": "Santa Cruz de la Sierra",
        "website": "https://andesdigital.bo",
        "phone": "+591 3 3456789",
        "address": "Av. San Martín 1250, Equipetrol",
        "description": "Fábrica de software que desarrolla plataformas web y móviles para banca, retail y gobierno.",
        "correo": "rrhh@andesdigital.bo",
        "cargo": "Jefa de Talento Humano",
        "universidades": {UAGRM: ("approved", None), UMSS: ("approved", None), UNIFRANZ: ("approved", None),
                          UMSA: ("pending", None)},
        "vacantes": [
            {
                "title": "Desarrollador Frontend Angular Junior",
                "description": "Buscamos un egresado apasionado por el frontend para sumarse al equipo que construye "
                               "portales de autogestión para clientes bancarios.",
                "responsibilities": ["Desarrollar componentes en Angular", "Consumir APIs REST",
                                     "Participar en revisiones de código"],
                "requirements": ["Egresado de Ingeniería de Sistemas o Informática", "Conocimientos de TypeScript"],
                "benefits": ["Seguro de salud privado", "Horario flexible", "Capacitaciones pagadas"],
                "seniority": "junior", "employment": "permanent", "modality": "hybrid",
                "city": "Santa Cruz de la Sierra", "salary": (5000, 7000), "positions": 2,
                "category": "tecnologia", "carreras": ["sistemas", "informatica"],
                "skills": [("angular", "required"), ("typescript", "required"), ("git", "preferred"),
                           ("equipo", "preferred")],
                "preguntas": True,
            },
            {
                "title": "Pasante de Desarrollo Backend (Python)",
                "description": "Pasantía de 6 meses con posibilidad de contratación para desarrollar microservicios "
                               "con FastAPI y PostgreSQL.",
                "responsibilities": ["Implementar endpoints REST", "Escribir pruebas automatizadas"],
                "requirements": ["Estudiante de últimos semestres o egresado reciente", "Bases de Python y SQL"],
                "benefits": ["Estipendio mensual", "Mentoría 1 a 1"],
                "seniority": "internship", "employment": "internship", "modality": "remote",
                "city": "Santa Cruz de la Sierra", "salary": (2500, 3000), "positions": 3,
                "category": "tecnologia", "carreras": ["sistemas", "informatica", "redes"],
                "skills": [("python", "required"), ("sql", "required"), ("docker", "optional")],
            },
        ],
    },
    {
        "clave": "altiplano",
        "legal_name": "Altiplano Analytics S.A.",
        "trade_name": "Altiplano Analytics",
        "tax_id": "3012456027",
        "sector": "tecnologia",
        "size": "small",
        "city": "La Paz",
        "website": "https://altiplanoanalytics.bo",
        "phone": "+591 2 2789456",
        "address": "Calle 21 de Calacoto 8120, Zona Sur",
        "description": "Consultora de ciencia de datos e inteligencia de negocios para minería, retail y sector público.",
        "correo": "talento@altiplanoanalytics.bo",
        "cargo": "Gerente de Operaciones",
        "universidades": {UMSA: ("approved", None), UMSS: ("approved", None), UAGRM: ("pending", None)},
        "vacantes": [
            {
                "title": "Analista de Datos Junior",
                "description": "Te sumarás al equipo de BI para construir tableros y modelos de datos para clientes "
                               "de retail y minería.",
                "responsibilities": ["Construir tableros en Power BI", "Modelar datos en SQL",
                                     "Presentar hallazgos a clientes"],
                "requirements": ["Egresado de Ingeniería de Sistemas, Industrial o Economía"],
                "benefits": ["Bono por desempeño", "Certificaciones de Microsoft pagadas"],
                "seniority": "junior", "employment": "permanent", "modality": "hybrid",
                "city": "La Paz", "salary": (5500, 7500), "positions": 2,
                "category": "tecnologia", "carreras": ["sistemas", "industrial", "economia"],
                "skills": [("sql", "required"), ("powerbi", "required"), ("excel", "preferred"),
                           ("comunicacion", "preferred")],
                "preguntas": True,
            },
            {
                "title": "Científico de Datos (Python)",
                "description": "Desarrollo de modelos predictivos de demanda y churn para clientes corporativos.",
                "responsibilities": ["Entrenar y validar modelos", "Automatizar pipelines de datos"],
                "requirements": ["Experiencia académica o laboral con Python y estadística"],
                "benefits": ["Trabajo remoto", "Presupuesto anual de formación"],
                "seniority": "mid", "employment": "permanent", "modality": "remote",
                "city": "La Paz", "salary": (9000, 12000), "positions": 1,
                "category": "tecnologia", "carreras": ["sistemas", "informatica", "economia"],
                "skills": [("python", "required"), ("sql", "required"), ("problemas", "preferred")],
            },
        ],
    },
    {
        "clave": "vallefin",
        "legal_name": "Valle Fintech S.R.L.",
        "trade_name": "ValleFin",
        "tax_id": "3012456035",
        "sector": "finanzas",
        "size": "startup",
        "city": "Cochabamba",
        "website": "https://vallefin.bo",
        "phone": "+591 4 4523698",
        "address": "Av. América Este 540, Edif. Torre Ketal",
        "description": "Fintech de pagos digitales y microcréditos para emprendedores del eje troncal.",
        "correo": "seleccion@vallefin.bo",
        "cargo": "Líder de Reclutamiento",
        "universidades": {UMSS: ("approved", None), UMSA: ("approved", None), UAGRM: ("approved", None)},
        "vacantes": [
            {
                "title": "Desarrollador Full Stack (Node.js + React)",
                "description": "Construí la billetera digital que usan miles de emprendedores bolivianos.",
                "responsibilities": ["Desarrollar funcionalidades de punta a punta", "Integrar pasarelas de pago"],
                "requirements": ["Egresado de carreras de computación", "Conocimientos de JavaScript"],
                "benefits": ["Stock options", "Semana de 4,5 días"],
                "seniority": "junior", "employment": "permanent", "modality": "hybrid",
                "city": "Cochabamba", "salary": (6000, 8500), "positions": 2,
                "category": "tecnologia", "carreras": ["sistemas", "informatica"],
                "skills": [("javascript", "required"), ("react", "required"), ("node", "required"),
                           ("git", "preferred")],
            },
            {
                "title": "Analista de Riesgo Crediticio",
                "description": "Evaluación de solicitudes de microcrédito con apoyo de modelos de scoring.",
                "responsibilities": ["Analizar solicitudes de crédito", "Elaborar reportes de cartera"],
                "requirements": ["Egresado de Economía, Contaduría o Administración"],
                "benefits": ["Seguro de salud", "Bono trimestral"],
                "seniority": "junior", "employment": "permanent", "modality": "onsite",
                "city": "Cochabamba", "salary": (4500, 6000), "positions": 1,
                "category": "finanzas", "carreras": ["economia", "contaduria", "administracion"],
                "skills": [("excel", "required"), ("sql", "preferred"), ("comunicacion", "preferred")],
            },
        ],
    },
    {
        "clave": "oriente",
        "legal_name": "Oriente Logística S.A.",
        "trade_name": "Oriente Logística",
        "tax_id": "3012456043",
        "sector": "comercio",
        "size": "large",
        "city": "Santa Cruz de la Sierra",
        "website": "https://orientelogistica.bo",
        "phone": "+591 3 3521470",
        "address": "Parque Industrial PI-12, Mz. 8",
        "description": "Operador logístico con centros de distribución en Santa Cruz, Cochabamba y La Paz.",
        "correo": "empleos@orientelogistica.bo",
        "cargo": "Coordinador de Selección",
        "universidades": {UAGRM: ("approved", None), UNIFRANZ: ("approved", None),
                          UMSA: ("rejected", "La carrera de Ingeniería Industrial no tiene convenio vigente.")},
        "vacantes": [
            {
                "title": "Ingeniero de Operaciones Logísticas",
                "description": "Optimización de rutas y procesos en nuestro centro de distribución principal.",
                "responsibilities": ["Mejorar indicadores de despacho", "Liderar proyectos de mejora continua"],
                "requirements": ["Egresado de Ingeniería Industrial"],
                "benefits": ["Transporte de personal", "Comedor subvencionado"],
                "seniority": "junior", "employment": "permanent", "modality": "onsite",
                "city": "Santa Cruz de la Sierra", "salary": (5000, 6500), "positions": 2,
                "category": "logistica", "carreras": ["industrial", "administracion"],
                "skills": [("excel", "required"), ("proyectos", "preferred"), ("equipo", "preferred")],
                "preguntas": True,
            },
            {
                "title": "Analista de Sistemas (ERP)",
                "description": "Soporte y parametrización del ERP que gestiona inventarios y facturación.",
                "responsibilities": ["Atender incidencias del ERP", "Documentar procesos"],
                "requirements": ["Egresado de Ingeniería de Sistemas", "Manejo de SQL"],
                "benefits": ["Seguro de salud", "Aguinaldo doble según ley"],
                "seniority": "junior", "employment": "permanent", "modality": "onsite",
                "city": "Santa Cruz de la Sierra", "salary": (4500, 5500), "positions": 1,
                "category": "tecnologia", "carreras": ["sistemas", "informatica"],
                "skills": [("sql", "required"), ("problemas", "preferred")],
            },
        ],
    },
    {
        "clave": "chiquitano",
        "legal_name": "Chiquitano Agroindustrial S.A.",
        "trade_name": "Chiquitano Agro",
        "tax_id": "3012456051",
        "sector": "agro",
        "size": "corporation",
        "city": "Santa Cruz de la Sierra",
        "website": "https://chiquitanoagro.bo",
        "phone": "+591 3 3698521",
        "address": "Carretera a Cotoca km 9",
        "description": "Agroindustria exportadora de soya, girasol y derivados con operaciones en la Chiquitanía.",
        "correo": "rrhh@chiquitanoagro.bo",
        "cargo": "Gerente de Recursos Humanos",
        "universidades": {UAGRM: ("approved", None), UMSS: ("pending", None),
                          UMSA: ("suspended", "Incumplimiento del convenio de pasantías.")},
        "vacantes": [
            {
                "title": "Asistente de Planificación Agrícola",
                "description": "Apoyo a la planificación de campañas agrícolas y control de costos de producción.",
                "responsibilities": ["Consolidar reportes de campo", "Controlar presupuesto de campaña"],
                "requirements": ["Egresado de Ingeniería Industrial, Administración o Economía"],
                "benefits": ["Vivienda en campamento", "Bono de producción"],
                "seniority": "junior", "employment": "temporary", "modality": "onsite",
                "city": "San José de Chiquitos", "salary": (4000, 5000), "positions": 2,
                "category": "administracion", "carreras": ["industrial", "administracion", "economia"],
                "skills": [("excel", "required"), ("powerbi", "preferred"), ("equipo", "preferred")],
            },
            {
                "title": "Técnico de Redes y Soporte",
                "description": "Mantenimiento de la red de planta y soporte a usuarios en oficinas centrales.",
                "responsibilities": ["Administrar switches y enlaces", "Brindar soporte de primer nivel"],
                "requirements": ["Egresado de Redes y Telecomunicaciones o Sistemas"],
                "benefits": ["Seguro de salud", "Capacitación en Cisco"],
                "seniority": "junior", "employment": "permanent", "modality": "onsite",
                "city": "Santa Cruz de la Sierra", "salary": (4200, 5200), "positions": 1,
                "category": "tecnologia", "carreras": ["redes", "sistemas"],
                "skills": [("problemas", "required"), ("comunicacion", "preferred")],
            },
        ],
    },
]

# (correo, nombres, apellidos, CI, universidad, ciudad, carrera, año egreso, estado, titular, skills)
EGRESADOS = [
    ("sofia.vargas@uagrm.egresa.bo", "Sofía", "Vargas Justiniano", "7712001", UAGRM, "Santa Cruz de la Sierra",
     "sistemas", 2024, "verified", "Desarrolladora Frontend", ["angular", "typescript", "git", "equipo"]),
    ("marco.rivero@uagrm.egresa.bo", "Marco", "Rivero Suárez", "7712002", UAGRM, "Santa Cruz de la Sierra",
     "industrial", 2023, "pending", "Ingeniero Industrial", ["excel", "proyectos"]),
    ("valeria.quiroga@umss.egresa.bo", "Valeria", "Quiroga Camacho", "5512001", UMSS, "Cochabamba",
     "informatica", 2024, "verified", "Desarrolladora Full Stack", ["javascript", "react", "node", "git"]),
    ("jorge.montano@umss.egresa.bo", "Jorge", "Montaño Rocha", "5512002", UMSS, "Cochabamba",
     "economia", 2023, "verified", "Economista", ["excel", "sql", "comunicacion"]),
    ("paola.arce@umss.egresa.bo", "Paola", "Arce Villarroel", "5512003", UMSS, "Cochabamba",
     "sistemas", 2025, "pending", "Egresada de Sistemas", ["python", "sql"]),
    ("luis.mamani@umsa.egresa.bo", "Luis", "Mamani Choque", "4412001", UMSA, "La Paz",
     "sistemas", 2024, "verified", "Analista de Datos", ["sql", "powerbi", "python"]),
    ("andrea.gutierrez@umsa.egresa.bo", "Andrea", "Gutiérrez Loza", "4412002", UMSA, "La Paz",
     "economia", 2023, "verified", "Analista Financiera", ["excel", "sql", "powerbi"]),
    ("rodrigo.condori@umsa.egresa.bo", "Rodrigo", "Condori Apaza", "4412003", UMSA, "El Alto",
     "redes", 2025, "pending", "Técnico en Redes", ["problemas", "comunicacion"]),
    ("camila.salvatierra@unifranz.egresa.bo", "Camila", "Salvatierra Paz", "8812001", UNIFRANZ,
     "Santa Cruz de la Sierra", "administracion", 2024, "verified", "Administradora de Empresas",
     ["excel", "proyectos", "comunicacion"]),
    ("diego.antelo@unifranz.egresa.bo", "Diego", "Antelo Ribera", "8812002", UNIFRANZ, "Santa Cruz de la Sierra",
     "sistemas", 2025, "pending", "Egresado de Sistemas", ["javascript", "git"]),
]

# (correo egresado, título vacante, estado, índice de etapa actual o None)
POSTULACIONES = [
    ("sofia.vargas@uagrm.egresa.bo", "Desarrollador Frontend Angular Junior", "interview", 2),
    ("sofia.vargas@uagrm.egresa.bo", "Desarrollador Full Stack (Node.js + React)", "applied", None),
    ("valeria.quiroga@umss.egresa.bo", "Desarrollador Full Stack (Node.js + React)", "shortlisted", 1),
    ("valeria.quiroga@umss.egresa.bo", "Desarrollador Frontend Angular Junior", "screening", 0),
    ("jorge.montano@umss.egresa.bo", "Analista de Riesgo Crediticio", "applied", None),
    ("jorge.montano@umss.egresa.bo", "Analista de Datos Junior", "screening", 0),
    ("luis.mamani@umsa.egresa.bo", "Analista de Datos Junior", "interview", 2),
    ("luis.mamani@umsa.egresa.bo", "Científico de Datos (Python)", "applied", None),
    ("andrea.gutierrez@umsa.egresa.bo", "Analista de Riesgo Crediticio", "rejected", 0),
    ("camila.salvatierra@unifranz.egresa.bo", "Ingeniero de Operaciones Logísticas", "shortlisted", 1),
]


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _usuario(db, correo: str, rol: str, institution_id: uuid.UUID | None) -> AppUser:
    usuario = db.scalar(select(AppUser).where(AppUser.email == correo))
    if usuario is None:
        usuario = AppUser(email=correo)
        db.add(usuario)
    usuario.password_hash = hash_password(PASSWORD_DEMO)
    usuario.account_status = "active"
    usuario.deleted_at = None
    usuario.institution_id = institution_id
    db.flush()
    role = db.scalar(select(Role).where(Role.name == rol))
    if db.get(UserRole, (usuario.id, role.id)) is None:
        db.add(UserRole(user_id=usuario.id, role_id=role.id))
    return usuario


def _empresa(db, datos: dict) -> Company:
    empresa = db.scalar(select(Company).where(Company.tax_id == datos["tax_id"]))
    if empresa is None:
        empresa = Company(tax_id=datos["tax_id"], legal_name=datos["legal_name"])
        db.add(empresa)
    empresa.legal_name = datos["legal_name"]
    empresa.trade_name = datos["trade_name"]
    empresa.sector_id = SECTOR[datos["sector"]]
    empresa.company_size = datos["size"]
    empresa.city = datos["city"]
    empresa.country_code = "BO"
    empresa.website = datos["website"]
    empresa.phone = datos["phone"]
    empresa.address = datos["address"]
    empresa.description = datos["description"]
    empresa.contact_email = datos["correo"]
    empresa.verification_status = "verified"
    empresa.account_status = "active"
    db.flush()

    responsable = _usuario(db, datos["correo"], "empresa", None)
    if db.scalar(select(CompanyMember).where(CompanyMember.user_id == responsable.id)) is None:
        db.add(CompanyMember(user_id=responsable.id, company_id=empresa.id, member_type="owner",
                             job_title=datos["cargo"], is_active=True))

    for inst_id, (estado, motivo) in datos["universidades"].items():
        vinculo = db.get(CompanyInstitution, (empresa.id, inst_id))
        if vinculo is None:
            vinculo = CompanyInstitution(company_id=empresa.id, institution_id=inst_id)
            db.add(vinculo)
        vinculo.status = estado
        vinculo.rejection_reason = motivo
        vinculo.reviewed_at = None if estado == "pending" else _ahora()
    db.flush()
    return empresa


def _vacante(db, empresa: Company, creador: AppUser, datos: dict) -> JobPosting:
    vacante = db.scalar(select(JobPosting).where(JobPosting.company_id == empresa.id,
                                                 JobPosting.title == datos["title"]))
    if vacante is None:
        vacante = JobPosting(company_id=empresa.id, title=datos["title"], description=datos["description"],
                             seniority_level=datos["seniority"], employment_type=datos["employment"],
                             city=datos["city"])
        db.add(vacante)
    vacante.created_by = creador.id
    vacante.category_id = CATEGORIA[datos["category"]]
    vacante.description = datos["description"]
    vacante.responsibilities_json = datos["responsibilities"]
    vacante.requirements_json = datos["requirements"]
    vacante.benefits_json = datos["benefits"]
    vacante.seniority_level = datos["seniority"]
    vacante.employment_type = datos["employment"]
    vacante.work_modality = datos["modality"]
    vacante.min_education_level = "undergraduate"
    vacante.city = datos["city"]
    vacante.country_code = "BO"
    vacante.salary_min = Decimal(datos["salary"][0])
    vacante.salary_max = Decimal(datos["salary"][1])
    vacante.currency = "BOB"
    vacante.salary_visible = True
    vacante.positions_available = datos["positions"]
    vacante.status = "published"
    vacante.published_at = vacante.published_at or _ahora() - timedelta(days=5)
    vacante.application_deadline = _ahora() + timedelta(days=45)
    db.flush()

    existentes_skill = {s.skill_id for s in db.scalars(select(JobSkill).where(JobSkill.job_posting_id == vacante.id))}
    for clave, importancia in datos["skills"]:
        if SKILL[clave] not in existentes_skill:
            db.add(JobSkill(job_posting_id=vacante.id, skill_id=SKILL[clave], importance=importancia,
                            min_proficiency="intermediate"))

    existentes_carrera = {
        p.field_of_study_id
        for p in db.scalars(select(JobEducationPreference).where(JobEducationPreference.job_posting_id == vacante.id))
    }
    for clave in datos["carreras"]:
        if CARRERA[clave] not in existentes_carrera:
            db.add(JobEducationPreference(job_posting_id=vacante.id, field_of_study_id=CARRERA[clave],
                                          education_level="undergraduate", is_required=False))

    if db.scalar(select(JobSelectionStage).where(JobSelectionStage.job_posting_id == vacante.id)) is None:
        for numero, (nombre, descripcion, terminal) in enumerate(ETAPAS, start=1):
            db.add(JobSelectionStage(job_posting_id=vacante.id, stage_number=numero, name=nombre,
                                     description=descripcion, is_terminal=terminal))

    if datos.get("preguntas") and db.scalar(
        select(ScreeningQuestion).where(ScreeningQuestion.job_posting_id == vacante.id)
    ) is None:
        pregunta = ScreeningQuestion(job_posting_id=vacante.id, question_text="¿Tenés disponibilidad inmediata?",
                                     question_type="single_choice", is_required=True, is_knockout=True, position=0)
        db.add(pregunta)
        db.flush()
        db.add(ScreeningOption(question_id=pregunta.id, option_text="Sí", is_accepted=True, position=0))
        db.add(ScreeningOption(question_id=pregunta.id, option_text="No", is_accepted=False, position=1))
        db.add(ScreeningQuestion(job_posting_id=vacante.id, question_text="¿Por qué te interesa este puesto?",
                                 question_type="text", is_required=False, is_knockout=False, position=1))
    db.flush()
    return vacante


def _egresado(db, fila) -> CandidateProfile:
    correo, nombres, apellidos, ci, inst_id, ciudad, carrera, anio, estado, titular, skills = fila
    usuario = _usuario(db, correo, "candidate", None)
    perfil = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == usuario.id))
    if perfil is None:
        perfil = CandidateProfile(user_id=usuario.id, first_name=nombres, last_name=apellidos)
        db.add(perfil)
    perfil.institution_id = inst_id
    perfil.first_name = nombres
    perfil.last_name = apellidos
    perfil.city = ciudad
    perfil.country_code = "BO"
    perfil.document_type = "ci"
    perfil.document_number = ci
    perfil.document_country_code = "BO"
    perfil.verification_status = estado
    perfil.verified_at = _ahora() if estado == "verified" else None
    perfil.professional_headline = titular
    perfil.professional_summary = f"{titular} egresado/a en {anio}, con interés en crecer profesionalmente."
    perfil.availability = "inmediata"
    perfil.job_search_status = "actively_looking"
    perfil.profile_visibility = "platform"
    perfil.contact_visibility = True
    perfil.phone = f"+591 7{ci[-7:]}"
    db.flush()

    marcador = EgresadoRepository.MARCADOR_EDUCACION_REGISTRO
    if db.scalar(select(CandidateEducation).where(CandidateEducation.candidate_id == perfil.id,
                                                  CandidateEducation.description.like(f"{marcador}%"))) is None:
        institucion_nombre = db.get(app.models.Institution, inst_id).name
        db.add(CandidateEducation(candidate_id=perfil.id, institution_id=inst_id, institution_name=institucion_nombre,
                                  field_of_study_id=CARRERA[carrera], program_name="Carrera universitaria",
                                  education_level="undergraduate", academic_status="graduated",
                                  graduation_date=date(anio, 12, 31),
                                  description=f"{marcador} Matrícula: {ci[-6:]}{anio}"))

    existentes = {s.skill_id for s in db.scalars(select(CandidateSkill).where(CandidateSkill.candidate_id == perfil.id))}
    for clave in skills:
        if SKILL[clave] not in existentes:
            db.add(CandidateSkill(candidate_id=perfil.id, skill_id=SKILL[clave], proficiency_level="intermediate"))
    db.flush()
    return perfil


def _postulacion(db, perfil: CandidateProfile, vacante: JobPosting, estado: str, indice_etapa: int | None,
                 reclutador: AppUser) -> None:
    if db.scalar(select(Application).where(Application.candidate_id == perfil.id,
                                           Application.job_id == vacante.id)) is not None:
        return
    etapas = list(db.scalars(select(JobSelectionStage).where(JobSelectionStage.job_posting_id == vacante.id)
                             .order_by(JobSelectionStage.stage_number)))
    inicio = _ahora() - timedelta(days=4)
    postulacion = Application(candidate_id=perfil.id, job_id=vacante.id, current_status="applied",
                              cover_letter="Me interesa mucho formar parte de su equipo.")
    db.add(postulacion)
    db.flush()
    db.add(ApplicationStatusHistory(application_id=postulacion.id, from_status=None, to_status="applied",
                                    reason="Postulación registrada"))

    if indice_etapa is not None:
        for i in range(indice_etapa + 1):
            ultima = i == indice_etapa
            resultado = "pending" if ultima and estado != "rejected" else ("failed" if ultima else "passed")
            db.add(ApplicationStageHistory(application_id=postulacion.id, stage_id=etapas[i].id,
                                           entered_at=inicio + timedelta(days=i), changed_by=reclutador.id,
                                           left_at=None if resultado == "pending" else inicio + timedelta(days=i + 1),
                                           result=resultado))
        postulacion.current_stage_id = etapas[indice_etapa].id

    if estado != "applied":
        postulacion.current_status = estado
        db.add(ApplicationStatusHistory(application_id=postulacion.id, from_status="applied", to_status=estado,
                                        changed_by=reclutador.id,
                                        reason="Perfil no ajustado al puesto" if estado == "rejected" else None))
    db.flush()


def ejecutar() -> None:
    if not PASSWORD_DEMO:
        raise SystemExit("Falta DEMO_PASSWORD en backend/.env (pedila por el grupo del equipo).")
    with SessionLocal() as db:
        print("[1/5] Superadmin y administradores por universidad...")
        _usuario(db, *SUPERADMIN)
        for fila in ADMINS_UNIVERSIDAD:
            _usuario(db, *fila)
        db.commit()

        print("[2/5] Empresas globales y sus vínculos con universidades...")
        empresas: dict[str, tuple[Company, AppUser]] = {}
        for datos in EMPRESAS:
            empresa = _empresa(db, datos)
            responsable = db.scalar(select(AppUser).where(AppUser.email == datos["correo"]))
            empresas[datos["clave"]] = (empresa, responsable)
        db.commit()

        print("[3/5] Vacantes publicadas con etapas y preguntas de filtro...")
        vacantes: dict[str, tuple[JobPosting, AppUser]] = {}
        for datos in EMPRESAS:
            empresa, responsable = empresas[datos["clave"]]
            for datos_vacante in datos["vacantes"]:
                vacantes[datos_vacante["title"]] = (_vacante(db, empresa, responsable, datos_vacante), responsable)
        db.commit()

        print("[4/5] Egresados por universidad...")
        perfiles = {fila[0]: _egresado(db, fila) for fila in EGRESADOS}
        db.commit()

        print("[5/5] Postulaciones en distintas etapas...")
        for correo, titulo, estado, indice in POSTULACIONES:
            vacante, reclutador = vacantes[titulo]
            _postulacion(db, perfiles[correo], vacante, estado, indice, reclutador)
        db.commit()

    print("\nListo. Las cuentas demo usan la contraseña definida en DEMO_PASSWORD.")


if __name__ == "__main__":
    ejecutar()
