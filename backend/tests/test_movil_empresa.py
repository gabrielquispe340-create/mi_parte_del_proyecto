"""App móvil: postulantes nuevos y agenda de la empresa, y bandeja de mensajes de ambos lados."""
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
from app.models.postulacion import Application
from app.models.usuario import AppUser, Role, UserRole
from app.models.vacante import JobPosting
from app.security.jwt_provider import create_access_token

client = TestClient(app)
AHORA = datetime.now(timezone.utc).replace(microsecond=0)


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


def _empresa(db: Session, nombre: str, miembros: int = 1) -> tuple[list[AppUser], Company]:
    empresa = Company(
        legal_name=f"{nombre} S.R.L.",
        trade_name=nombre,
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


def _vacante(db: Session, empresa: Company, autor: AppUser, titulo: str) -> JobPosting:
    vacante = JobPosting(
        company_id=empresa.id,
        title=titulo,
        description="Vacante de prueba de la app móvil",
        seniority_level="junior",
        employment_type="permanent",
        work_modality="onsite",
        city="Santa Cruz",
        status="published",
        created_by=autor.id,
    )
    db.add(vacante)
    db.flush()
    return vacante


def _postulacion(db: Session, vacante: JobPosting, nombre: str, estado: str, hace: timedelta):
    usuario = _usuario(db, "cand", "candidate")
    perfil = CandidateProfile(user_id=usuario.id, first_name=nombre, last_name="Prueba", verification_status="verified")
    db.add(perfil)
    db.flush()
    postulacion = Application(candidate_id=perfil.id, job_id=vacante.id, current_status=estado, applied_at=AHORA - hace)
    db.add(postulacion)
    db.flush()
    return usuario, postulacion


def _entrevista(db: Session, postulacion: Application, inicio: datetime, estado: str = "confirmed") -> Interview:
    entrevista = Interview(
        application_id=postulacion.id,
        scheduled_start=inicio,
        scheduled_end=inicio + timedelta(minutes=45),
        modality="virtual",
        meeting_url="https://meet.google.com/abc-defg-hij",
        status=estado,
    )
    db.add(entrevista)
    return entrevista


def _token(usuario: AppUser, rol: str) -> str:
    return create_access_token(str(usuario.id), rol, {"roles": [rol]})


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def datos(db_session: Session):
    db = db_session
    reclutadores, empresa = _empresa(db, f"Andina {uuid.uuid4().hex[:4]}", miembros=2)
    soporte = _vacante(db, empresa, reclutadores[0], "Soporte técnico")
    datos_vac = _vacante(db, empresa, reclutadores[0], "Analista de datos")
    usuario_lucia, lucia = _postulacion(db, soporte, "Lucia", "applied", timedelta(days=2))
    usuario_mario, mario = _postulacion(db, datos_vac, "Mario", "applied", timedelta(hours=3))
    _, en_revision = _postulacion(db, soporte, "Revisado", "screening", timedelta(hours=1))

    otros, otra_empresa = _empresa(db, f"Ajena {uuid.uuid4().hex[:4]}")
    ajena = _vacante(db, otra_empresa, otros[0], "Vacante ajena")
    _, postulacion_ajena = _postulacion(db, ajena, "Ajeno", "applied", timedelta(minutes=5))

    # Agenda: hoy a las 10:00 UTC, mañana, y una de otra empresa el mismo día.
    hoy = AHORA.replace(hour=10, minute=0, second=0)
    entrevista_hoy = _entrevista(db, en_revision, hoy)
    _entrevista(db, lucia, hoy + timedelta(days=1), estado="pending_confirmation")
    _entrevista(db, postulacion_ajena, hoy + timedelta(hours=1))
    db.commit()

    return {
        "empresa": empresa,
        "lucia": lucia,
        "mario": mario,
        "inicio_dia": hoy.replace(hour=0),
        "entrevista_hoy": entrevista_hoy,
        "token_empresa": _token(reclutadores[0], "empresa"),
        "token_colega": _token(reclutadores[1], "empresa"),
        "token_otra_empresa": _token(otros[0], "empresa"),
        "token_lucia": _token(usuario_lucia, "candidate"),
        "token_mario": _token(usuario_mario, "candidate"),
    }


# ─── Postulantes nuevos ──────────────────────────────────────────────────────


def test_postulantes_nuevos_solo_sin_revisar_y_de_la_empresa(datos):
    res = client.get("/api/seleccion/postulantes-nuevos", headers=_auth(datos["token_empresa"]))
    assert res.status_code == 200, res.text
    cuerpo = res.json()
    assert cuerpo["empresa_nombre"] == datos["empresa"].trade_name
    assert cuerpo["total"] == 2
    # Del más reciente al más viejo; el que ya está en revisión y el de otra empresa no aparecen.
    assert [p["candidato_nombre"] for p in cuerpo["postulantes"]] == ["Mario Prueba", "Lucia Prueba"]
    assert cuerpo["postulantes"][0]["vacante_titulo"] == "Analista de datos"
    assert cuerpo["postulantes"][0]["postulacion_id"] == str(datos["mario"].id)


def test_postulantes_nuevos_respeta_el_limite(datos):
    res = client.get("/api/seleccion/postulantes-nuevos?limite=1", headers=_auth(datos["token_empresa"]))
    assert res.status_code == 200
    assert res.json()["total"] == 2 and len(res.json()["postulantes"]) == 1


def test_postulantes_nuevos_solo_para_empresas(datos):
    assert client.get("/api/seleccion/postulantes-nuevos", headers=_auth(datos["token_lucia"])).status_code == 403
    assert client.get("/api/seleccion/postulantes-nuevos").status_code == 401


# ─── Agenda de entrevistas ───────────────────────────────────────────────────


def _agenda(token: str, desde: datetime, hasta: datetime):
    return client.get(
        "/api/seleccion/entrevistas",
        params={"desde": desde.isoformat(), "hasta": hasta.isoformat()},
        headers=_auth(token),
    )


def test_agenda_del_dia_solo_de_la_empresa(datos):
    inicio = datos["inicio_dia"]
    res = _agenda(datos["token_empresa"], inicio, inicio + timedelta(days=1))
    assert res.status_code == 200, res.text
    entrevistas = res.json()
    # La de mañana queda fuera del rango y la de la otra empresa no se ve.
    assert [e["id"] for e in entrevistas] == [str(datos["entrevista_hoy"].id)]
    assert entrevistas[0]["candidato_nombre"] == "Revisado Prueba"
    assert entrevistas[0]["vacante_titulo"] == "Soporte técnico"


def test_agenda_de_la_semana_ordenada_por_hora(datos):
    inicio = datos["inicio_dia"]
    res = _agenda(datos["token_empresa"], inicio, inicio + timedelta(days=7))
    assert res.status_code == 200
    inicios = [e["scheduled_start"] for e in res.json()]
    assert len(inicios) == 2 and inicios == sorted(inicios)


@pytest.mark.parametrize("dias", [0, -1, 32])
def test_agenda_rechaza_rangos_invalidos(datos, dias):
    inicio = datos["inicio_dia"]
    res = _agenda(datos["token_empresa"], inicio, inicio + timedelta(days=dias))
    assert res.status_code == 422
    assert isinstance(res.json()["detail"], str)


def test_agenda_solo_para_empresas(datos):
    inicio = datos["inicio_dia"]
    assert _agenda(datos["token_lucia"], inicio, inicio + timedelta(days=1)).status_code == 403


# ─── Bandeja de mensajes ─────────────────────────────────────────────────────


def _escribir(token: str, postulacion: Application, texto: str):
    res = client.post(
        f"/api/comunicacion/postulaciones/{postulacion.id}/mensajes",
        data={"contenido": texto},
        headers=_auth(token),
    )
    assert res.status_code == 201, res.text


def _bandeja(token: str) -> list[dict]:
    res = client.get("/api/comunicacion/conversaciones", headers=_auth(token))
    assert res.status_code == 200, res.text
    return res.json()


def test_bandeja_muestra_ultimo_mensaje_y_no_leidos(datos):
    _escribir(datos["token_empresa"], datos["lucia"], "Hola Lucia, ¿podés el lunes?")
    _escribir(datos["token_lucia"], datos["lucia"], "Sí, puedo.")
    _escribir(datos["token_empresa"], datos["lucia"], "Perfecto, te esperamos.")

    [hilo] = _bandeja(datos["token_lucia"])
    assert hilo["application_id"] == str(datos["lucia"].id)
    assert hilo["empresa_nombre"] == datos["empresa"].trade_name
    assert hilo["vacante_titulo"] == "Soporte técnico"
    assert hilo["ultimo_mensaje"] == "Perfecto, te esperamos."
    assert hilo["ultimo_mensaje_es_mio"] is False
    assert hilo["no_leidos"] == 1

    [del_reclutador] = _bandeja(datos["token_empresa"])
    assert del_reclutador["candidato_nombre"] == "Lucia Prueba"
    assert del_reclutador["ultimo_mensaje_es_mio"] is True and del_reclutador["no_leidos"] == 0

    # El colega nunca abrió el hilo: todo lo que no escribió él está sin leer.
    [del_colega] = _bandeja(datos["token_colega"])
    assert del_colega["no_leidos"] == 3


def test_bandeja_se_pone_al_dia_al_abrir_el_hilo(datos):
    _escribir(datos["token_empresa"], datos["lucia"], "¿Seguís interesada?")
    assert _bandeja(datos["token_lucia"])[0]["no_leidos"] == 1

    client.get(f"/api/comunicacion/postulaciones/{datos['lucia'].id}/mensajes", headers=_auth(datos["token_lucia"]))
    assert _bandeja(datos["token_lucia"])[0]["no_leidos"] == 0


def test_bandeja_ordena_por_ultimo_mensaje(datos):
    _escribir(datos["token_empresa"], datos["lucia"], "Primero a Lucia")
    _escribir(datos["token_empresa"], datos["mario"], "Después a Mario")
    assert [h["candidato_nombre"] for h in _bandeja(datos["token_empresa"])] == ["Mario Prueba", "Lucia Prueba"]

    _escribir(datos["token_lucia"], datos["lucia"], "Respondo yo")
    assert [h["candidato_nombre"] for h in _bandeja(datos["token_empresa"])] == ["Lucia Prueba", "Mario Prueba"]


def test_bandeja_no_muestra_hilos_ajenos(datos):
    _escribir(datos["token_empresa"], datos["lucia"], "Mensaje privado")
    assert _bandeja(datos["token_mario"]) == []
    assert _bandeja(datos["token_otra_empresa"]) == []
    assert client.get("/api/comunicacion/conversaciones").status_code == 401
