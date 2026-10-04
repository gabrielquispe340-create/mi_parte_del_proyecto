"""HU-18: comparar perfiles de postulantes lado a lado."""
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.main import app
from app.models.candidato import (
    CandidateEducation,
    CandidateLanguage,
    CandidateProfile,
    CandidateSkill,
    WorkExperience,
)
from app.models.catalogo import Language, Skill
from app.models.empresa import Company, CompanyMember
from app.models.postulacion import Application
from app.models.seguridad import AuditLog
from app.models.usuario import AppUser, Role, UserRole
from app.models.vacante import JobPosting, JobSkill
from app.security.jwt_provider import create_access_token

client = TestClient(app)


@pytest.fixture
def db_session():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _usuario(db: Session, prefijo: str, rol: str) -> AppUser:
    if not db.query(Role).filter_by(name=rol).first():
        db.add(Role(name=rol))
        db.flush()
    usuario = AppUser(email=f"{prefijo}_{uuid.uuid4().hex[:8]}@test.bo", password_hash="x", account_status="active")
    db.add(usuario)
    db.flush()
    db.add(UserRole(user_id=usuario.id, role_id=db.query(Role).filter_by(name=rol).first().id))
    return usuario


def _empresa(db: Session) -> tuple[AppUser, Company]:
    usuario = _usuario(db, "empresa", "empresa")
    empresa = Company(
        legal_name=f"Empresa HU18 {uuid.uuid4().hex[:4]}",
        tax_id=f"NIT-{uuid.uuid4().hex[:8]}",
        verification_status="verified",
        account_status="active",
    )
    db.add(empresa)
    db.flush()
    db.add(CompanyMember(user_id=usuario.id, company_id=empresa.id, member_type="recruiter", is_active=True))
    return usuario, empresa


def _vacante(db: Session, empresa: Company, autor: AppUser) -> JobPosting:
    vacante = JobPosting(
        company_id=empresa.id,
        title="Analista de datos",
        description="Vacante de prueba HU-18",
        seniority_level="junior",
        employment_type="permanent",
        work_modality="remote",
        city="Santa Cruz",
        status="published",
        created_by=autor.id,
    )
    db.add(vacante)
    db.flush()
    return vacante


def _postulante(db: Session, vacante: JobPosting, nombre: str, estado: str = "screening") -> Application:
    usuario = _usuario(db, "cand", "candidate")
    perfil = CandidateProfile(user_id=usuario.id, first_name=nombre, last_name="Prueba", verification_status="verified")
    db.add(perfil)
    db.flush()
    postulacion = Application(candidate_id=perfil.id, job_id=vacante.id, current_status=estado)
    db.add(postulacion)
    db.flush()
    return postulacion


@pytest.fixture
def datos(db_session: Session):
    db = db_session
    usuario_empresa, empresa = _empresa(db)
    vacante = _vacante(db, empresa, usuario_empresa)

    sql = Skill(name=f"SQL HU18 {uuid.uuid4().hex[:6]}", category="Datos")
    ingles = Language(name=f"Inglés HU18 {uuid.uuid4().hex[:6]}")
    db.add_all([sql, ingles])
    db.flush()
    db.add(JobSkill(job_posting_id=vacante.id, skill_id=sql.id, importance="required"))

    # Ana tiene el CV completo y la habilidad requerida; Beto, el CV vacío.
    ana = _postulante(db, vacante, "Ana")
    db.add_all(
        [
            CandidateEducation(
                candidate_id=ana.candidate_id,
                institution_name="UAGRM",
                program_name="Ingeniería en Sistemas",
                academic_status="graduated",
            ),
            WorkExperience(
                candidate_id=ana.candidate_id,
                company_name="Pasantía SRL",
                position_title="Pasante de datos",
                start_date=date(2024, 2, 1),
            ),
            WorkExperience(
                candidate_id=ana.candidate_id,
                company_name="Datos SA",
                position_title="Analista junior",
                start_date=date(2025, 3, 1),
            ),
            CandidateLanguage(candidate_id=ana.candidate_id, language_id=ingles.id, proficiency_level="intermediate"),
            CandidateSkill(candidate_id=ana.candidate_id, skill_id=sql.id),
        ]
    )
    beto = _postulante(db, vacante, "Beto")
    carla = _postulante(db, vacante, "Carla")
    descartado = _postulante(db, vacante, "Dario", estado="rejected")

    # Otra empresa con su propia vacante y postulante.
    usuario_otra, otra = _empresa(db)
    vacante_otra = _vacante(db, otra, usuario_otra)
    ajeno = _postulante(db, vacante_otra, "Eva")
    db.commit()

    return {
        "vacante": vacante,
        "ana": ana,
        "beto": beto,
        "carla": carla,
        "descartado": descartado,
        "ajeno": ajeno,
        "usuario_empresa": usuario_empresa,
        "skill": sql,
        "token": create_access_token(str(usuario_empresa.id), "empresa", {"roles": ["empresa"]}),
        "token_otra": create_access_token(str(usuario_otra.id), "empresa", {"roles": ["empresa"]}),
    }


