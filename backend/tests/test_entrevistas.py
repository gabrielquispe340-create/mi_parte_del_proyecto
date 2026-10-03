import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.main import app
from app.models.candidato import CandidateProfile
from app.models.empresa import Company, CompanyMember
from app.models.entrevista import Interview
from app.models.notificacion import Notification
from app.models.postulacion import Application
from app.models.usuario import AppUser, Role, UserRole
from app.models.vacante import JobPosting, JobSelectionStage
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
def setup_datos(db_session: Session):
    """Crea los datos base (empresa, candidato, vacante con etapas, postulación) para pruebas."""
    # 1. Asegurar roles
    for r_name in ("empresa", "candidate", "platform_admin", "moderator"):
        if not db_session.query(Role).filter_by(name=r_name).first():
            db_session.add(Role(name=r_name))
    db_session.commit()

    # 2. Usuario y miembro de empresa
    empresa_user = AppUser(
        email=f"empresa_{uuid.uuid4().hex[:6]}@test.bo",
        password_hash="fakehash",
        account_status="active",
    )
    db_session.add(empresa_user)
    db_session.flush()

    role_emp = db_session.query(Role).filter_by(name="empresa").first()
    db_session.add(UserRole(user_id=empresa_user.id, role_id=role_emp.id))

    company = Company(
        legal_name="Empresa Test SRL",
        tax_id=f"NIT-{uuid.uuid4().hex[:8]}",
        verification_status="verified",
        account_status="active",
    )
    db_session.add(company)
    db_session.flush()

    member = CompanyMember(
        user_id=empresa_user.id,
        company_id=company.id,
        member_type="recruiter",
        is_active=True,
    )
    db_session.add(member)

    # 3. Usuario y perfil de candidato
    cand_user = AppUser(
        email=f"candidato_{uuid.uuid4().hex[:6]}@test.bo",
        password_hash="fakehash",
        account_status="active",
    )
    db_session.add(cand_user)
    db_session.flush()

    role_cand = db_session.query(Role).filter_by(name="candidate").first()
    db_session.add(UserRole(user_id=cand_user.id, role_id=role_cand.id))

    candidate = CandidateProfile(
        user_id=cand_user.id,
        first_name="Juan",
        last_name="Perez",
        verification_status="verified",
    )
    db_session.add(candidate)
    db_session.flush()

    # 4. Vacante con etapas de selección
    vacante = JobPosting(
        company_id=company.id,
        title="Desarrollador Fullstack",
        description="Vacante de prueba",
        seniority_level="junior",
        employment_type="permanent",
        work_modality="remote",
        city="Santa Cruz",
        status="published",
        created_by=empresa_user.id,
    )
    db_session.add(vacante)
    db_session.flush()

    etapa_revision = JobSelectionStage(
        job_posting_id=vacante.id,
        stage_number=1,
        name="Revisión de CV",
        is_terminal=False,
    )
    etapa_entrevista = JobSelectionStage(
        job_posting_id=vacante.id,
        stage_number=2,
        name="Entrevista Técnica",
        is_terminal=False,
    )
    etapa_oferta = JobSelectionStage(
        job_posting_id=vacante.id,
        stage_number=3,
        name="Oferta y Contratación",
        is_terminal=True,
    )
    db_session.add_all([etapa_revision, etapa_entrevista, etapa_oferta])
    db_session.flush()

    # 5. Postulación inicial en etapa de revisión
    app_post = Application(
        candidate_id=candidate.id,
        job_id=vacante.id,
        current_stage_id=etapa_revision.id,
        current_status="screening",
    )
    db_session.add(app_post)
    db_session.commit()

    token_empresa = create_access_token(str(empresa_user.id), "empresa", {"roles": ["empresa"]})
    token_candidato = create_access_token(str(cand_user.id), "candidate", {"roles": ["candidate"]})

    return {
        "empresa_user": empresa_user,
        "cand_user": cand_user,
        "company": company,
        "candidate": candidate,
        "vacante": vacante,
        "etapa_revision": etapa_revision,
        "etapa_entrevista": etapa_entrevista,
        "app_post": app_post,
        "token_empresa": token_empresa,
        "token_candidato": token_candidato,
    }


