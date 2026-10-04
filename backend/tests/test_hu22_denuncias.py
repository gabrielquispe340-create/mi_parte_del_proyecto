"""HU-22: denuncia de ofertas sospechosas, ocultamiento automático y revisión del administrador."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.tenancy import INSTITUCION_POR_DEFECTO_ID
from app.main import app
from app.models.candidato import CandidateProfile
from app.models.empresa import Company, CompanyMember
from app.models.institucion import CompanyInstitution
from app.models.moderacion import ModerationReport
from app.models.notificacion import Notification
from app.models.usuario import AppUser, Role, UserRole
from app.models.vacante import JobPosting
from app.security.jwt_provider import create_access_token

client = TestClient(app)
UMSS = uuid.UUID("50000000-0000-0000-0000-000000000002")
CON_DETALLE = "Me pidieron depositar 300 Bs para reservar el puesto antes de la entrevista."


@pytest.fixture
def db_session():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _usuario(db: Session, prefijo: str, rol: str, universidad: uuid.UUID | None = None) -> AppUser:
    if not db.query(Role).filter_by(name=rol).first():
        db.add(Role(name=rol))
        db.flush()
    usuario = AppUser(
        email=f"{prefijo}_{uuid.uuid4().hex[:8]}@test.bo",
        password_hash="x",
        account_status="active",
        institution_id=universidad,
    )
    db.add(usuario)
    db.flush()
    db.add(UserRole(user_id=usuario.id, role_id=db.query(Role).filter_by(name=rol).first().id))
    return usuario


def _egresado(db: Session, nombre: str) -> AppUser:
    usuario = _usuario(db, "egresado", "candidate")
    db.add(CandidateProfile(user_id=usuario.id, first_name=nombre, last_name="Prueba", verification_status="verified"))
    return usuario


def _token(usuario: AppUser, rol: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(usuario.id), rol, {'roles': [rol]})}"}


@pytest.fixture
def datos(db_session: Session):
    db = db_session
    sufijo = uuid.uuid4().hex[:6]
    empresa = Company(
        legal_name=f"Sospechosa {sufijo} S.R.L.",
        trade_name=f"Sospechosa {sufijo}",
        tax_id=f"NIT-{sufijo}",
        verification_status="verified",
        account_status="active",
        contact_email=f"rrhh_{sufijo}@test.bo",
    )
    db.add(empresa)
    db.flush()
    # Recluta solo en la UAGRM: el admin de la UMSS no debe ver sus denuncias.
    db.add(CompanyInstitution(company_id=empresa.id, institution_id=INSTITUCION_POR_DEFECTO_ID, status="approved"))
    reclutador = _usuario(db, "rrhh", "empresa")
    db.add(CompanyMember(user_id=reclutador.id, company_id=empresa.id, member_type="recruiter", is_active=True))
    titulo = f"Asistente administrativo {sufijo}"
    vacante = JobPosting(
        company_id=empresa.id,
        title=titulo,
        description="Oferta de prueba para denuncias",
        seniority_level="junior",
        employment_type="permanent",
        work_modality="onsite",
        city="Santa Cruz",
        status="published",
        created_by=reclutador.id,
    )
    db.add(vacante)
    egresados = [_egresado(db, f"Denunciante{i}") for i in range(4)]
    postulante = _egresado(db, "Postulante")
    admin_uagrm = _usuario(db, "admin_uagrm", "platform_admin", INSTITUCION_POR_DEFECTO_ID)
    admin_umss = _usuario(db, "admin_umss", "platform_admin", UMSS)
    db.commit()
    return {
        "vacante_id": str(vacante.id),
        "titulo": titulo,
        "reclutador_id": reclutador.id,
        "egresados": [_token(e, "candidate") for e in egresados],
        "egresado_ids": [e.id for e in egresados],
        "postulante": _token(postulante, "candidate"),
        "empresa": _token(reclutador, "empresa"),
        "admin": _token(admin_uagrm, "platform_admin"),
        "admin_otra": _token(admin_umss, "platform_admin"),
    }


def _denunciar(datos, i: int, descripcion: str | None = CON_DETALLE, categoria: str = "fraud"):
    return client.post(
        f"/api/moderacion/vacantes/{datos['vacante_id']}/denuncias",
        json={"categoria": categoria, "descripcion": descripcion},
        headers=datos["egresados"][i],
    )


def _en_busqueda(datos) -> bool:
    res = client.get("/api/vacantes/buscar", params={"q": datos["titulo"]}, headers=datos["postulante"])
    assert res.status_code == 200, res.text
    return any(v["id"] == datos["vacante_id"] for v in res.json()["items"])


def _pendientes(datos, quien: str = "admin") -> dict | None:
    res = client.get("/api/moderacion/denuncias", params={"page_size": 100}, headers=datos[quien])
    assert res.status_code == 200, res.text
    return next((v for v in res.json()["items"] if v["vacante_id"] == datos["vacante_id"]), None)


def _resolver(datos, decision: str, nota: str | None = None, quien: str = "admin"):
    return client.post(
        f"/api/moderacion/vacantes/{datos['vacante_id']}/resolucion",
        json={"decision": decision, "nota": nota},
        headers=datos[quien],
    )


def _postular(datos):
    return client.post("/api/postulaciones/", json={"job_id": datos["vacante_id"]}, headers=datos["postulante"])


def _avisos(db: Session, user_id, tipo: str) -> list[Notification]:
    db.expire_all()
    return db.query(Notification).filter_by(user_id=user_id, notification_type=tipo).all()


def test_cp01_la_denuncia_queda_registrada_y_visible_para_el_admin(datos):
    res = _denunciar(datos, 0)
    assert res.status_code == 201, res.text
    assert res.json()["cuenta_para_umbral"] is True

    mia = client.get(f"/api/moderacion/vacantes/{datos['vacante_id']}/mi-denuncia", headers=datos["egresados"][0])
    assert mia.json()["denunciada"] is True

    item = _pendientes(datos)
    assert item is not None
    assert item["oculta"] is False
    assert item["denuncias"][0]["categoria"] == "fraud"
    assert item["denuncias"][0]["denunciante_nombre"] == "Denunciante0 Prueba"
    # Una sola denuncia no la oculta.
    assert _en_busqueda(datos)


def test_no_se_denuncia_dos_veces_ni_la_propia_oferta(datos):
    assert _denunciar(datos, 0).status_code == 201
    assert _denunciar(datos, 0).status_code == 409
    propia = client.post(
        f"/api/moderacion/vacantes/{datos['vacante_id']}/denuncias",
        json={"categoria": "spam", "descripcion": CON_DETALLE},
        headers=datos["empresa"],
    )
    assert propia.status_code == 422


def test_otro_motivo_exige_contar_que_paso(datos):
    assert _denunciar(datos, 0, descripcion="raro", categoria="other").status_code == 422
    assert _denunciar(datos, 0, descripcion=CON_DETALLE, categoria="other").status_code == 201


def test_cp02_la_tercera_denuncia_oculta_la_oferta(datos, db_session):
    for i in range(2):
        assert _denunciar(datos, i).status_code == 201
    assert _en_busqueda(datos)

    assert _denunciar(datos, 2).status_code == 201

    assert not _en_busqueda(datos)
    detalle = client.get(f"/api/vacantes/buscar/{datos['vacante_id']}", headers=datos["postulante"])
    assert detalle.status_code == 404
    # La empresa la sigue viendo, marcada como oculta, y recibió el aviso.
    assert client.get(f"/api/vacantes/buscar/{datos['vacante_id']}", headers=datos["empresa"]).status_code == 200
    mias = client.get("/api/vacantes/mis-vacantes", params={"page_size": 100}, headers=datos["empresa"]).json()
    assert next(v for v in mias["items"] if v["id"] == datos["vacante_id"])["oculta_por_denuncias"] is True
    assert len(_avisos(db_session, datos["reclutador_id"], "vacante_denunciada")) == 1
    # Mientras está oculta no recibe postulaciones.
    assert _postular(datos).status_code == 400
    assert _pendientes(datos)["oculta"] is True


def test_denuncias_sin_fundamento_no_cuentan_para_el_umbral(datos):
    assert _denunciar(datos, 0).status_code == 201
    assert _denunciar(datos, 1).status_code == 201
    sin_detalle = _denunciar(datos, 2, descripcion=None)
    assert sin_detalle.status_code == 201
    assert sin_detalle.json()["cuenta_para_umbral"] is False

    assert _en_busqueda(datos)
    item = _pendientes(datos)
    assert item["oculta"] is False
    assert item["denuncias_que_cuentan"] == 2
    assert len(item["denuncias"]) == 3


def test_cp03_mantener_la_vuelve_visible_y_cierra_las_denuncias(datos, db_session):
    for i in range(3):
        _denunciar(datos, i)
    assert not _en_busqueda(datos)

    res = _resolver(datos, "mantener")
    assert res.status_code == 200, res.text
    assert res.json()["denuncias_cerradas"] == 3
    assert res.json()["estado_vacante"] == "published"

    assert _en_busqueda(datos)
    assert _pendientes(datos) is None
    db_session.expire_all()
    estados = {
        r.status for r in db_session.query(ModerationReport).filter_by(job_id=uuid.UUID(datos["vacante_id"]))
    }
    assert estados == {"dismissed"}
    assert len(_avisos(db_session, datos["reclutador_id"], "denuncia_resuelta")) == 1
    assert len(_avisos(db_session, datos["egresado_ids"][0], "denuncia_resuelta")) == 1
    # Ya resuelta, no hay nada más que decidir.
    assert _resolver(datos, "mantener").status_code == 422


def test_cp04_eliminar_la_retira_y_deja_de_aceptar_postulaciones(datos):
    _denunciar(datos, 0)
    res = _resolver(datos, "eliminar", nota="Pedía dinero a los postulantes.")
    assert res.status_code == 200, res.text
    assert res.json()["estado_vacante"] == "closed"

    assert not _en_busqueda(datos)
    assert client.get(f"/api/vacantes/buscar/{datos['vacante_id']}", headers=datos["postulante"]).status_code == 404
    assert _postular(datos).status_code == 400
    mias = client.get("/api/vacantes/mis-vacantes", params={"page_size": 100}, headers=datos["empresa"]).json()
    retirada = next(v for v in mias["items"] if v["id"] == datos["vacante_id"])
    assert "Pedía dinero" in retirada["rejection_reason"]


def test_suspender_exige_motivo_y_la_deja_rechazada(datos):
    _denunciar(datos, 0)
    assert _resolver(datos, "suspender").status_code == 422
    res = _resolver(datos, "suspender", nota="La descripción no coincide con la empresa.")
    assert res.status_code == 200, res.text
    assert res.json()["estado_vacante"] == "rejected"
    assert not _en_busqueda(datos)


def test_cada_universidad_ve_solo_las_denuncias_de_sus_empresas(datos):
    _denunciar(datos, 0)
    assert _pendientes(datos, "admin_otra") is None
    assert _resolver(datos, "mantener", quien="admin_otra").status_code == 404
    # Un egresado no accede al listado del administrador.
    assert client.get("/api/moderacion/denuncias", headers=datos["egresados"][1]).status_code == 403


def test_el_contador_del_panel_coincide_con_el_listado(datos):
    _denunciar(datos, 0)
    _denunciar(datos, 1, descripcion=None)
    panel = client.get("/api/instituciones/panel", headers=datos["admin"]).json()
    listado = client.get("/api/moderacion/denuncias", headers=datos["admin"]).json()
    assert panel["pendientes"]["denuncias"] == listado["total"]
    assert listado["total"] >= 1
