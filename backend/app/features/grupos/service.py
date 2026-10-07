"""Grupos de usuarios y privilegios por componente de la interfaz (requisito general 2)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException, ConflictException, ResourceNotFoundException
from app.features.bitacora.service import BitacoraService
from app.features.grupos.schema import (
    CatalogoPermisosResponse,
    ComponenteResponse,
    GrupoResponse,
    GuardarGrupoRequest,
    MiembroGrupo,
    PersonalResponse,
)
from app.models.grupo import UserGroup, UserGroupMember, UserGroupPermission
from app.models.institucion import Institution
from app.models.usuario import AppUser, Role, UserRole
from app.security.permisos import ADMIN, CATALOGO, COMPONENTES, MODERADOR, SIEMPRE_ADMIN, permisos_de_usuario
from app.security.tenant import AlcanceStaff

_ROLES_STAFF = (ADMIN, MODERADOR)


class GrupoService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.bitacora = BitacoraService(db)

    def catalogo(self) -> CatalogoPermisosResponse:
        return CatalogoPermisosResponse(
            componentes=[
                ComponenteResponse(
                    codigo=c.codigo,
                    tipo=c.tipo,
                    modulo=c.modulo,
                    nombre=c.nombre,
                    descripcion=c.descripcion,
                    por_defecto=sorted(c.por_defecto),
                    asignable_a=sorted(c.asignable_a),
                )
                for c in CATALOGO
            ],
            siempre_admin=sorted(SIEMPRE_ADMIN),
        )

    def listar(self, alcance: AlcanceStaff, institucion_id: uuid.UUID | None = None) -> list[GrupoResponse]:
        stmt = select(UserGroup).order_by(UserGroup.name)
        destino = self._universidad(alcance, institucion_id, obligatoria=False)
        if destino is not None:
            stmt = stmt.where(UserGroup.institution_id == destino)
        return self._a_dtos(list(self.db.scalars(stmt)))

    def personal(self, alcance: AlcanceStaff, institucion_id: uuid.UUID | None) -> list[PersonalResponse]:
        """Admins y moderadores de la universidad, con sus grupos y lo que ven hoy."""
        destino = self._universidad(alcance, institucion_id)
        roles = self._roles_staff(destino)
        grupos_por_usuario: dict[uuid.UUID, list[str]] = {}
        filas = self.db.execute(
            select(UserGroupMember.user_id, UserGroup.name)
            .join(UserGroup, UserGroup.id == UserGroupMember.group_id)
            .where(UserGroup.institution_id == destino)
            .order_by(UserGroup.name)
        )
        for user_id, nombre in filas:
            grupos_por_usuario.setdefault(user_id, []).append(nombre)
        usuarios = self.db.scalars(
            select(AppUser).where(AppUser.id.in_(roles.keys())).order_by(AppUser.email)
        ).all()
        return [
            PersonalResponse(
                id=u.id,
                correo=u.email,
                rol=roles[u.id],
                grupos=grupos_por_usuario.get(u.id, []),
                permisos=sorted(permisos_de_usuario(self.db, u.id, [roles[u.id]], destino)),
            )
            for u in usuarios
        ]

    def crear(self, data: GuardarGrupoRequest, alcance: AlcanceStaff, ip: str | None) -> GrupoResponse:
        destino = self._universidad(alcance, data.institucion_id)
        grupo = UserGroup(institution_id=destino, name="", description=None)
        self._aplicar(grupo, data, destino)
        self.db.add(grupo)
        self.db.flush()
        self._registrar("crear_grupo", grupo, alcance, ip)
        self.db.commit()
        return self._a_dtos([grupo])[0]

    def actualizar(
        self, grupo_id: uuid.UUID, data: GuardarGrupoRequest, alcance: AlcanceStaff, ip: str | None
    ) -> GrupoResponse:
        grupo = self._obtener(grupo_id, alcance)
        self._aplicar(grupo, data, grupo.institution_id)
        grupo.updated_at = func.now()
        self.db.flush()
        self._registrar("editar_grupo", grupo, alcance, ip)
        self.db.commit()
        self.db.refresh(grupo)
        return self._a_dtos([grupo])[0]

    def eliminar(self, grupo_id: uuid.UUID, alcance: AlcanceStaff, ip: str | None) -> None:
        grupo = self._obtener(grupo_id, alcance)
        self._registrar("eliminar_grupo", grupo, alcance, ip)
        self.db.delete(grupo)
        self.db.commit()

    # --- Reglas -------------------------------------------------------------------------

    def _aplicar(self, grupo: UserGroup, data: GuardarGrupoRequest, destino: uuid.UUID) -> None:
        nombre = " ".join(data.nombre.split())
        if len(nombre) < 3:
            raise BusinessException("El nombre del grupo debe tener al menos 3 caracteres.")
        mismo_nombre = select(UserGroup.id).where(
            UserGroup.institution_id == destino, func.lower(UserGroup.name) == nombre.lower()
        )
        if grupo.id is not None:
            mismo_nombre = mismo_nombre.where(UserGroup.id != grupo.id)
        if self.db.scalar(mismo_nombre) is not None:
            raise ConflictException(f"Ya existe un grupo llamado «{nombre}» en esta universidad.")

        desconocidos = sorted(set(data.permisos) - set(COMPONENTES))
        if desconocidos:
            raise BusinessException(f"Componentes desconocidos: {', '.join(desconocidos)}.")

        miembros = set(data.miembros)
        if miembros - set(self._roles_staff(destino)):
            raise BusinessException(
                "Solo los administradores y moderadores de la universidad pueden pertenecer a un grupo."
            )

        grupo.name = nombre
        grupo.description = (data.descripcion or "").strip() or None
        # Se agrega y quita solo la diferencia: reinsertar la misma clave en un flush choca.
        permisos = set(data.permisos)
        grupo.permisos = [p for p in grupo.permisos if p.permission_code in permisos] + [
            UserGroupPermission(permission_code=c)
            for c in sorted(permisos - {p.permission_code for p in grupo.permisos})
        ]
        grupo.miembros = [m for m in grupo.miembros if m.user_id in miembros] + [
            UserGroupMember(user_id=u) for u in sorted(miembros - {m.user_id for m in grupo.miembros})
        ]

    def _universidad(
        self, alcance: AlcanceStaff, institucion_id: uuid.UUID | None, obligatoria: bool = True
    ) -> uuid.UUID | None:
        """El admin de una universidad siempre opera en la suya; el superadmin elige."""
        if not alcance.es_global:
            return alcance.institution_id
        if institucion_id is None:
            if obligatoria:
                raise BusinessException("Elegí la universidad del grupo.")
            return None
        institucion = self.db.get(Institution, institucion_id)
        if institucion is None or not institucion.is_tenant:
            raise ConflictException("La universidad indicada no está habilitada en la plataforma.")
        return institucion.id

    def _obtener(self, grupo_id: uuid.UUID, alcance: AlcanceStaff) -> UserGroup:
        grupo = self.db.get(UserGroup, grupo_id)
        if grupo is None or (not alcance.es_global and grupo.institution_id != alcance.institution_id):
            raise ResourceNotFoundException("No se encontró el grupo.")
        return grupo

    def _roles_staff(self, institucion_id: uuid.UUID) -> dict[uuid.UUID, str]:
        """Rol de cada admin/moderador activo de la universidad (admin tiene prioridad)."""
        filas = self.db.execute(
            select(AppUser.id, Role.name)
            .join(UserRole, UserRole.user_id == AppUser.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                AppUser.institution_id == institucion_id,
                AppUser.deleted_at.is_(None),
                Role.name.in_(_ROLES_STAFF),
            )
        )
        roles: dict[uuid.UUID, str] = {}
        for user_id, rol in filas:
            if roles.get(user_id) != ADMIN:
                roles[user_id] = rol
        return roles

    def _registrar(self, accion: str, grupo: UserGroup, alcance: AlcanceStaff, ip: str | None) -> None:
        self.bitacora.registrar(
            modulo="grupos",
            accion=accion,
            usuario_id=alcance.usuario.id_usuario,
            ip=ip,
            detalles=(
                f"grupo={grupo.name} institucion={grupo.institution_id} "
                f"permisos={len(grupo.permisos)} miembros={len(grupo.miembros)}"
            ),
        )

    def _a_dtos(self, grupos: list[UserGroup]) -> list[GrupoResponse]:
        usuarios_ids = {m.user_id for g in grupos for m in g.miembros}
        instituciones = {g.institution_id for g in grupos}
        correos = (
            dict(self.db.execute(select(AppUser.id, AppUser.email).where(AppUser.id.in_(usuarios_ids))).all())
            if usuarios_ids
            else {}
        )
        roles: dict[uuid.UUID, str] = {}
        for institucion_id in instituciones:
            roles.update(self._roles_staff(institucion_id))
        consulta = select(Institution.id, Institution.name).where(Institution.id.in_(instituciones))
        nombres = dict(self.db.execute(consulta).all()) if instituciones else {}
        return [
            GrupoResponse(
                id=g.id,
                nombre=g.name,
                descripcion=g.description,
                institucion_id=g.institution_id,
                institucion=nombres.get(g.institution_id),
                permisos=sorted(p.permission_code for p in g.permisos),
                miembros=sorted(
                    (
                        MiembroGrupo(id=m.user_id, correo=correos.get(m.user_id, ""), rol=roles.get(m.user_id, ""))
                        for m in g.miembros
                    ),
                    key=lambda m: m.correo,
                ),
                actualizado=g.updated_at,
            )
            for g in grupos
        ]