def test_cp01_proponer_entrevista(setup_datos, db_session: Session):
    """CP01: Empresa propone fecha/hora/modalidad -> status pending_confirmation + notifica candidato."""
    app_id = setup_datos["app_post"].id
    token_empresa = setup_datos["token_empresa"]
    cand_user_id = setup_datos["cand_user"].id

    fecha_inicio = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    fecha_fin = (datetime.now(timezone.utc) + timedelta(days=2, hours=1)).isoformat()

    payload = {
        "scheduled_start": fecha_inicio,
        "scheduled_end": fecha_fin,
        "modality": "virtual",
        "meeting_url": "https://meet.google.com/abc-defg-hij",
        "notes": "Favor tener a mano su portafolio.",
    }

    res = client.post(
        f"/api/seleccion/postulaciones/{app_id}/entrevistas",
        json=payload,
        headers={"Authorization": f"Bearer {token_empresa}"},
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["status"] == "pending_confirmation"
    assert data["modality"] == "virtual"
    assert data["meeting_url"] == "https://meet.google.com/abc-defg-hij"
    assert data["rejection_count"] == 0
    assert data["requires_manual_review"] is False

    # Verificar que se generó la notificación al candidato
    notif = (
        db_session.query(Notification)
        .filter(Notification.user_id == cand_user_id, Notification.notification_type == "interview_proposal")
        .first()
    )
    assert notif is not None
    assert "Propuesta de entrevista" in notif.title


def test_cp02_candidato_confirma(setup_datos, db_session: Session):
    """CP02: Propuesta pendiente + candidato confirma -> status confirmed + notifica empresa."""
    app_id = setup_datos["app_post"].id
    token_empresa = setup_datos["token_empresa"]
    token_candidato = setup_datos["token_candidato"]
    empresa_user_id = setup_datos["empresa_user"].id

    # 1. Crear propuesta
    res_prop = client.post(
        f"/api/seleccion/postulaciones/{app_id}/entrevistas",
        json={
            "scheduled_start": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "modality": "onsite",
            "location": "Piso 4, Oficina 402",
        },
        headers={"Authorization": f"Bearer {token_empresa}"},
    )
    assert res_prop.status_code == 201
    entrevista_id = res_prop.json()["id"]

    # 2. Candidato confirma
    res_conf = client.post(
        f"/api/postulaciones/entrevistas/{entrevista_id}/confirmar",
        headers={"Authorization": f"Bearer {token_candidato}"},
    )
    assert res_conf.status_code == 200, res_conf.text
    data = res_conf.json()
    assert data["status"] == "confirmed"

    # 3. Notificación a empresa
    notif = (
        db_session.query(Notification)
        .filter(Notification.user_id == empresa_user_id, Notification.notification_type == "interview_confirmed")
        .first()
    )
    assert notif is not None
    assert "confirmada" in notif.title.lower()


def test_cp03_candidato_rechaza_permite_reprogramar(setup_datos, db_session: Session):
    """CP03: Candidato rechaza propuesta -> empresa puede reprogramar."""
    app_id = setup_datos["app_post"].id
    token_empresa = setup_datos["token_empresa"]
    token_candidato = setup_datos["token_candidato"]

    # 1. Proponer
    res_prop = client.post(
        f"/api/seleccion/postulaciones/{app_id}/entrevistas",
        json={
            "scheduled_start": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "modality": "virtual",
            "meeting_url": "https://meet.google.com/test",
        },
        headers={"Authorization": f"Bearer {token_empresa}"},
    )
    entrevista_id = res_prop.json()["id"]

    # 2. Candidato rechaza
    res_rech = client.post(
        f"/api/postulaciones/entrevistas/{entrevista_id}/rechazar",
        json={"motivo": "Cruce de horario con examen de grado."},
        headers={"Authorization": f"Bearer {token_candidato}"},
    )
    assert res_rech.status_code == 200
    data_rech = res_rech.json()
    assert data_rech["status"] == "rejected"
    assert data_rech["candidate_feedback"] == "Cruce de horario con examen de grado."
    assert data_rech["rejection_count"] == 1
    assert data_rech["requires_manual_review"] is False

    # 3. Empresa reprograma en la MISMA fila
    nueva_fecha = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    res_reprog = client.put(
        f"/api/seleccion/entrevistas/{entrevista_id}/reprogramar",
        json={
            "scheduled_start": nueva_fecha,
            "modality": "virtual",
            "meeting_url": "https://meet.google.com/test-nuevo",
            "notes": "Nuevo horario propuesto.",
        },
        headers={"Authorization": f"Bearer {token_empresa}"},
    )
    assert res_reprog.status_code == 200
    data_reprog = res_reprog.json()
    assert data_reprog["id"] == entrevista_id
    assert data_reprog["status"] == "pending_confirmation"
    assert data_reprog["rejection_count"] == 1  # Conserva conteo


def test_cp03_reprogramar_bloqueado_tras_3_rechazos(setup_datos, db_session: Session):
    """Regla de 3 rechazos: al llegar a 3 se activa requires_manual_review y bloquea reprogramación (409)."""
    app_id = setup_datos["app_post"].id
    token_empresa = setup_datos["token_empresa"]
    token_candidato = setup_datos["token_candidato"]

    # 1. Proponer inicial
    res_prop = client.post(
        f"/api/seleccion/postulaciones/{app_id}/entrevistas",
        json={
            "scheduled_start": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "modality": "virtual",
            "meeting_url": "https://meet.google.com/test",
        },
        headers={"Authorization": f"Bearer {token_empresa}"},
    )
    entrevista_id = res_prop.json()["id"]

    # Ciclo de 3 rechazos consecutivos
    for i in range(1, 4):
        # Rechazo candidato
        res_r = client.post(
            f"/api/postulaciones/entrevistas/{entrevista_id}/rechazar",
            json={"motivo": f"Rechazo número {i}"},
            headers={"Authorization": f"Bearer {token_candidato}"},
        )
        assert res_r.status_code == 200
        if i < 3:
            # Reprogramar permitido
            res_rep = client.put(
                f"/api/seleccion/entrevistas/{entrevista_id}/reprogramar",
                json={
                    "scheduled_start": (datetime.now(timezone.utc) + timedelta(days=i + 2)).isoformat(),
                    "modality": "virtual",
                    "meeting_url": "https://meet.google.com/test",
                },
                headers={"Authorization": f"Bearer {token_empresa}"},
            )
            assert res_rep.status_code == 200

    # Tras el 3er rechazo, la entrevista debe estar marcada para revisión manual
    db_ent = db_session.query(Interview).filter_by(id=uuid.UUID(entrevista_id)).first()
    assert db_ent.rejection_count == 3
    assert db_ent.requires_manual_review is True

    # Intentar reprogramar debe fallar con 409 Conflict
    res_bloqueado = client.put(
        f"/api/seleccion/entrevistas/{entrevista_id}/reprogramar",
        json={
            "scheduled_start": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
            "modality": "virtual",
            "meeting_url": "https://meet.google.com/test",
        },
        headers={"Authorization": f"Bearer {token_empresa}"},
    )
    assert res_bloqueado.status_code == 409
    assert "revisión manual" in res_bloqueado.json()["detail"].lower()

    # Reclutador desbloquea manualmente (/revisar)
    res_rev = client.post(
        f"/api/seleccion/entrevistas/{entrevista_id}/revisar",
        json={"aprobado": True},
        headers={"Authorization": f"Bearer {token_empresa}"},
    )
    assert res_rev.status_code == 200
    assert res_rev.json()["requires_manual_review"] is False

    # Ahora sí permite reprogramar
    res_desbloq = client.put(
        f"/api/seleccion/entrevistas/{entrevista_id}/reprogramar",
        json={
            "scheduled_start": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
            "modality": "virtual",
            "meeting_url": "https://meet.google.com/test",
        },
        headers={"Authorization": f"Bearer {token_empresa}"},
    )
    assert res_desbloq.status_code == 200
    assert res_desbloq.json()["status"] == "pending_confirmation"


def test_cp04_empresa_cancela_notifica_ambas_partes(setup_datos, db_session: Session):
    """CP04: Empresa cancela entrevista -> status cancelled + notificación a ambas partes."""
    app_id = setup_datos["app_post"].id
    token_empresa = setup_datos["token_empresa"]
    empresa_user_id = setup_datos["empresa_user"].id
    cand_user_id = setup_datos["cand_user"].id

    res_prop = client.post(
        f"/api/seleccion/postulaciones/{app_id}/entrevistas",
        json={
            "scheduled_start": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "modality": "onsite",
            "location": "Oficina Central",
        },
        headers={"Authorization": f"Bearer {token_empresa}"},
    )
    entrevista_id = res_prop.json()["id"]

    res_canc = client.post(
        f"/api/seleccion/entrevistas/{entrevista_id}/cancelar",
        headers={"Authorization": f"Bearer {token_empresa}"},
    )
    assert res_canc.status_code == 200
    assert res_canc.json()["status"] == "cancelled"

    # Notificación al candidato
    notif_cand = (
        db_session.query(Notification)
        .filter(Notification.user_id == cand_user_id, Notification.notification_type == "interview_cancelled")
        .first()
    )
    assert notif_cand is not None

    # Notificación a la empresa
    notif_emp = (
        db_session.query(Notification)
        .filter(Notification.user_id == empresa_user_id, Notification.notification_type == "interview_cancelled")
        .first()
    )
    assert notif_emp is not None


def test_kanban_auto_sync_al_confirmar(setup_datos, db_session: Session):
    """Decisión 5: Al confirmar, la postulación se mueve automáticamente a la etapa 'Entrevista'."""
    app_post = setup_datos["app_post"]
    token_empresa = setup_datos["token_empresa"]
    token_candidato = setup_datos["token_candidato"]
    etapa_entrevista = setup_datos["etapa_entrevista"]

    # Inicialmente está en etapa_revision ("Revisión de CV") y status "screening"
    assert app_post.current_status == "screening"
    assert app_post.current_stage_id != etapa_entrevista.id

    # 1. Proponer
    res_prop = client.post(
        f"/api/seleccion/postulaciones/{app_post.id}/entrevistas",
        json={
            "scheduled_start": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "modality": "virtual",
            "meeting_url": "https://meet.google.com/test",
        },
        headers={"Authorization": f"Bearer {token_empresa}"},
    )
    entrevista_id = res_prop.json()["id"]

    # 2. Confirmar
    res_conf = client.post(
        f"/api/postulaciones/entrevistas/{entrevista_id}/confirmar",
        headers={"Authorization": f"Bearer {token_candidato}"},
    )
    assert res_conf.status_code == 200

    # 3. Verificar que en BD la postulación avanzó automáticamente
    db_session.expire_all()
    app_actualizada = db_session.query(Application).filter_by(id=app_post.id).first()
    assert app_actualizada.current_stage_id == etapa_entrevista.id
    assert app_actualizada.current_status == "interview"
