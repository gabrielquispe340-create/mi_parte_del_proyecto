import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, literal_column, select, union_all
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException, ForbiddenException, ResourceNotFoundException
from app.core.tenancy import INSTITUCION_POR_DEFECTO_ID, condicion_institucion
from app.features.instituciones.schema import (
    ActividadPanel,
    InstitucionEmpresaResponse,
    PanelAdminResponse,
    PendientesPanel,
    PlanDeUniversidadResponse,
    ResumenInstitucionResponse,
    TotalesPanel,
)
from app.features.planes.limites import planes_por_codigo, resolver_plan
from app.features.vacantes.repository import empresa_vinculada_a
from app.models.candidato import CandidateProfile
from app.models.empresa import Company, CompanyMember
from app.models.institucion import CompanyInstitution, Institution, SaasPlan, UniversitySignupRequest
from app.models.postulacion import Application
from app.models.seguridad import AuditLog
from app.models.usuario import AppUser, Role, UserRole
from app.models.vacante import JobPosting, JobStatus
from app.security.tenant import usuarios_de_institucion

# Bolivia no tiene horario de verano: UTC-4 todo el año.
_ZONA_BOLIVIA = timezone(timedelta(hours=-4))
_ACCIONES_DE_ACCESO = ("login", "login_fallido")
_LIMITE_ACTIVIDAD = 8


def _sigla(institucion: Institution) -> str | None:
    return institucion.slug.upper() if institucion.slug else None


class InstitucionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _tenants(self, institution_id: uuid.UUID | None = None) -> list[Institution]:
        stmt = select(Institution).where(Institution.is_tenant.is_(True)).order_by(Institution.name)
        if institution_id is not None:
            stmt = stmt.where(Institution.id == institution_id)
        return list(self.db.scalars(stmt))

    def _empresa_de(self, usuario_id: uuid.UUID) -> Company:
        empresa = self.db.scalar(
            select(Company)
            .join(CompanyMember, CompanyMember.company_id == Company.id)
            .where(CompanyMember.user_id == usuario_id)
        )
        if empresa is None:
            raise ForbiddenException("El usuario no pertenece a ninguna empresa.")
        return empresa

    # ─── Autogestión de la empresa ──────────────────────────────────────────

    def instituciones_de_empresa(self, usuario_id: uuid.UUID) -> list[InstitucionEmpresaResponse]:
        empresa = self._empresa_de(usuario_id)
        vinculos = {
            v.institution_id: v
            for v in self.db.scalars(select(CompanyInstitution).where(CompanyInstitution.company_id == empresa.id))
        }
        resultado = []
        for inst in self._tenants():
            vinculo = vinculos.get(inst.id)
            resultado.append(
                InstitucionEmpresaResponse(
                    id=inst.id,
                    nombre=inst.name,
                    sigla=_sigla(inst),
                    ciudad=inst.city,
                    estado=vinculo.status if vinculo else None,
                    motivo_rechazo=vinculo.rejection_reason if vinculo else None,
                    fecha_solicitud=vinculo.requested_at if vinculo else None,
                )
            )
        return resultado

    def solicitar_acceso(self, usuario_id: uuid.UUID, institution_id: uuid.UUID) -> InstitucionEmpresaResponse:
        empresa = self._empresa_de(usuario_id)
        institucion = self.db.get(Institution, institution_id)
        if institucion is None or not institucion.is_tenant:
            raise ResourceNotFoundException("La universidad no existe o no está habilitada en la plataforma.")

        vinculo = self.db.get(CompanyInstitution, (empresa.id, institution_id))
        if vinculo is None:
            vinculo = CompanyInstitution(company_id=empresa.id, institution_id=institution_id, status="pending")
            self.db.add(vinculo)
        elif vinculo.status == "rejected":
            vinculo.status = "pending"
            vinculo.rejection_reason = None
            vinculo.reviewed_by = None
            vinculo.reviewed_at = None
            vinculo.requested_at = func.now()
        elif vinculo.status == "suspended":
            raise BusinessException("Tu acceso a esta universidad está suspendido; contactá a su administración.")
        self.db.commit()
        self.db.refresh(vinculo)

        return InstitucionEmpresaResponse(
            id=institucion.id,
            nombre=institucion.name,
            sigla=_sigla(institucion),
            ciudad=institucion.city,
            estado=vinculo.status,
            motivo_rechazo=vinculo.rejection_reason,
            fecha_solicitud=vinculo.requested_at,
        )

    # ─── Resumen por universidad (panel de administración) ──────────────────

    def resumen(self, institution_id: uuid.UUID | None) -> list[ResumenInstitucionResponse]:
        """Métricas por tenant. El superadmin (None) ve todas; el admin de una universidad, solo la suya."""
        conteos = self._conteos_por_tenant(institution_id)
        planes = planes_por_codigo(self.db)
        return [self._resumen_de(inst, conteos, planes) for inst in self._tenants(institution_id)]

    def _conteos_por_tenant(self, institution_id: uuid.UUID | None) -> dict[tuple[str, uuid.UUID, str], int]:
        """(métrica, universidad, estado) -> cantidad, en una sola consulta.

        La base está lejos (Supabase): una consulta por métrica y universidad hacía que el
        panel tardara varios segundos. Los egresados sin universidad cuentan para la UAGRM.
        """
        sin_estado = literal_column("''")
        egresados = select(
            literal_column("'egresados'"),
            CandidateProfile.institution_id,
            CandidateProfile.verification_status,
            func.count(),
        ).group_by(CandidateProfile.institution_id, CandidateProfile.verification_status)
        # Mismo criterio que la lista de Validación de egresados (EgresadoRepository).
        por_validar = (
            select(literal_column("'por_validar'"), CandidateProfile.institution_id, sin_estado, func.count())
            .where(
                CandidateProfile.verification_status.in_(["pending", "in_review"]),
                CandidateProfile.document_number.is_not(None),
            )
            .group_by(CandidateProfile.institution_id)
        )
        postulaciones = (
            select(literal_column("'postulaciones'"), CandidateProfile.institution_id, sin_estado, func.count())
            .select_from(Application)
            .join(CandidateProfile, CandidateProfile.id == Application.candidate_id)
            .group_by(CandidateProfile.institution_id)
        )
        empresas = select(
            literal_column("'empresas'"),
            CompanyInstitution.institution_id,
            CompanyInstitution.status,
            func.count(),
        ).group_by(CompanyInstitution.institution_id, CompanyInstitution.status)
        vacantes = (
            select(literal_column("'vacantes'"), CompanyInstitution.institution_id, sin_estado, func.count())
            .select_from(JobPosting)
            .join(CompanyInstitution, CompanyInstitution.company_id == JobPosting.company_id)
            .where(CompanyInstitution.status == "approved", JobPosting.status == JobStatus.PUBLISHED.value)
            .group_by(CompanyInstitution.institution_id)
        )
        moderadores = (
            select(literal_column("'moderadores'"), AppUser.institution_id, sin_estado, func.count())
            .select_from(AppUser)
            .join(UserRole, UserRole.user_id == AppUser.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.name == "moderator", AppUser.deleted_at.is_(None))
            .group_by(AppUser.institution_id)
        )
        if institution_id is not None:
            de_la_inst = condicion_institucion(CandidateProfile.institution_id, institution_id)
            egresados = egresados.where(de_la_inst)
            por_validar = por_validar.where(de_la_inst)
            postulaciones = postulaciones.where(de_la_inst)
            empresas = empresas.where(CompanyInstitution.institution_id == institution_id)
            vacantes = vacantes.where(CompanyInstitution.institution_id == institution_id)
            moderadores = moderadores.where(AppUser.institution_id == institution_id)

        conteos: dict[tuple[str, uuid.UUID, str], int] = defaultdict(int)
        consulta = union_all(egresados, por_validar, postulaciones, empresas, vacantes, moderadores)
        for metrica, inst, estado, cantidad in self.db.execute(consulta):
            conteos[(metrica, inst or INSTITUCION_POR_DEFECTO_ID, estado)] += cantidad
        return conteos

    def _resumen_de(
        self,
        inst: Institution,
        conteos: dict[tuple[str, uuid.UUID, str], int],
        planes: dict[str, SaasPlan],
    ) -> ResumenInstitucionResponse:
        def contar(metrica: str, estado: str = "") -> int:
            return conteos.get((metrica, inst.id, estado), 0)

        plan = resolver_plan(inst, planes)

        return ResumenInstitucionResponse(
            id=inst.id,
            nombre=inst.name,
            sigla=_sigla(inst),
            ciudad=inst.city,
            egresados_total=sum(n for (m, i, _), n in conteos.items() if m == "egresados" and i == inst.id),
            egresados_verificados=contar("egresados", "verified"),
            egresados_pendientes=contar("por_validar"),
            empresas_aprobadas=contar("empresas", "approved"),
            empresas_pendientes=contar("empresas", "pending"),
            vacantes_publicadas=contar("vacantes"),
            postulaciones=contar("postulaciones"),
            moderadores=contar("moderadores"),
            plan=PlanDeUniversidadResponse(
                codigo=plan.contratado.code,
                nombre=plan.contratado.name,
                precio_anual_bs=float(plan.contratado.price_bs_year),
                estado_pago=plan.estado_pago,
                pago_hasta=inst.plan_paid_until,
                vigente=plan.vigente.code,
                max_egresados=plan.vigente.max_graduates,
                max_moderadores=plan.vigente.max_moderators,
                reportes=plan.vigente.employability_reports,
                marca_propia=plan.vigente.custom_branding,
            ),
        )

    # ─── Panel de inicio del admin ──────────────────────────────────────────

    def panel(self, institution_id: uuid.UUID | None) -> PanelAdminResponse:
        universidades = self.resumen(institution_id)
        cifras = self._cifras_del_panel(institution_id)
        return PanelAdminResponse(
            universidades=universidades,
            totales=TotalesPanel(
                egresados=sum(u.egresados_total for u in universidades),
                egresados_verificados=sum(u.egresados_verificados for u in universidades),
                empresas_habilitadas=cifras["empresas_habilitadas"],
                vacantes_publicadas=cifras["vacantes_publicadas"],
                postulaciones=sum(u.postulaciones for u in universidades),
            ),
            pendientes=PendientesPanel(
                egresados=sum(u.egresados_pendientes for u in universidades),
                empresas=cifras["empresas_pendientes"],
                vacantes=cifras["vacantes_por_moderar"],
                universidades=cifras.get("universidades_pendientes", 0),
            ),
            accesos_hoy=cifras["accesos_hoy"],
            accesos_fallidos_hoy=cifras["accesos_fallidos_hoy"],
            actividad=self._actividad(institution_id),
        )

    def _cifras_del_panel(self, institution_id: uuid.UUID | None) -> dict[str, int]:
        """Las cifras que no salen de sumar universidades, en una sola consulta.

        Los pendientes usan los mismos criterios que la pantalla a la que lleva cada tarjeta
        (filtro "Pendientes" de Gestión de empresas, Moderación de ofertas) para que los
        números coincidan: una empresa con la cuenta suspendida no cuenta como pendiente.
        """
        inicio_hoy = datetime.now(_ZONA_BOLIVIA).replace(hour=0, minute=0, second=0, microsecond=0)
        accesos = select(func.count(AuditLog.id)).where(AuditLog.action == "login", AuditLog.created_at >= inicio_hoy)
        fallidos = select(func.count(AuditLog.id)).where(
            AuditLog.action == "login_fallido", AuditLog.created_at >= inicio_hoy
        )
        vacantes_por_moderar = select(func.count(JobPosting.id)).where(
            JobPosting.status == JobStatus.PENDING_REVIEW.value
        )
        vinculo_aprobado = [CompanyInstitution.status == "approved"]

        empresa_activa = Company.account_status != "suspended"
        if institution_id is None:
            empresas_pendientes = select(func.count(Company.id)).where(
                Company.verification_status.in_(["pending", "in_review"]), empresa_activa
            )
        else:
            empresas_pendientes = (
                select(func.count())
                .select_from(CompanyInstitution)
                .join(Company, Company.id == CompanyInstitution.company_id)
                .where(
                    CompanyInstitution.institution_id == institution_id,
                    CompanyInstitution.status == "pending",
                    empresa_activa,
                )
            )
            vacantes_por_moderar = vacantes_por_moderar.where(
                empresa_vinculada_a(institution_id, ("approved", "pending"))
            )
            vinculo_aprobado.append(CompanyInstitution.institution_id == institution_id)
            del_tenant = AuditLog.user_id.in_(usuarios_de_institucion(institution_id))
            accesos = accesos.where(del_tenant)
            fallidos = fallidos.where(del_tenant)

        # Una empresa o vacante presente en varias universidades se cuenta una sola vez.
        empresas_habilitadas = select(func.count(func.distinct(CompanyInstitution.company_id))).where(
            *vinculo_aprobado
        )
        visible = (
            select(CompanyInstitution.company_id)
            .where(CompanyInstitution.company_id == JobPosting.company_id, *vinculo_aprobado)
            .exists()
        )
        vacantes_publicadas = select(func.count(JobPosting.id)).where(
            JobPosting.status == JobStatus.PUBLISHED.value, visible
        )

        subconsultas = {
            "empresas_habilitadas": empresas_habilitadas,
            "vacantes_publicadas": vacantes_publicadas,
            "empresas_pendientes": empresas_pendientes,
            "vacantes_por_moderar": vacantes_por_moderar,
            "accesos_hoy": accesos,
            "accesos_fallidos_hoy": fallidos,
        }
        if institution_id is None:
            # Las altas de universidades las decide solo el superadmin.
            subconsultas["universidades_pendientes"] = select(func.count(UniversitySignupRequest.id)).where(
                UniversitySignupRequest.status == "pending"
            )
        fila = self.db.execute(
            select(*(sub.scalar_subquery().label(nombre) for nombre, sub in subconsultas.items()))
        ).one()
        return {nombre: valor or 0 for nombre, valor in fila._mapping.items()}

    def _actividad(self, institution_id: uuid.UUID | None) -> list[ActividadPanel]:
        """Últimas acciones de gestión; los inicios de sesión se resumen aparte en accesos_hoy."""
        stmt = (
            select(AuditLog, AppUser.email)
            .outerjoin(AppUser, AppUser.id == AuditLog.user_id)
            .where(AuditLog.action.not_in(_ACCIONES_DE_ACCESO))
            .order_by(AuditLog.created_at.desc())
            .limit(_LIMITE_ACTIVIDAD)
        )
        if institution_id is not None:
            stmt = stmt.where(AuditLog.user_id.in_(usuarios_de_institucion(institution_id)))
        return [
            ActividadPanel(
                fecha=log.fecha,
                usuario=correo,
                modulo=log.entity_type,
                accion=log.action,
                detalles=log.detalles,
                resultado=log.resultado,
            )
            for log, correo in self.db.execute(stmt)
        ]
