import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.main import app
from app.models.candidato import CandidateEducation, CandidateProfile, CandidateSkill
from app.models.catalogo import FieldOfStudy, Skill
from app.models.empresa import Company, CompanyMember
from app.models.postulacion import Application
from app.models.usuario import AppUser, Role, UserRole
from app.models.vacante import JobEducationPreference, JobPosting, JobSkill
from app.security.jwt_provider import create_access_token

client = TestClient(app)


@pytest.fixture
def db_session():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def setup_datos_hu24(db_session: Session):
    """Crea una empresa con una vacante y 2 postulantes con diferentes niveles de afinidad."""
    # 1. Asegurar roles
    for r_name in ("empresa", "candidate", "platform_admin"):
        if not db_session.query(Role).filter_by(name=r_name).first():
            db_session.add(Role(name=r_name))
    db_session.commit()

    # 2. Catálogo: Carrera y Habilidades
    carrera_sistemas = db_session.query(FieldOfStudy).filter_by(name="Ingeniería en Sistemas").first()
    if not carrera_sistemas:
        carrera_sistemas = FieldOfStudy(name="Ingeniería en Sistemas", category="Tecnología")
        db_session.add(carrera_sistemas)
        db_session.flush()

    skill_python = db_session.query(Skill).filter_by(name="Python").first()
    if not skill_python:
        skill_python = Skill(name="Python", category="Backend")
        db_session.add(skill_python)
        db_session.flush()

    skill_sql = db_session.query(Skill).filter_by(name="SQL").first()
    if not skill_sql:
        skill_sql = Skill(name="SQL", category="Bases de Datos")
        db_session.add(skill_sql)
        db_session.flush()

    # 3. Empresa y reclutador
    empresa_user = AppUser(
        email=f"empresa_hu24_{uuid.uuid4().hex[:6]}@tech.bo",
        password_hash="fakehash",
        account_status="active",
    )
    db_session.add(empresa_user)
    db_session.flush()

    role_emp = db_session.query(Role).filter_by(name="empresa").first()
    db_session.add(UserRole(user_id=empresa_user.id, role_id=role_emp.id))

    company = Company(
        legal_name="Software Hub SRL",
        trade_name="Software Hub",
        tax_id=f"NIT-{uuid.uuid4().hex[:8]}",
        verification_status="verified",
        account_status="active",
    )
    db_session.add(company)
    db_session.flush()

    db_session.add(
        CompanyMember(
            user_id=empresa_user.id,
            company_id=company.id,
            member_type="owner",
            is_active=True,
        )
    )

    # 4. Vacante que pide Python, SQL y carrera de Sistemas
    vacante = JobPosting(
        company_id=company.id,
        title="Desarrollador Backend Python HU24",
        description="Buscamos desarrollador con Python y bases de datos relacionales",
        seniority_level="junior",
        employment_type="permanent",
        work_modality="remote",
        city="Santa Cruz",
        status="published",
        created_by=empresa_user.id,
    )
    db_session.add(vacante)
    db_session.flush()

    db_session.add(JobEducationPreference(job_posting_id=vacante.id, field_of_study_id=carrera_sistemas.id))
    db_session.add(JobSkill(job_posting_id=vacante.id, skill_id=skill_python.id, min_proficiency="intermediate", weight=3))
    db_session.add(JobSkill(job_posting_id=vacante.id, skill_id=skill_sql.id, min_proficiency="intermediate", weight=2))

    # 5. Candidato 1: Alta Afinidad (Tiene carrera Sistemas, Python y SQL)
    u1 = AppUser(email=f"cand_alto_{uuid.uuid4().hex[:6]}@uagrm.bo", password_hash="hash", account_status="active")
    db_session.add(u1)
    db_session.flush()
    c1 = CandidateProfile(user_id=u1.id, first_name="Ana", last_name="Gutiérrez", professional_headline="Ingeniera de Software")
    db_session.add(c1)
    db_session.flush()
    db_session.add(CandidateEducation(candidate_id=c1.id, field_of_study_id=carrera_sistemas.id, program_name="Ingeniería en Sistemas", academic_status="graduated"))
    db_session.add(CandidateSkill(candidate_id=c1.id, skill_id=skill_python.id, proficiency_level="advanced"))
    db_session.add(CandidateSkill(candidate_id=c1.id, skill_id=skill_sql.id, proficiency_level="intermediate"))

    app1 = Application(candidate_id=c1.id, job_id=vacante.id, current_status="applied")
    db_session.add(app1)

    # 6. Candidato 2: Baja/Media Afinidad (Solo tiene SQL)
    u2 = AppUser(email=f"cand_bajo_{uuid.uuid4().hex[:6]}@uagrm.bo", password_hash="hash", account_status="active")
    db_session.add(u2)
    db_session.flush()
    c2 = CandidateProfile(user_id=u2.id, first_name="Pedro", last_name="Vaca", professional_headline="Egresado")
    db_session.add(c2)
    db_session.flush()
    db_session.add(CandidateSkill(candidate_id=c2.id, skill_id=skill_sql.id, proficiency_level="basic"))

    app2 = Application(candidate_id=c2.id, job_id=vacante.id, current_status="applied")
    db_session.add(app2)

    db_session.commit()

    token_empresa = create_access_token(str(empresa_user.id), "empresa", {"roles": ["empresa"]})
    token_candidato = create_access_token(str(u1.id), "candidate", {"roles": ["candidate"]})

    return {
        "vacante_id": vacante.id,
        "token_empresa": token_empresa,
        "token_candidato": token_candidato,
        "cand1_id": c1.id,
        "cand2_id": c2.id,
    }


