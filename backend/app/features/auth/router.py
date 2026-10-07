from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException, UnauthorizedException
from app.common.request_context import get_client_ip
from app.core.database import get_db
from app.features.auth.schema import (
    CambiarPasswordRequest,
    LoginRequest,
    MessageResponse,
    MisPermisosResponse,
    RefreshRequest,
    RegistroEgresadoRequest,
    RegistroEmpresaRequest,
    TokenResponse,
)
from app.features.bitacora.service import BitacoraService
from app.features.auth.service import AuthService
from app.models.usuario import AppUser
from app.security.dependencies import CurrentUser, get_current_user
from app.security.permisos import permisos_de_usuario
from app.security.tenant import institucion_de_usuario

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/registro/egresado", response_model=MessageResponse, status_code=201)
def registrar_egresado(data: RegistroEgresadoRequest, request: Request, db: Session = Depends(get_db)) -> MessageResponse:
    usuario = AuthService(db).registrar_egresado(data)
    BitacoraService(db).registrar(
        modulo="auth", accion="registro_egresado", usuario_id=usuario.id, ip=get_client_ip(request)
    )
    db.commit()
    return MessageResponse(detail="Registro exitoso. Revisa tu correo para verificar la cuenta.")


@router.post("/registro/empresa", response_model=MessageResponse, status_code=201)
def registrar_empresa(data: RegistroEmpresaRequest, request: Request, db: Session = Depends(get_db)) -> MessageResponse:
    usuario = AuthService(db).registrar_empresa(data)
    BitacoraService(db).registrar(
        modulo="auth", accion="registro_empresa", usuario_id=usuario.id, ip=get_client_ip(request)
    )
    db.commit()
    return MessageResponse(detail="Solicitud de registro recibida. Queda pendiente de autorización.")


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    ip = get_client_ip(request)
    try:
        token, usuario = AuthService(db).login(data.correo, data.password)
    except UnauthorizedException:
        BitacoraService(db).registrar(
            modulo="auth",
            accion="login_fallido",
            ip=ip,
            detalles=f"correo={data.correo}",
            resultado=False,
        )
        db.commit()
        raise

    BitacoraService(db).registrar(modulo="auth", accion="login", usuario_id=usuario.id, ip=ip)
    db.commit()
    return token


@router.post("/refresh", response_model=TokenResponse)
def refrescar_token(data: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return AuthService(db).refrescar_token(data.refresh_token)


@router.post("/cambiar-password", response_model=TokenResponse)
def cambiar_password(
    data: CambiarPasswordRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenResponse:
    ip = get_client_ip(request)
    servicio = AuthService(db)
    try:
        tokens = servicio.cambiar_password(current_user.id_usuario, data.password_actual, data.password_nueva)
    except BusinessException:
        BitacoraService(db).registrar(
            modulo="auth", accion="cambiar_password", usuario_id=current_user.id_usuario, ip=ip, resultado=False
        )
        db.commit()
        raise

    BitacoraService(db).registrar(modulo="auth", accion="cambiar_password", usuario_id=current_user.id_usuario, ip=ip)
    db.commit()
    return tokens


@router.get("/permisos", response_model=MisPermisosResponse)
def mis_permisos(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Componentes del panel que puede usar el usuario; se consulta en la base, no en el token."""
    if db.get(AppUser, current_user.id_usuario) is None:
        raise UnauthorizedException("La cuenta ya no existe.")
    institucion = institucion_de_usuario(db, current_user)
    superadmin = "platform_admin" in current_user.roles and institucion is None
    permisos = permisos_de_usuario(db, current_user.id_usuario, current_user.roles, institucion)
    return MisPermisosResponse(permisos=sorted(permisos), superadmin=superadmin)
