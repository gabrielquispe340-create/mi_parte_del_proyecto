"""HU-19: mensajería interna entre la empresa y el candidato de una postulación."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.main import app
from app.models.candidato import CandidateEducation, CandidateProfile
from app.models.comunicacion import Conversation, ConversationMember
from app.models.empresa import Company, CompanyMember
from app.models.notificacion import Notification
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


def _empresa(db: Session, miembros: int = 1) -> tuple[list[AppUser], Company]:
    empresa = Company(
        legal_name=f"Empresa HU19 {uuid.uuid4().hex[:4]}",
        tax_id=f"NIT-{uuid.uuid4().hex[:8]}",
        verification_status="verified",
        account_status="active",
    )
    db.add(empresa)
    db.flush()
    usuarios = []
    for _ in range(miembros):
        usuario = _usuario(db, "rrhh", "empresa")
        db.add(CompanyMember(user_id=usuario.id, company_id=empresa.id, member_type="recruiter", is_active=True))
        usuarios.append(usuario)
    return usuarios, empresa


def _candidato(db: Session, nombre: str) -> tuple[AppUser, CandidateProfile]:
    usuario = _usuario(db, "cand", "candidate")
    perfil = CandidateProfile(user_id=usuario.id, first_name=nombre, last_name="Prueba", verification_status="verified")
    db.add(perfil)
    db.flush()
    return usuario, perfil


def _token(usuario: AppUser, rol: str) -> str:
    return create_access_token(str(usuario.id), rol, {"roles": [rol]})


@pytest.fixture
def datos(db_session: Session):
    db = db_session
    reclutadores, empresa = _empresa(db, miembros=2)
    vacante = JobPosting(
        company_id=empresa.id,
        title="Soporte técnico",
        description="Vacante de prueba HU-19",
        seniority_level="junior",
        employment_type="permanent",
        work_modality="onsite",
        city="Santa Cruz",
        status="published",
        created_by=reclutadores[0].id,
    )
    db.add(vacante)
    db.flush()

    usuario_cand, candidato = _candidato(db, "Lucia")
    # Formación cargada a mano, sin carrera del catálogo (antes rompía el hilo con degree_title).
    db.add(
        CandidateEducation(
            candidate_id=candidato.id,
            institution_name="UAGRM",
            program_name="Ingeniería Informática",
            academic_status="graduated",
        )
    )
    postulacion = Application(candidate_id=candidato.id, job_id=vacante.id, current_status="screening")
    db.add(postulacion)

    usuario_ajeno, _ = _candidato(db, "Tercero")
    otros_reclutadores, _ = _empresa(db)
    db.commit()

    return {
        "postulacion": postulacion,
        "usuario_cand": usuario_cand,
        "reclutadores": reclutadores,
        "token_empresa": _token(reclutadores[0], "empresa"),
        "token_cand": _token(usuario_cand, "candidate"),
        "token_ajeno": _token(usuario_ajeno, "candidate"),
        "token_otra_empresa": _token(otros_reclutadores[0], "empresa"),
    }


def _url(postulacion_id) -> str:
    return f"/api/comunicacion/postulaciones/{postulacion_id}/mensajes"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_cp01_empresa_escribe_y_el_candidato_recibe_aviso(datos, db_session: Session):
    pid = datos["postulacion"].id
    res = client.post(_url(pid), data={"contenido": "Hola Lucia, ¿podés el lunes?"}, headers=_auth(datos["token_empresa"]))
    assert res.status_code == 201, res.text
    assert res.json()["es_mio"] is True and res.json()["sender_rol"] == "empresa"

    conv = db_session.query(Conversation).filter_by(application_id=pid).one()
    # Respeta el CHECK de Supabase: hilo de postulación sin candidate_id/company_id.
    assert conv.candidate_id is None and conv.company_id is None
    miembros = {m.user_id for m in db_session.query(ConversationMember).filter_by(conversation_id=conv.id)}
    assert miembros == {datos["usuario_cand"].id, *(r.id for r in datos["reclutadores"])}

    aviso = (
        db_session.query(Notification)
        .filter_by(user_id=datos["usuario_cand"].id, notification_type="new_message")
        .one()
    )
    assert "Nuevo mensaje" in aviso.title


def test_cp02_candidato_lee_el_hilo(datos):
    pid = datos["postulacion"].id
    client.post(_url(pid), data={"contenido": "Primer mensaje"}, headers=_auth(datos["token_empresa"]))

    res = client.get(_url(pid), headers=_auth(datos["token_cand"]))
    assert res.status_code == 200, res.text
    hilo = res.json()
    assert hilo["candidato_carrera"] == "Ingeniería Informática"
    assert [m["content"] for m in hilo["mensajes"]] == ["Primer mensaje"]
    assert hilo["mensajes"][0]["es_mio"] is False and hilo["mensajes"][0]["sender_rol"] == "empresa"
    assert hilo["no_leidos"] == 0


def test_cp03_adjunto_se_sube_y_lo_descarga_la_otra_parte(datos):
    pid = datos["postulacion"].id
    contenido = b"%PDF-1.4 cv de prueba"
    res = client.post(
        _url(pid),
        files={"archivo": ("../../mi cv.pdf", contenido, "application/pdf")},
        headers=_auth(datos["token_cand"]),
    )
    assert res.status_code == 201, res.text
    adjunto = res.json()["adjunto"]
    # El nombre se limpia: sin rutas para escaparse de la carpeta de adjuntos.
    assert adjunto["original_filename"] == "mi cv.pdf"
    assert adjunto["file_size"] == len(contenido)

    descarga = client.get(f"/api/comunicacion/adjuntos/{adjunto['id']}", headers=_auth(datos["token_empresa"]))
    assert descarga.status_code == 200
    assert descarga.content == contenido
    assert descarga.headers["content-disposition"].startswith("attachment")

    ajena = client.get(f"/api/comunicacion/adjuntos/{adjunto['id']}", headers=_auth(datos["token_ajeno"]))
    assert ajena.status_code == 403


def test_cp04_rechaza_adjuntos_de_mas_de_5_mb(datos):
    grande = b"0" * (5 * 1024 * 1024 + 1)
    res = client.post(
        _url(datos["postulacion"].id),
        files={"archivo": ("grande.pdf", grande, "application/pdf")},
        headers=_auth(datos["token_cand"]),
    )
    assert res.status_code == 422
    assert "5 MB" in res.json()["detail"]


def test_cp05_rechaza_mensaje_vacio(datos):
    res = client.post(_url(datos["postulacion"].id), data={"contenido": "   "}, headers=_auth(datos["token_cand"]))
    assert res.status_code == 422


@pytest.mark.parametrize("quien", ["token_ajeno", "token_otra_empresa"])
def test_cp06_terceros_no_acceden_a_la_conversacion(datos, quien):
    pid = datos["postulacion"].id
    assert client.get(_url(pid), headers=_auth(datos[quien])).status_code == 403
    assert client.post(_url(pid), data={"contenido": "hola"}, headers=_auth(datos[quien])).status_code == 403


def test_cp07_requiere_sesion(datos):
    assert client.get(_url(datos["postulacion"].id)).status_code == 401