def _comparar(token: str | None, vacante_id, postulaciones: list):
    encabezados = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post(
        f"/api/seleccion/vacantes/{vacante_id}/comparar",
        json={"postulaciones": [str(p) for p in postulaciones]},
        headers=encabezados,
    )


def test_cp01_compara_perfiles_lado_a_lado(datos, db_session: Session):
    res = _comparar(datos["token"], datos["vacante"].id, [datos["ana"].id, datos["beto"].id])
    assert res.status_code == 200, res.text
    ana, beto = res.json()

    assert ana["candidato_nombre"] == "Ana Prueba"
    assert ana["postulacion_id"] == str(datos["ana"].id)
    # Mismas etiquetas en español que el perfil del egresado.
    assert ana["formacion"][0]["estado_academico"] == "egresado"
    assert ana["idiomas"][0]["nivel"] == "intermedio"
    assert [h["nombre"] for h in ana["habilidades"]] == [datos["skill"].name]
    # La experiencia más reciente primero.
    assert [e["cargo"] for e in ana["experiencia"]] == ["Analista junior", "Pasante de datos"]

    # La afinidad es un porcentaje y quien cumple la habilidad requerida queda arriba.
    assert isinstance(ana["afinidad"], int) and isinstance(beto["afinidad"], int)
    assert ana["afinidad"] > beto["afinidad"]
    assert beto["formacion"] == [] and beto["habilidades"] == []

    registro = (
        db_session.query(AuditLog)
        .filter(AuditLog.user_id == datos["usuario_empresa"].id, AuditLog.action == "comparar_candidatos")
        .first()
    )
    assert registro is not None


def test_cp02_compara_hasta_tres(datos):
    ids = [datos["ana"].id, datos["beto"].id, datos["carla"].id]
    res = _comparar(datos["token"], datos["vacante"].id, ids)
    assert res.status_code == 200, res.text
    assert len(res.json()) == 3


@pytest.mark.parametrize("cantidad", [1, 4])
def test_cp03_rechaza_menos_de_dos_o_mas_de_tres(datos, cantidad):
    ids = [datos["ana"].id, datos["beto"].id, datos["carla"].id, datos["descartado"].id][:cantidad]
    assert _comparar(datos["token"], datos["vacante"].id, ids).status_code == 422


def test_cp04_rechaza_el_mismo_candidato_repetido(datos):
    res = _comparar(datos["token"], datos["vacante"].id, [datos["ana"].id, datos["ana"].id])
    # Las reglas de negocio responden 422 (BusinessException), con un mensaje propio.
    assert res.status_code == 422
    assert "distintos" in res.json()["detail"]


def test_cp05_rechaza_postulaciones_de_otra_vacante(datos):
    res = _comparar(datos["token"], datos["vacante"].id, [datos["ana"].id, datos["ajeno"].id])
    assert res.status_code == 422
    assert "no pertenece" in res.json()["detail"]


def test_cp06_rechaza_candidatos_descartados(datos):
    res = _comparar(datos["token"], datos["vacante"].id, [datos["ana"].id, datos["descartado"].id])
    assert res.status_code == 422
    assert "descartados" in res.json()["detail"]


def test_cp07_empresa_no_compara_en_vacantes_ajenas(datos):
    res = _comparar(datos["token_otra"], datos["vacante"].id, [datos["ana"].id, datos["beto"].id])
    assert res.status_code == 404


def test_cp08_requiere_sesion(datos):
    assert _comparar(None, datos["vacante"].id, [datos["ana"].id, datos["beto"].id]).status_code == 401
