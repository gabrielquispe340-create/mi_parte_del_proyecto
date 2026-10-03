import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.main import app
from app.models.candidato import CandidateProfile
from app.models.empresa import Company, CompanyMember
from app.models.usuario import AppUser, Role, UserRole
from app.models.vacante import JobPosting
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
def setup_datos_hu34(db_session: Session):
    """Crea los datos de prueba para verificar acceso público, estadísticas y visibilidad de contacto (HU-34)."""
    # 1. Asegurar roles
    for r_name in ("empresa", "candidate", "platform_admin", "moderator"):
        if not db_session.query(Role).filter_by(name=r_name).first():
            db_session.add(Role(name=r_name))
    db_session.commit()

    # 2. Usuario empresa y empresa verificada con datos de contacto privados
    empresa_user = AppUser(
        email=f"empresa_hu34_{uuid.uuid4().hex[:6]}@test.bo",
        password_hash="fakehash",
        account_status="active",
    )
    db_session.add(empresa_user)
    db_session.flush()

    role_emp = db_session.query(Role).filter_by(name="empresa").first()
    db_session.add(UserRole(user_id=empresa_user.id, role_id=role_emp.id))

    company = Company(
        legal_name="Empresa Pública Demo SRL",
        trade_name="Demo Corp",
        tax_id=f"NIT-{uuid.uuid4().hex[:8]}",
        contact_email="rrhh.privado@democorp.bo",
        phone="+591-78901234",
        address="Av. Bush, Edificio Central Piso 4",
        city="Santa Cruz",
        verification_status="verified",
        account_status="active",
    )
    db_session.add(company)
    db_session.flush()

    member = CompanyMember(
        user_id=empresa_user.id,
        company_id=company.id,
        member_type="owner",
        job_title="Gerente",
        is_active=True,
    )
    db_session.add(member)

    # 3. Usuario egresado/candidato
    cand_user = AppUser(
        email=f"candidato_hu34_{uuid.uuid4().hex[:6]}@test.bo",
        password_hash="fakehash",
        account_status="active",
    )
    db_session.add(cand_user)
    db_session.flush()

    role_cand = db_session.query(Role).filter_by(name="candidate").first()
    db_session.add(UserRole(user_id=cand_user.id, role_id=role_cand.id))

    candidate = CandidateProfile(
        user_id=cand_user.id,
        first_name="Carlos",
        last_name="Mendoza",
        verification_status="verified",
    )
    db_session.add(candidate)
    db_session.flush()

    # 4. Vacante publicada y activa
    vacante = JobPosting(
        company_id=company.id,
        title="Ingeniero de Software Junior HU34",
        description="Puesto público de prueba para egresados",
        seniority_level="junior",
        employment_type="permanent",
        work_modality="remote",
        city="Santa Cruz",
        status="published",
        created_by=empresa_user.id,
    )
    db_session.add(vacante)
    db_session.commit()

    token_candidato = create_access_token(str(cand_user.id), "candidate", {"roles": ["candidate"]})

    return {
        "company": company,
        "vacante": vacante,
        "token_candidato": token_candidato,
    }


def test_cp01_visitante_lista_vacantes_sin_auth(setup_datos_hu34):
    """CP01: Un usuario sin sesión accede al listado público y ve vacantes activas sin token."""
    response = client.get("/api/vacantes/buscar")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    # Verifica que al menos la vacante creada esté en los resultados
    titulos = [v["title"] for v in data["items"]]
    assert any("HU34" in t for t in titulos)


def test_cp02_visitante_obtiene_estadisticas_con_cache():
    """CP02: Un usuario sin sesión consulta estadísticas públicas agregadas y se verifica caché."""
    resp1 = client.get("/api/vacantes/estadisticas-publicas")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert "total_vacantes_activas" in data1
    assert "total_empresas_registradas" in data1
    assert "fecha_actualizacion" in data1
    assert data1["total_vacantes_activas"] >= 1
    assert data1["total_empresas_registradas"] >= 1

    # Segunda llamada inmediata: debe devolver exactamente la misma fecha_actualizacion (hit de caché)
    resp2 = client.get("/api/vacantes/estadisticas-publicas")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["fecha_actualizacion"] == data1["fecha_actualizacion"]
    assert data2["total_vacantes_activas"] == data1["total_vacantes_activas"]


def test_cp03_visitante_no_puede_postular_sin_token(setup_datos_hu34):
    """CP03: Un visitante sin cuenta no puede enviar postulaciones (retorna 401 Unauthorized)."""
    vacante_id = str(setup_datos_hu34["vacante"].id)
    response = client.post(
        "/api/postulaciones/",
        json={"vacante_id": vacante_id, "respuestas": []},
    )
    assert response.status_code == 401


def test_cp04_visitante_no_ve_contacto_empresa_en_detalle(setup_datos_hu34):
    """CP04: Un visitante consulta el detalle de la vacante y el sistema oculta datos de contacto."""
    vacante_id = str(setup_datos_hu34["vacante"].id)
    response = client.get(f"/api/vacantes/buscar/{vacante_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == vacante_id
    # Los datos de contacto deben ser estrictamente None para visitantes
    assert data.get("company_contact_email") is None
    assert data.get("company_phone") is None
    assert data.get("company_address") is None


def test_cp04_con_token_si_ve_contacto(setup_datos_hu34):
    """CP04: Un usuario autenticado con sesión sí puede visualizar la información de contacto."""
    vacante_id = str(setup_datos_hu34["vacante"].id)
    token = setup_datos_hu34["token_candidato"]
    response = client.get(
        f"/api/vacantes/buscar/{vacante_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == vacante_id
    assert data.get("company_contact_email") == "rrhh.privado@democorp.bo"
    assert data.get("company_phone") == "+591-78901234"
    assert data.get("company_address") == "Av. Bush, Edificio Central Piso 4"
