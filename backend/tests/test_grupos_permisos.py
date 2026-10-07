"""Requisito general 2: grupos de usuarios y privilegios por componente de la interfaz."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.tenancy import INSTITUCION_POR_DEFECTO_ID
from app.main import app
from app.models.grupo import UserGroup
from app.models.seguridad import AuditLog
from app.models.usuario import AppUser, Role, UserRole
from app.security.jwt_provider import create_access_token
from app.security.permisos import CATALOGO, TODOS

client = TestClient(app)
UMSS = uuid.UUID("50000000-0000-0000-0000-000000000002")


def _usuario(db: Session, prefijo: str, rol: str, universidad: uuid.UUID | None) -> AppUser:
    usuario = AppUser(
        email=f"{prefijo}_{uuid.uuid4().hex[:8]}@grupos.test.bo",
        password_hash="x",
        account_status="active",
        institution_id=universidad,
    )
    db.add(usuario)
    db.flush()
    db.add(UserRole(user_id=usuario.id, role_id=db.scalar(select(Role.id).where(Role.name == rol))))
    return usuario


def _token(usuario: AppUser, rol: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(usuario.id), rol, {'roles': [rol]})}"}


@pytest.fixture
def gente():
    db: Session = SessionLocal()
    personas = {
        "superadmin": _usuario(db, "super", "platform_admin", None),
        "admin": _usuario(db, "admin", "platform_admin", INSTITUCION_POR_DEFECTO_ID),
        "moderador": _usuario(db, "moderador", "moderator", INSTITUCION_POR_DEFECTO_ID),
        "otro_moderador": _usuario(db, "moderador2", "moderator", INSTITUCION_POR_DEFECTO_ID),
        "admin_umss": _usuario(db, "admin_umss", "platform_admin", UMSS),
    }
    db.commit()
    datos = {
        nombre: _token(u, "moderator" if "moderador" in nombre else "platform_admin") for nombre, u in personas.items()
    }
    datos.update({f"{nombre}_id": str(u.id) for nombre, u in personas.items()})
    yield datos
    # Los grupos de prueba se borran con sus miembros y permisos (ON DELETE CASCADE).
    db.query(UserGroup).filter(UserGroup.name.like("Prueba %")).delete(synchronize_session=False)
    db.commit()
    db.close()


def _permisos(cabecera: dict) -> set[str]:
    res = client.get("/api/auth/permisos", headers=cabecera)
    assert res.status_code == 200, res.text
    return set(res.json()["permisos"])


def _grupo(cabecera: dict, nombre: str, permisos: list[str], miembros: list[str], **extra):
    return client.post(
        "/api/admin/grupos",
        json={"nombre": f"Prueba {nombre} {uuid.uuid4().hex[:4]}", "permisos": permisos, "miembros": miembros, **extra},
        headers=cabecera,
    )


def test_el_catalogo_cubre_menus_formularios_botones_y_etiquetas(gente):
    assert {c.tipo for c in CATALOGO} == {"menu", "formulario", "boton", "etiqueta"}
    res = client.get("/api/admin/permisos/catalogo", headers=gente["admin"])
    assert res.status_code == 200, res.text
    assert {c["codigo"] for c in res.json()["componentes"]} == set(TODOS)
    assert res.json()["siempre_admin"] == ["menu.grupos"]
    # Los grupos los administra el admin de la universidad, no el moderador.
    assert client.get("/api/admin/permisos/catalogo", headers=gente["moderador"]).status_code == 403


def test_sin_grupo_cada_rol_tiene_sus_permisos_por_defecto(gente):
    assert _permisos(gente["superadmin"]) == set(TODOS)
    admin, moderador = _permisos(gente["admin"]), _permisos(gente["moderador"])
    assert {"menu.usuarios", "menu.grupos", "menu.bitacora", "boton.reportes.exportar"} <= admin
    assert {"menu.validacion", "menu.moderacion", "menu.bitacora"} <= moderador
    assert not {"menu.usuarios", "menu.grupos", "menu.universidades"} & moderador


def test_el_grupo_define_lo_que_ve_y_el_backend_lo_hace_cumplir(gente):
    res = _grupo(
        gente["admin"],
        "Moderación",
        ["menu.moderacion", "boton.moderacion.decidir", "menu.alertas"],
        [gente["moderador_id"]],
        descripcion="Solo revisa ofertas",
    )
    assert res.status_code == 201, res.text
    grupo = res.json()
    assert [(m["id"], m["rol"]) for m in grupo["miembros"]] == [(gente["moderador_id"], "moderator")]

    assert _permisos(gente["moderador"]) == {"menu.moderacion", "boton.moderacion.decidir", "menu.alertas"}
    assert client.get("/api/validacion/vacantes/pendientes", headers=gente["moderador"]).status_code == 200
    negado = client.get("/api/validacion/egresados/pendientes", headers=gente["moderador"])
    assert negado.status_code == 403 and "Validación de egresados" in negado.json()["detail"]
    assert client.get("/api/bitacora", headers=gente["moderador"]).status_code == 403
    assert client.get("/api/instituciones/panel", headers=gente["moderador"]).status_code == 403
    # El otro moderador, sin grupo, sigue con lo de su rol.
    assert client.get("/api/validacion/egresados/pendientes", headers=gente["otro_moderador"]).status_code == 200

    # Editar el grupo cambia los permisos al instante, sin volver a iniciar sesión.
    editado = client.put(
        f"/api/admin/grupos/{grupo['id']}",
        json={
            "nombre": grupo["nombre"],
            "permisos": ["menu.moderacion", "menu.validacion"],
            "miembros": [gente["moderador_id"]],
        },
        headers=gente["admin"],
    )
    assert editado.status_code == 200, editado.text
    assert editado.json()["permisos"] == ["menu.moderacion", "menu.validacion"]
    assert client.get("/api/validacion/egresados/pendientes", headers=gente["moderador"]).status_code == 200

    assert client.delete(f"/api/admin/grupos/{grupo['id']}", headers=gente["admin"]).status_code == 204
    assert "menu.bitacora" in _permisos(gente["moderador"])


def test_el_rol_pone_el_techo_y_el_admin_no_se_bloquea(gente):
    res = _grupo(gente["admin"], "Mixto", ["menu.usuarios", "menu.reportes"], [gente["moderador_id"], gente["admin_id"]])
    assert res.status_code == 201, res.text
    # Un moderador no recibe un componente reservado a administradores aunque su grupo lo tenga.
    assert _permisos(gente["moderador"]) == {"menu.reportes"}
    assert client.get("/api/admin/usuarios", headers=gente["moderador"]).status_code == 403
    # El admin queda limitado por su grupo, pero conserva «Grupos y permisos».
    assert _permisos(gente["admin"]) == {"menu.usuarios", "menu.reportes", "menu.grupos"}
    assert client.get("/api/bitacora", headers=gente["admin"]).status_code == 403
    assert client.get("/api/admin/grupos", headers=gente["admin"]).status_code == 200
    # El superadmin no se ve afectado por ningún grupo.
    assert client.get("/api/bitacora", headers=gente["superadmin"]).status_code == 200


def test_las_etiquetas_y_botones_tambien_se_controlan(gente):
    _grupo(gente["admin"], "Lectores", ["menu.dashboard", "menu.reportes"], [gente["moderador_id"]])
    panel = client.get("/api/instituciones/panel", headers=gente["moderador"])
    assert panel.status_code == 200, panel.text
    assert panel.json()["totales"] is None and panel.json()["actividad"] == []
    assert client.get("/api/instituciones/panel", headers=gente["admin"]).json()["totales"] is not None

    consulta = {"fuente": "vacantes", "columnas": ["titulo"]}
    assert client.post("/api/reportes/vista-previa", json=consulta, headers=gente["moderador"]).status_code == 200
    exportar = client.post("/api/reportes/exportar", json={**consulta, "formato": "excel"}, headers=gente["moderador"])
    assert exportar.status_code == 403 and "Exportar reporte" in exportar.json()["detail"]
    permitido = client.post("/api/reportes/exportar", json={**consulta, "formato": "excel"}, headers=gente["admin"])
    assert permitido.status_code == 200


def test_cada_universidad_administra_solo_sus_grupos(gente):
    grupo = _grupo(gente["admin"], "UAGRM", ["menu.reportes"], [gente["moderador_id"]]).json()
    assert grupo["institucion_id"] == str(INSTITUCION_POR_DEFECTO_ID)

    assert grupo["id"] not in {g["id"] for g in client.get("/api/admin/grupos", headers=gente["admin_umss"]).json()}
    cambio = {"nombre": "Prueba robado", "permisos": [], "miembros": []}
    assert client.put(f"/api/admin/grupos/{grupo['id']}", json=cambio, headers=gente["admin_umss"]).status_code == 404
    assert client.delete(f"/api/admin/grupos/{grupo['id']}", headers=gente["admin_umss"]).status_code == 404
    # No puede sumar personal de otra universidad (ni egresados o empresas) a sus grupos.
    assert _grupo(gente["admin_umss"], "Ajeno", ["menu.reportes"], [gente["moderador_id"]]).status_code == 422

    personal = client.get("/api/admin/grupos/personal", headers=gente["admin"]).json()
    moderador = next(p for p in personal if p["id"] == gente["moderador_id"])
    assert moderador["grupos"] == [grupo["nombre"]] and moderador["permisos"] == ["menu.reportes"]
    assert gente["admin_umss_id"] not in {p["id"] for p in personal}


def test_el_superadmin_elige_la_universidad(gente):
    assert _grupo(gente["superadmin"], "Sin universidad", [], []).status_code == 422
    res = _grupo(gente["superadmin"], "UMSS", ["menu.dashboard"], [gente["admin_umss_id"]], institucion_id=str(UMSS))
    assert res.status_code == 201, res.text
    assert res.json()["institucion_id"] == str(UMSS)
    assert _permisos(gente["admin_umss"]) == {"menu.dashboard", "menu.grupos"}
    filtrados = client.get("/api/admin/grupos", params={"institucion_id": str(UMSS)}, headers=gente["superadmin"])
    assert {g["institucion_id"] for g in filtrados.json()} == {str(UMSS)}


def test_validaciones_y_bitacora(gente):
    db: Session = SessionLocal()
    antes = db.scalar(select(func.count(AuditLog.id)))
    primero = _grupo(gente["admin"], "Duplicado", ["menu.reportes"], [])
    assert primero.status_code == 201
    repetido = client.post(
        "/api/admin/grupos",
        json={"nombre": primero.json()["nombre"].upper(), "permisos": [], "miembros": []},
        headers=gente["admin"],
    )
    assert repetido.status_code == 409
    assert _grupo(gente["admin"], "Inventado", ["menu.no_existe"], []).status_code == 422
    # Solo el alta válida queda en la bitácora.
    assert db.scalar(select(func.count(AuditLog.id))) == antes + 1
    db.close()
