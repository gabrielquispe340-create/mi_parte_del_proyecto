"""Entidades ORM mapeadas al esquema PostgreSQL real de Supabase (UUID PKs).

Los módulos aún sin implementar (entrevistas, etc.) usan las tablas
correspondientes del mismo esquema cuando se desarrollen.
"""

from app.models.candidato import (
    CandidateEducation,
    CandidateLanguage,
    CandidateProfile,
    CandidateSkill,
    Certification,
    WorkExperience,
)
from app.models.catalogo import FieldOfStudy, JobCategory, Language, Skill
from app.models.empresa import Company, CompanyMember, CompanyVerification, Sector
from app.models.institucion import (
    CompanyInstitution,
    Institution,
    PlanPayment,
    SaasPlan,
    UniversitySignupRequest,
)
from app.models.notificacion import Notification
from app.models.respaldo import SystemBackup
from app.models.seguridad import AuditLog, LoginAttempt
from app.models.usuario import AppUser, Role, UserRole
from app.models.vacante import (
    EmploymentType,
    JobEducationPreference,
    JobLanguageRequirement,
    JobPosting,
    JobSelectionStage,
    JobSkill,
    JobStatus,
    ScreeningOption,
    ScreeningQuestion,
    SeniorityLevel,
    SkillProficiencyLevel,
    WorkModality,
)
from app.models.entrevista import Interview
from app.models.postulacion import (
    Application,
    ApplicationAnswer,
    ApplicationNote,
    ApplicationStageHistory,
    ApplicationStatusHistory,
)

__all__ = [
    "AppUser",
    "Application",
    "Interview",
    "ApplicationAnswer",
    "ApplicationNote",
    "ApplicationStageHistory",
    "ApplicationStatusHistory",
    "AuditLog",
    "CandidateEducation",
    "CandidateLanguage",
    "CandidateProfile",
    "CandidateSkill",
    "Certification",
    "Company",
    "CompanyInstitution",
    "CompanyMember",
    "CompanyVerification",
    "EmploymentType",
    "FieldOfStudy",
    "Institution",
    "JobCategory",
    "JobEducationPreference",
    "JobLanguageRequirement",
    "JobPosting",
    "JobSelectionStage",
    "JobSkill",
    "JobStatus",
    "Language",
    "LoginAttempt",
    "Notification",
    "PlanPayment",
    "Role",
    "SaasPlan",
    "ScreeningOption",
    "ScreeningQuestion",
    "Sector",
    "SeniorityLevel",
    "Skill",
    "SkillProficiencyLevel",
    "SystemBackup",
    "UniversitySignupRequest",
    "UserRole",
    "WorkExperience",
    "WorkModality",
]
