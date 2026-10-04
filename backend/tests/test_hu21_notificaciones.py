import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.main import app
from app.models.candidato import CandidateProfile
from app.models.notificacion import Notification, NotificationPreference
from app.models.usuario import AppUser, Role, UserRole
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
def setup_datos_hu21(db_session: Session):
    """Crea un egresado de prueba con credenciales y preferencias para HU-21."""
    # 1. Asegurar rol candidate
    role_cand = db_session.query(Role).filter_by(name="candidate").first()
    if not role_cand:
        role_cand = Role(name="candidate")
        db_session.add(role_cand)
        db_session.flush()

    # 2. Usuario egresado
    cand_user = AppUser(
        email=f"egresado_notif_{uuid.uuid4().hex[:6]}@uagrm.bo",
        password_hash="fakehash123",
        account_status="active",
    )
    db_session.add(cand_user)
    db_session.flush()

    db_session.add(UserRole(user_id=cand_user.id, role_id=role_cand.id))

    perfil = CandidateProfile(
        user_id=cand_user.id,
        first_name="Jhonny",
        last_name="Duran",
        verification_status="verified",
    )
    db_session.add(perfil)

    # 3. Preferencias de notificación iniciales
    pref = NotificationPreference(
        user_id=cand_user.id,
        email_enabled=True,
        push_enabled=True,
        in_app_enabled=True,
        notify_stage_changes=True,
        notify_job_matches=True,
        notify_interview_events=True,
        notify_messages=True,
    )
    db_session.add(pref)

    # 4. Notificaciones iniciales de prueba (1 no leída, 1 leída)
    notif1 = Notification(
        user_id=cand_user.id,
        notification_type="stage_change",
        title="Avance de Etapa: Desarrollador Python",
        body="¡Felicidades! Has avanzado a la etapa 'Entrevista Técnica' en TECNOVA.",
        link="/vacantes/abc-123",
        read_at=None,
    )
    notif2 = Notification(
        user_id=cand_user.id,
        notification_type="job_match",
        title="Nueva vacante afín publicada",
        body="Se ha publicado una nueva oferta de 'Analista de Sistemas' que coincide 85% con tu perfil.",
        link="/vacantes/xyz-789",
        read_at=datetime.now(timezone.utc),
    )
    db_session.add_all([notif1, notif2])
    db_session.commit()

    token = create_access_token(str(cand_user.id), "candidate", {"roles": ["candidate"]})

    return {
        "user_id": cand_user.id,
        "token": token,
        "notif1_id": notif1.id,
        "notif2_id": notif2.id,
    }


def test_cp01_consultar_historial_y_contador(setup_datos_hu21):
    """CP01/CP04: Consulta el listado de notificaciones y el contador de no leídas."""
    token = setup_datos_hu21["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Contador de no leídas
    res_count = client.get("/api/notificaciones/contador-no-leidas", headers=headers)
    assert res_count.status_code == 200
    assert res_count.json()["no_leidas"] == 1

    # 2. Listado completo
    res_list = client.get("/api/notificaciones", headers=headers)
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["total"] == 2
    assert data["no_leidas"] == 1
    assert len(data["items"]) == 2


def test_cp02_marcar_notificacion_como_leida(setup_datos_hu21):
    """CP02: Marcar una notificación individual como leída."""
    token = setup_datos_hu21["token"]
    notif1_id = setup_datos_hu21["notif1_id"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.patch(f"/api/notificaciones/{notif1_id}/leer", headers=headers)
    assert res.status_code == 200
    assert res.json()["leida"] is True
    assert res.json()["read_at"] is not None

    # Verificar que el contador de no leídas ahora es 0
    res_count = client.get("/api/notificaciones/contador-no-leidas", headers=headers)
    assert res_count.json()["no_leidas"] == 0


def test_cp03_preferencias_notificacion_actualizar_y_consultar(setup_datos_hu21):
    """CP03: Consultar y actualizar las preferencias de notificación."""
    token = setup_datos_hu21["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Consultar preferencias actuales
    res_get = client.get("/api/notificaciones/preferencias", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["notify_job_matches"] is True

    # 2. Desactivar notificaciones de vacantes afines
    update_payload = {"notify_job_matches": False, "email_enabled": False}
    res_put = client.put("/api/notificaciones/preferencias", json=update_payload, headers=headers)
    assert res_put.status_code == 200
    data_put = res_put.json()
    assert data_put["notify_job_matches"] is False
    assert data_put["email_enabled"] is False
    assert data_put["notify_stage_changes"] is True  # Se mantiene intacto


def test_cp04_respeto_de_preferencias_desactivadas(setup_datos_hu21):
    """CP03: Si el egresado tiene desactivadas las notificaciones de vacantes afines, no se crea."""
    token = setup_datos_hu21["token"]
    user_id = setup_datos_hu21["user_id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Desactivar notify_job_matches
    client.put("/api/notificaciones/preferencias", json={"notify_job_matches": False}, headers=headers)

    # Intentar emitir notificación de tipo job_match
    payload = {
        "user_id": str(user_id),
        "notification_type": "job_match",
        "title": "Oferta Recomendada",
        "body": "Ingeniero Cloud en Banco Mercantil",
    }
    res = client.post("/api/notificaciones", json=payload, headers=headers)
    assert res.status_code == 201
    assert res.json() is None  # Rechazada silenciosamente por preferencia


def test_cp05_marcar_todas_leidas_y_eliminar(setup_datos_hu21):
    """CP05: Marcar todas como leídas y eliminar una notificación del historial."""
    token = setup_datos_hu21["token"]
    notif2_id = setup_datos_hu21["notif2_id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Marcar todas leídas
    res_all = client.post("/api/notificaciones/marcar-todas-leidas", headers=headers)
    assert res_all.status_code == 200

    # Eliminar notif2
    res_del = client.delete(f"/api/notificaciones/{notif2_id}", headers=headers)
    assert res_del.status_code == 200
    assert res_del.json()["eliminado"] is True

    # Verificar que el total disminuyó
    res_list = client.get("/api/notificaciones", headers=headers)
    assert res_list.json()["total"] == 1
