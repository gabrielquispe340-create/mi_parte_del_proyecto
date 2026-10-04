"""HU-21: las preferencias de alertas se aplican a los avisos reales (mensajes,
entrevistas, etapas) y los tokens push solo los maneja su dueño."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.features.notificaciones.emisor import emitir_notificacion
from app.main import app
from app.models.candidato import CandidateProfile
from app.models.empresa import Company, CompanyMember
from app.models.notificacion import Notification, NotificationPreference, UserDeviceToken
from app.models.postulacion import Application
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


def _usuario(db: Session, prefijo: str, rol: str) -> AppUser:
    if not db.query(Role).filter_by(name=rol).first():
        db.add(Role(name=rol))
        db.flush()
    usuario = AppUser(email=f"{prefijo}_{uuid.uuid4().hex[:8]}@test.bo", password_hash="x", account_status="active")
    db.add(usuario)
    db.flush()
    db.add(UserRole(user_id=usuario.id, role_id=db.query(Role).filter_by(name=rol).first().id))
    return usuario


def _auth(usuario: AppUser, rol: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(usuario.id), rol, {'roles': [rol]})}"}


@pytest.fixture
def datos(db_session: Session):
    db = db_session
    reclutador = _usuario(db, "rrhh", "empresa")
    empresa = Company(
        legal_name=f"Empresa HU21 {uuid.uuid4().hex[:4]}",
        tax_id=f"NIT-{uuid.uuid4().hex[:8]}",
        verification_status="verified",
        account_status="active",
    )
    db.add(empresa)
    db.flush()
    db.add(CompanyMember(user_id=reclutador.id, company_id=empresa.id, member_type="recruiter", is_active=True))
    vacante = JobPosting(
        company_id=empresa.id,
        title="Analista HU21",
        description="Vacante de prueba",
        seniority_level="junior",
        employment_type="permanent",
        work_modality="onsite",
        city="Santa Cruz",
        status="published",
        created_by=reclutador.id,
    )
    db.add(vacante)
    db.flush()
    egresado = _usuario(db, "cand", "candidate")
    perfil = CandidateProfile(user_id=egresado.id, first_name="Rosa", last_name="Prueba", verification_status="verified")
    db.add(perfil)
    db.flush()
    postulacion = Application(candidate_id=perfil.id, job_id=vacante.id, current_status="screening")
    db.add(postulacion)
    db.commit()
    return {"reclutador": reclutador, "egresado": egresado, "postulacion": postulacion}


def _avisos(db: Session, usuario: AppUser, tipo: str) -> int:
    db.expire_all()
    return db.query(Notification).filter_by(user_id=usuario.id, notification_type=tipo).count()


def _escribir(datos: dict, texto: str):
    res = client.post(
        f"/api/comunicacion/postulaciones/{datos['postulacion'].id}/mensajes",
        data={"contenido": texto},
        headers=_auth(datos["reclutador"], "empresa"),
    )
    assert res.status_code == 201, res.text


def test_mensajes_silenciados_no_generan_aviso_pero_se_envian(datos, db_session):
    egresado = datos["egresado"]
    client.put("/api/notificaciones/preferencias", json={"notify_messages": False}, headers=_auth(egresado, "candidate"))

    _escribir(datos, "¿Podés venir el lunes?")
    assert _avisos(db_session, egresado, "new_message") == 0

    client.put("/api/notificaciones/preferencias", json={"notify_messages": True}, headers=_auth(egresado, "candidate"))
    _escribir(datos, "Te esperamos a las 10.")
    assert _avisos(db_session, egresado, "new_message") == 1


def test_sin_avisos_en_la_app_no_se_crea_ninguno(datos, db_session):
    egresado = datos["egresado"]
    client.put("/api/notificaciones/preferencias", json={"in_app_enabled": False}, headers=_auth(egresado, "candidate"))

    _escribir(datos, "Hola")
    assert _avisos(db_session, egresado, "new_message") == 0


@pytest.mark.parametrize(
    "campo, tipo",
    [
        ("notify_interview_events", "interview_proposal"),
        ("notify_interview_events", "interview_cancelled"),
        ("notify_stage_changes", "application_status"),
        ("notify_messages", "new_message"),
        ("notify_job_matches", "job_match"),
    ],
)
def test_cada_preferencia_silencia_sus_tipos(datos, db_session, campo, tipo):
    egresado = datos["egresado"]
    db_session.add(NotificationPreference(user_id=egresado.id, **{campo: False}))
    db_session.commit()

    assert emitir_notificacion(db_session, egresado.id, tipo, "Aviso de prueba") is None
    # Un tipo que no depende de ninguna preferencia sigue llegando.
    assert emitir_notificacion(db_session, egresado.id, "account_notice", "Aviso general") is not None
    db_session.rollback()


def test_sin_preferencias_guardadas_llega_todo(datos, db_session):
    assert emitir_notificacion(db_session, datos["egresado"].id, "interview_proposal", "Entrevista") is not None
    db_session.rollback()


def test_un_usuario_no_puede_desactivar_el_token_push_de_otro(datos, db_session):
    egresado, reclutador = datos["egresado"], datos["reclutador"]
    token_fcm = f"token-{uuid.uuid4().hex}"
    res = client.post(
        "/api/notificaciones/fcm/registrar-token",
        json={"fcm_token": token_fcm, "device_type": "android"},
        headers=_auth(egresado, "candidate"),
    )
    assert res.status_code == 200, res.text

    ajeno = client.post("/api/notificaciones/fcm/eliminar-token", json={"fcm_token": token_fcm}, headers=_auth(reclutador, "empresa"))
    assert ajeno.json() == {"desactivado": False}
    db_session.expire_all()
    assert db_session.query(UserDeviceToken).filter_by(fcm_token=token_fcm).one().is_active is True

    propio = client.post("/api/notificaciones/fcm/eliminar-token", json={"fcm_token": token_fcm}, headers=_auth(egresado, "candidate"))
    assert propio.json() == {"desactivado": True}
