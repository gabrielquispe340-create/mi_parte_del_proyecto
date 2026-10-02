import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.common.request_context import get_client_ip
from app.core.database import get_db
from app.features.roles.schema import (
    AsignarRolRequest,
    AsignarRolResponse,
    CrearUsuarioStaffRequest,
    RolResponse,
    UsuarioAdminResponse,
)
from app.security.dependencies import require_roles
from app.security.tenant import AlcanceStaff, get_alcance_staff
from app.features.roles.service import RolesService

router = APIRouter(prefix="/admin", tags=["gestion-roles"])

_solo_admin = require_roles("platform_admin")


@router.get("/roles", response_model=list[RolResponse], dependencies=[Depends(_solo_admin)])
def listar_roles(db: Session = Depends(get_db)):
    return RolesService(db).listar_roles()


@router.get("/usuarios", response_model=list[UsuarioAdminResponse], dependencies=[Depends(_solo_admin)])
def listar_usuarios(alcance: AlcanceStaff = Depends(get_alcance_staff), db: Session = Depends(get_db)):
    return RolesService(db).listar_usuarios(alcance.institution_id)


@router.post(
    "/usuarios", response_model=UsuarioAdminResponse, status_code=201, dependencies=[Depends(_solo_admin)]
)
def crear_usuario_staff(
    data: CrearUsuarioStaffRequest,
    request: Request,
    alcance: AlcanceStaff = Depends(get_alcance_staff),
    db: Session = Depends(get_db),
):
    return RolesService(db).crear_usuario_staff(
        data,
        responsable_id=alcance.usuario.id_usuario,
        ip=get_client_ip(request),
        institution_id=alcance.institution_id,
    )


@router.put("/usuarios/{usuario_id}/rol", response_model=AsignarRolResponse, dependencies=[Depends(_solo_admin)])
def asignar_rol(
    usuario_id: uuid.UUID,
    data: AsignarRolRequest,
    request: Request,
    alcance: AlcanceStaff = Depends(get_alcance_staff),
    db: Session = Depends(get_db),
):
    usuario, rol_anterior = RolesService(db).asignar_rol(
        usuario_id=usuario_id,
        nombre_rol=data.rol,
        responsable_id=alcance.usuario.id_usuario,
        ip=get_client_ip(request),
        institution_id=alcance.institution_id,
    )
    return AsignarRolResponse(
        usuario=usuario,
        rol_anterior=rol_anterior,
        detalle="Rol actualizado. El usuario deberá iniciar sesión de nuevo para obtener los nuevos permisos.",
    )