def test_cp01_sugerencia_candidatos_ranking_afinidad(setup_datos_hu24):
    """CP01: Solicita el ranking sugerido de candidatos y valida orden descendente."""
    vacante_id = setup_datos_hu24["vacante_id"]
    token = setup_datos_hu24["token_empresa"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get(f"/api/ia/sugerencias-candidatos/{vacante_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_postulantes"] == 2
    assert len(data["items"]) == 2

    # El primer candidato debe tener mayor o igual afinidad que el segundo
    c1 = data["items"][0]
    c2 = data["items"][1]
    assert c1["afinidad_porcentaje"] >= c2["afinidad_porcentaje"]
    assert c1["first_name"] == "Ana"


def test_cp02_filtro_umbral_minimo_70_porciento(setup_datos_hu24):
    """CP02: Al aplicar umbral_minimo=70, solo se retornan candidatos con afinidad >= 70."""
    vacante_id = setup_datos_hu24["vacante_id"]
    token = setup_datos_hu24["token_empresa"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get(f"/api/ia/sugerencias-candidatos/{vacante_id}?umbral_minimo=70", headers=headers)
    assert res.status_code == 200
    data = res.json()
    for item in data["items"]:
        assert item["afinidad_porcentaje"] >= 70


def test_cp03_explicabilidad_criterios_coincidentes(setup_datos_hu24):
    """CP03: Valida que se presenten las razones transparentes de la coincidencia (RNF-20)."""
    vacante_id = setup_datos_hu24["vacante_id"]
    token = setup_datos_hu24["token_empresa"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get(f"/api/ia/sugerencias-candidatos/{vacante_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    candidato_ana = next(c for c in data["items"] if c["first_name"] == "Ana")
    assert len(candidato_ana["razones_principales"]) > 0
    assert any("Python" in r or "Habilidades" in r or "Carrera" in r for r in candidato_ana["razones_principales"])


def test_cp04_solo_empresa_o_admin_acceso(setup_datos_hu24):
    """CP04: Un candidato no tiene permiso para consultar las sugerencias de la empresa."""
    vacante_id = setup_datos_hu24["vacante_id"]
    token_cand = setup_datos_hu24["token_candidato"]
    headers = {"Authorization": f"Bearer {token_cand}"}

    res = client.get(f"/api/ia/sugerencias-candidatos/{vacante_id}", headers=headers)
    assert res.status_code in (401, 403)
