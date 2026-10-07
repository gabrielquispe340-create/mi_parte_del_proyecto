import jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException, ConflictException, UnauthorizedException
from app.core.tenancy import INSTITUCION_POR_DEFECTO_ID
from app.features.auth.repository import (
    CandidateRepository,
    EmpresaRegistroRepository,
    UsuarioRepository,
)
from app.features.auth.schema import RegistroEgresadoRequest, RegistroEmpresaRequest, TokenResponse
from app.features.planes.limites import verificar_cupo_egresados
from app.models.candidato import CandidateEducation, CandidateProfile
from app.models.empresa import Company, CompanyMember, Sector
from app.models.institucion import CompanyInstitution, Institution
from app.models.seguridad import LoginAttempt
from app.models.usuario import AppUser
from app.security.jwt_provider import create_access_token, create_refresh_token, decode_token
from app.security.login_rate_limiter import limpiar_intentos, registrar_intento_fallido, verificar_bloqueo
from app.security.password_hasher import hash_password, verify_password
from app.security.permisos import permisos_de_usuario
from app.shared.email_service import EmailService

_ROL_PRIORIDAD = ("platform_admin", "moderator", "empresa", "candidate")


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.usuarios = UsuarioRepository(db)
        self.candidatos = CandidateRepository(db)
        self.empresas = EmpresaRegistroRepository(db)
        self.email_service = EmailService()

    def registrar_egresado(self, data: RegistroEgresadoRequest) -> AppUser:
        if self.usuarios.existe_correo(data.correo):
            raise ConflictException("El correo electrónico ya está registrado.")
        if self.candidatos.existe_ci(data.ci):
            raise ConflictException("Ya existe un egresado registrado con ese CI.")
        if data.carrera_id is not None:
            from app.models.catalogo import FieldOfStudy

            if self.db.get(FieldOfStudy, data.carrera_id) is None:
                raise ConflictException("La carrera indicada no existe.")
        institucion = self._institucion_cliente(data.institucion_id or INSTITUCION_POR_DEFECTO_ID)
        verificar_cupo_egresados(self.db, institucion.id)

        usuario = AppUser(
            email=data.correo.strip().lower(),
            password_hash=hash_password(data.password),
            account_status="active",
        )
        self.usuarios.crear(usuario)
        self.usuarios.asignar_rol(usuario, "candidate")
        perfil = self.candidatos.crear(
            CandidateProfile(
                user_id=usuario.id,
                institution_id=institucion.id,
                first_name=data.nombres.strip(),
                last_name=data.apellidos.strip(),
                country_code="BO",
                document_type="ci",
                document_number=data.ci,
                document_country_code="BO",
                verification_status="pending",
            )
        )
        # carrera_id/anio_egreso/matricula no tienen columna en candidate_profile en el
        # esquema real: se guardan como una fila "principal" de candidate_education
        # (identificada por traer field_of_study_id set). Ver EgresadoRepository.
        if data.carrera_id is not None or data.anio_egreso is not None or data.matricula is not None:
            from datetime import date as _date

            from app.features.perfil.repository import EgresadoRepository

            marcador = EgresadoRepository.MARCADOR_EDUCACION_REGISTRO
            descripcion = f"{marcador} Matrícula: {data.matricula}" if data.matricula else marcador
            self.db.add(
                CandidateEducation(
                    candidate_id=perfil.id,
                    institution_id=institucion.id,
                    institution_name=institucion.name,
                    program_name="Carrera universitaria",
                    field_of_study_id=data.carrera_id,
                    education_level="undergraduate",
                    academic_status="graduated" if data.anio_egreso else "in_progress",
                    graduation_date=_date(data.anio_egreso, 12, 31) if data.anio_egreso else None,
                    description=descripcion,
                )
            )
        self.db.commit()
        self.email_service.enviar(
            data.correo, "Bienvenido a EGRESA", "Gracias por registrarte. Tu cuenta ya está lista para iniciar sesión."
        )
        return usuario

    _TAMANIO_MAP: dict[str, str] = {
        "startup": "startup",
        "micro": "startup",
        "1-10": "startup",
        "1 - 10": "startup",
        "pequeña": "small",
        "pequena": "small",
        "small": "small",
        "11-50": "small",
        "11 - 50": "small",
        "mediana": "medium",
        "medium": "medium",
        "51-200": "medium",
        "51 - 200": "medium",
        "grande": "large",
        "large": "large",
        "+200": "large",
        "200+": "large",
        "corporacion": "corporation",
        "corporación": "corporation",
        "corporation": "corporation",
    }

    def _mapear_tamanio_empresa(self, tamanio: str | None) -> str | None:
        """Normaliza el tamaño de empresa al valor exacto que exige ck_comp_size
        ('startup', 'small', 'medium', 'large', 'corporation'), aceptando el texto
        libre que puede llegar del formulario de registro."""
        if not tamanio:
            return None
        raw = tamanio.strip().lower()
        if raw in ("startup", "small", "medium", "large", "corporation"):
            return raw
        for clave, valor in self._TAMANIO_MAP.items():
            if clave in raw:
                return valor
        return "small"

    def registrar_empresa(self, data: RegistroEmpresaRequest) -> AppUser:
        if self.usuarios.existe_correo(data.correo):
            raise ConflictException("El correo electrónico ya está registrado.")
        if self.empresas.existe_nit(data.nit):
            raise ConflictException("Ya existe una empresa registrada con ese NIT/RUC.")
        if self.empresas.existe_razon_social(data.razon_social):
            raise ConflictException("Ya existe una empresa registrada con esa razón social.")

        instituciones = [self._institucion_cliente(inst_id) for inst_id in dict.fromkeys(data.instituciones_ids)]

        sector_id = None
        if data.sector:
            sector = self.db.scalar(select(Sector).where(func.lower(Sector.name) == data.sector.lower()))
            sector_id = sector.id if sector else None

        company_size = self._mapear_tamanio_empresa(data.tamanio)

        usuario = AppUser(
            email=data.correo.strip().lower(),
            password_hash=hash_password(data.password),
            account_status="active",
        )
        self.usuarios.crear(usuario)
        self.usuarios.asignar_rol(usuario, "empresa")

        empresa = Company(
            legal_name=data.razon_social,
            tax_id=data.nit,
            sector_id=sector_id,
            company_size=company_size,
            description=data.descripcion,
            website=data.sitio_web,
            phone=data.telefono,
            contact_email=data.correo.strip().lower(),
            country_code="BO",
            city=data.ciudad,
            address=data.direccion,
            verification_status="pending",
            account_status="active",
        )
        self.empresas.crear(empresa)
        self.empresas.crear_miembro(
            CompanyMember(user_id=usuario.id, company_id=empresa.id, member_type="owner", job_title="Propietario")
        )
        for institucion in instituciones:
            self.db.add(CompanyInstitution(company_id=empresa.id, institution_id=institucion.id, status="pending"))

        self.db.commit()
        self.email_service.enviar(
            data.correo,
            "Solicitud de registro recibida",
            "Tu empresa fue registrada y está pendiente de autorización por la UAGRM.",
        )
        return usuario

    def login(self, correo: str, password: str) -> tuple[TokenResponse, AppUser]:
        verificar_bloqueo(correo)
        usuario = self.usuarios.obtener_por_correo(correo)

        if usuario is None or not verify_password(password, usuario.password_hash):
            registrar_intento_fallido(correo)
            self._registrar_login_attempt(correo, usuario, success=False)
            raise UnauthorizedException("Correo o contraseña incorrectos.")

        if not usuario.activo:
            estado = (
                "pendiente de verificación" if usuario.account_status == "pending_verification" else "desactivada"
            )
            raise UnauthorizedException(f"La cuenta se encuentra {estado}.")

        empresa = self.usuarios.obtener_empresa_de_usuario(usuario.id)
        if empresa is not None and empresa.account_status == "suspended":
            self._registrar_login_attempt(correo, usuario, success=False)
            raise UnauthorizedException("La empresa asociada a esta cuenta se encuentra suspendida.")

        limpiar_intentos(correo)
        usuario.last_login_at = func.now()
        self._registrar_login_attempt(correo, usuario, success=True)
        return self._emitir_tokens(usuario), usuario

    def refrescar_token(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except jwt.PyJWTError as exc:
            raise UnauthorizedException("El token de actualización es inválido o ha expirado.") from exc

        if payload.get("type") != "refresh":
            raise UnauthorizedException("El token de actualización es inválido.")

        usuario = self.usuarios.obtener_por_id(payload.get("sub", ""))
        if usuario is None or not usuario.activo:
            raise UnauthorizedException("La cuenta no está activa.")

        empresa = self.usuarios.obtener_empresa_de_usuario(usuario.id)
        if empresa is not None and empresa.account_status == "suspended":
            raise UnauthorizedException("La empresa asociada a esta cuenta se encuentra suspendida.")

        return self._emitir_tokens(usuario)

    def cambiar_password(self, usuario_id, password_actual: str, password_nueva: str) -> TokenResponse:
        """Cambia la contraseña del propio usuario y le emite tokens nuevos.

        Los errores son 422 (no 401) para que el frontend no los confunda con una sesión
        vencida. Los intentos con la contraseña actual incorrecta cuentan para el bloqueo
        del login, así este endpoint no sirve para adivinarla.
        """
        usuario = self.usuarios.obtener_por_id(str(usuario_id))
        if usuario is None or not usuario.activo:
            raise UnauthorizedException("La cuenta no está activa.")

        verificar_bloqueo(usuario.email)
        if not verify_password(password_actual, usuario.password_hash):
            registrar_intento_fallido(usuario.email)
            raise BusinessException("La contraseña actual no es correcta.")
        if password_nueva == password_actual:
            raise BusinessException("La nueva contraseña debe ser distinta de la actual.")

        limpiar_intentos(usuario.email)
        usuario.password_hash = hash_password(password_nueva)
        usuario.must_change_password = False
        usuario.updated_at = func.now()
        return self._emitir_tokens(usuario)

    def _emitir_tokens(self, usuario: AppUser) -> TokenResponse:
        roles = self._roles_de(usuario)
        rol_principal = self._rol_principal(roles)
        institucion = self._institucion_de(usuario, roles)
        subject = str(usuario.id)
        claims = {"roles": roles, "institucion_id": str(institucion.id) if institucion else None}
        return TokenResponse(
            access_token=create_access_token(subject, rol_principal, claims),
            refresh_token=create_refresh_token(subject, rol_principal),
            rol=rol_principal,
            roles=roles,
            institucion_id=institucion.id if institucion else None,
            institucion_nombre=institucion.name if institucion else None,
            debe_cambiar_password=bool(usuario.must_change_password),
            permisos=sorted(self.permisos_de(usuario, roles)),
        )

    def permisos_de(self, usuario: AppUser, roles: list[str]) -> frozenset[str]:
        """Permisos por componente; el staff sin universidad es superadmin solo si es admin."""
        institucion_id = usuario.institution_id
        if institucion_id is None and "platform_admin" not in roles:
            institucion_id = INSTITUCION_POR_DEFECTO_ID
        return permisos_de_usuario(self.db, usuario.id, roles, institucion_id)

    def _institucion_de(self, usuario: AppUser, roles: list[str]) -> Institution | None:
        if {"platform_admin", "moderator"} & set(roles):
            institucion_id = usuario.institution_id
        elif "candidate" in roles:
            perfil = self.db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == usuario.id))
            institucion_id = (perfil.institution_id or INSTITUCION_POR_DEFECTO_ID) if perfil else None
        else:
            institucion_id = None
        return self.db.get(Institution, institucion_id) if institucion_id else None

    def _institucion_cliente(self, institucion_id) -> Institution:
        institucion = self.db.get(Institution, institucion_id)
        if institucion is None or not institucion.is_tenant:
            raise ConflictException("La universidad indicada no está habilitada en la plataforma.")
        return institucion

    def _roles_de(self, usuario: AppUser) -> list[str]:
        return usuario.nombres_roles or (
            ["empresa"] if self.usuarios.pertenece_a_empresa(usuario.id) else ["candidate"]
        )

    def _rol_principal(self, roles: list[str]) -> str:
        return next((r for r in _ROL_PRIORIDAD if r in roles), roles[0] if roles else "candidate")

    def _registrar_login_attempt(self, correo: str, usuario: AppUser | None, success: bool) -> None:
        self.db.add(
            LoginAttempt(email=correo.strip().lower(), user_id=usuario.id if usuario else None, success=success)
        )
