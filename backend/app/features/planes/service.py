import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException, ConflictException, ResourceNotFoundException
from app.features.auth.repository import UsuarioRepository
from app.features.bitacora.service import BitacoraService
from app.features.instituciones.schema import ResumenInstitucionResponse
from app.features.instituciones.service import InstitucionService
from app.features.planes import stripe_pagos
from app.features.planes.limites import PLAN_GRATUITO, hoy_bolivia
from app.features.planes.schema import (
    AprobarSolicitudResponse,
    CheckoutResponse,
    ConfirmarPagoResponse,
    InstitucionDisponibleResponse,
    PagoPlanResponse,
    PlanResponse,
    SolicitudUniversidadRequest,
    SolicitudUniversidadResponse,
)
from app.features.roles.schema import CrearUsuarioStaffRequest
from app.features.roles.service import RolesService
from app.models.institucion import Institution, PlanPayment, SaasPlan, UniversitySignupRequest
from app.models.usuario import AppUser
from app.security.tenant import AlcanceStaff

logger = logging.getLogger(__name__)

_DURACION_PAGO = timedelta(days=365)  # los planes se pagan por año


def _plan_dto(plan: SaasPlan) -> PlanResponse:
    return PlanResponse(
        codigo=plan.code,
        nombre=plan.name,
        precio_anual_bs=float(plan.price_bs_year),
        max_egresados=plan.max_graduates,
        max_moderadores=plan.max_moderators,
        reportes=plan.employability_reports,
        marca_propia=plan.custom_branding,
    )


class PlanService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.bitacora = BitacoraService(db)

    # ─── Público: catálogo y solicitud de alta ──────────────────────────────

    def listar_planes(self) -> list[PlanResponse]:
        stmt = select(SaasPlan).where(SaasPlan.audience == "university").order_by(SaasPlan.sort_order)
        return [_plan_dto(plan) for plan in self.db.scalars(stmt)]

    def instituciones_disponibles(self) -> list[InstitucionDisponibleResponse]:
        stmt = select(Institution).where(Institution.is_tenant.is_(False)).order_by(Institution.name)
        return [InstitucionDisponibleResponse(id=i.id, nombre=i.name, ciudad=i.city) for i in self.db.scalars(stmt)]

    def crear_solicitud(self, data: SolicitudUniversidadRequest, ip: str | None) -> SolicitudUniversidadResponse:
        plan = self._plan_de_universidad(data.plan)
        sigla = data.sigla.strip().upper()
        correo = data.responsable_correo.strip().lower()

        if data.institucion_id is not None:
            institucion = self.db.get(Institution, data.institucion_id)
            if institucion is None:
                raise ResourceNotFoundException("La universidad elegida no existe.")
            if institucion.is_tenant:
                raise ConflictException("Esa universidad ya trabaja con EGRESA.")
        self._validar_sigla_libre(sigla, data.institucion_id)
        pendiente = self.db.scalar(
            select(UniversitySignupRequest.id).where(
                UniversitySignupRequest.status == "pending",
                or_(
                    func.upper(UniversitySignupRequest.acronym) == sigla,
                    func.lower(UniversitySignupRequest.contact_email) == correo,
                ),
            )
        )
        if pendiente is not None:
            raise ConflictException("Ya hay una solicitud pendiente para esa universidad o ese correo.")
        if UsuarioRepository(self.db).existe_correo(correo):
            raise ConflictException(
                "Ese correo ya tiene una cuenta en EGRESA. Indicá otro para el administrador de la universidad."
            )

        solicitud = UniversitySignupRequest(
            institution_id=data.institucion_id,
            name=data.nombre.strip(),
            acronym=sigla,
            city=data.ciudad.strip() if data.ciudad else None,
            contact_name=data.responsable_nombre.strip(),
            contact_email=correo,
            contact_phone=data.responsable_telefono.strip() if data.responsable_telefono else None,
            plan_code=plan.code,
        )
        self.db.add(solicitud)
        self.db.flush()
        self.bitacora.registrar(
            modulo="planes",
            accion="solicitud_universidad",
            ip=ip,
            detalles=f"sigla={sigla} plan={plan.code} correo={correo}",
        )
        self.db.commit()
        return self._solicitud_dto(solicitud, plan)

    # ─── Superadmin: revisión de solicitudes ────────────────────────────────

    def listar_solicitudes(self, estado: str | None) -> list[SolicitudUniversidadResponse]:
        stmt = select(UniversitySignupRequest).order_by(UniversitySignupRequest.created_at.desc())
        if estado:
            stmt = stmt.where(UniversitySignupRequest.status == estado)
        planes = {p.code: p for p in self.db.scalars(select(SaasPlan))}
        return [self._solicitud_dto(s, planes[s.plan_code]) for s in self.db.scalars(stmt)]

    def aprobar(
        self, solicitud_id: uuid.UUID, password_admin: str, responsable_id: uuid.UUID, ip: str | None
    ) -> AprobarSolicitudResponse:
        """Vuelve cliente a la universidad y crea su admin con contraseña temporal.

        Un plan pago queda con el pago pendiente (rigen límites del Básico) hasta que la
        universidad lo pague con tarjeta o el superadmin registre un pago manual.
        """
        solicitud = self._solicitud_pendiente(solicitud_id)
        plan = self._plan_de_universidad(solicitud.plan_code)
        self._validar_sigla_libre(solicitud.acronym, solicitud.institution_id)

        if solicitud.institution_id is not None:
            institucion = self.db.get(Institution, solicitud.institution_id)
            if institucion is None or institucion.is_tenant:
                raise ConflictException("La universidad de la solicitud ya no está disponible.")
        else:
            institucion = Institution(
                name=solicitud.name,
                city=solicitud.city,
                country_code="BO",
                institution_type="university",
            )
            self.db.add(institucion)
        institucion.slug = solicitud.acronym.lower()
        institucion.is_tenant = True
        institucion.verification_status = "verified"
        institucion.plan_code = plan.code
        institucion.plan_paid_until = None
        self.db.flush()

        solicitud.institution_id = institucion.id
        solicitud.status = "approved"
        solicitud.reviewed_by = responsable_id
        solicitud.reviewed_at = datetime.now(timezone.utc)
        self.bitacora.registrar(
            modulo="planes",
            accion="aprobar_universidad",
            usuario_id=responsable_id,
            ip=ip,
            detalles=f"sigla={solicitud.acronym} plan={plan.code} institucion={institucion.id}",
        )

        # Crea el admin (con must_change_password) y confirma toda la transacción.
        RolesService(self.db).crear_usuario_staff(
            CrearUsuarioStaffRequest(
                correo=solicitud.contact_email,
                password=password_admin,
                rol="platform_admin",
                institucion_id=institucion.id,
            ),
            responsable_id=responsable_id,
            ip=ip,
            institution_id=None,
        )
        return AprobarSolicitudResponse(
            universidad_id=institucion.id,
            universidad=institucion.name,
            plan=plan.name,
            admin_correo=solicitud.contact_email,
            detalle=(
                "Universidad habilitada. Pasale las credenciales al responsable."
                + (
                    " El plan queda con el pago pendiente hasta que la universidad lo pague con tarjeta"
                    " desde su panel (o registres un pago manual)."
                    if plan.es_pago
                    else ""
                )
            ),
        )

    def rechazar(
        self, solicitud_id: uuid.UUID, motivo: str, responsable_id: uuid.UUID, ip: str | None
    ) -> SolicitudUniversidadResponse:
        solicitud = self._solicitud_pendiente(solicitud_id)
        solicitud.status = "rejected"
        solicitud.rejection_reason = motivo.strip()
        solicitud.reviewed_by = responsable_id
        solicitud.reviewed_at = datetime.now(timezone.utc)
        self.bitacora.registrar(
            modulo="planes",
            accion="rechazar_universidad",
            usuario_id=responsable_id,
            ip=ip,
            detalles=f"sigla={solicitud.acronym} motivo={motivo.strip()}",
        )
        self.db.commit()
        return self._solicitud_dto(solicitud, self._plan_de_universidad(solicitud.plan_code))

    # ─── Superadmin: plan y pago de cada universidad ────────────────────────

    def cambiar_plan(
        self, institution_id: uuid.UUID, codigo: str, responsable_id: uuid.UUID, ip: str | None
    ) -> ResumenInstitucionResponse:
        """Los límites nuevos solo frenan altas futuras: no se borra nada al bajar de plan."""
        institucion = self._cliente(institution_id)
        plan = self._plan_de_universidad(codigo)
        anterior = institucion.plan_code or PLAN_GRATUITO
        institucion.plan_code = plan.code
        self.bitacora.registrar(
            modulo="planes",
            accion="cambiar_plan",
            usuario_id=responsable_id,
            ip=ip,
            detalles=f"institucion={institucion.id} plan_anterior={anterior} plan_nuevo={plan.code}",
        )
        self.db.commit()
        return InstitucionService(self.db).resumen(institucion.id)[0]

    def registrar_pago(
        self, institution_id: uuid.UUID, responsable_id: uuid.UUID, ip: str | None
    ) -> ResumenInstitucionResponse:
        """Pago manual (transferencia, QR, etc.): extiende la vigencia un año."""
        institucion = self._cliente(institution_id)
        plan = self._plan_de_universidad(institucion.plan_code or PLAN_GRATUITO)
        if not plan.es_pago:
            raise BusinessException("El plan Básico es gratuito: no hay pagos que registrar.")
        institucion.plan_paid_until = self._nuevo_vencimiento(institucion)
        self.db.add(
            PlanPayment(
                institution_id=institucion.id,
                plan_code=plan.code,
                amount_bs=plan.price_bs_year,
                method="manual",
                status="paid",
                paid_until=institucion.plan_paid_until,
                created_by=responsable_id,
                paid_at=datetime.now(timezone.utc),
            )
        )
        self.bitacora.registrar(
            modulo="planes",
            accion="registrar_pago",
            usuario_id=responsable_id,
            ip=ip,
            detalles=f"institucion={institucion.id} plan={plan.code} pagado_hasta={institucion.plan_paid_until}",
        )
        self.db.commit()
        return InstitucionService(self.db).resumen(institucion.id)[0]

    def listar_pagos(self, institution_id: uuid.UUID | None) -> list[PagoPlanResponse]:
        """Pagos acreditados, del más reciente al más antiguo. None = todas las universidades."""
        stmt = (
            select(PlanPayment, Institution.name, SaasPlan.name, AppUser.email)
            .join(Institution, Institution.id == PlanPayment.institution_id)
            .join(SaasPlan, SaasPlan.code == PlanPayment.plan_code)
            .outerjoin(AppUser, AppUser.id == PlanPayment.created_by)
            .where(PlanPayment.status == "paid")
            .order_by(PlanPayment.paid_at.desc())
            .limit(500)
        )
        if institution_id is not None:
            stmt = stmt.where(PlanPayment.institution_id == institution_id)
        return [
            PagoPlanResponse(
                id=pago.id,
                universidad_id=pago.institution_id,
                universidad=universidad,
                plan=pago.plan_code,
                plan_nombre=plan_nombre,
                monto_bs=float(pago.amount_bs),
                metodo=pago.method,
                pagado_hasta=pago.paid_until,
                fecha=pago.paid_at or pago.created_at,
                registrado_por=correo,
            )
            for pago, universidad, plan_nombre, correo in self.db.execute(stmt)
        ]

    # ─── Admin de la universidad: pago con tarjeta (Stripe Checkout) ────────

    def iniciar_pago(self, alcance: AlcanceStaff) -> CheckoutResponse:
        """Crea la sesión de Stripe Checkout por un año del plan contratado."""
        if alcance.es_global:
            raise BusinessException("El pago con tarjeta lo hace el administrador de cada universidad.")
        institucion = self._cliente(alcance.institution_id)
        plan = self._plan_de_universidad(institucion.plan_code or PLAN_GRATUITO)
        if not plan.es_pago:
            raise BusinessException("El plan Básico es gratuito: no hay nada que pagar.")
        usuario = self.db.get(AppUser, alcance.usuario.id_usuario)

        pago = PlanPayment(
            institution_id=institucion.id,
            plan_code=plan.code,
            amount_bs=plan.price_bs_year,
            method="stripe",
            status="pending",
            created_by=usuario.id,
        )
        self.db.add(pago)
        self.db.flush()
        vence = self._nuevo_vencimiento(institucion)
        sesion = stripe_pagos.crear_checkout(
            monto_bs=plan.price_bs_year,
            producto=f"EGRESA · Plan {plan.name} (1 año)",
            descripcion=f"{institucion.name}: plan al día hasta el {vence:%d/%m/%Y}.",
            correo=usuario.email,
            referencia=str(institucion.id),
            metadata={"pago_id": str(pago.id), "institucion_id": str(institucion.id), "plan": plan.code},
        )
        pago.stripe_session_id = sesion.id
        self.db.commit()
        return CheckoutResponse(url=sesion.url)

    def confirmar_pago(self, session_id: str, alcance: AlcanceStaff) -> ConfirmarPagoResponse:
        """Al volver de Stripe: consulta la sesión y acredita el pago si ya se cobró."""
        pago = self._pago_stripe(session_id)
        if pago is None or (not alcance.es_global and pago.institution_id != alcance.institution_id):
            raise ResourceNotFoundException("No se encontró el pago.")
        if pago.status == "pending":
            self._aplicar_sesion(pago, stripe_pagos.obtener_sesion(session_id))
        plan = self.db.get(SaasPlan, pago.plan_code)
        return ConfirmarPagoResponse(estado=pago.status, plan_nombre=plan.name, pagado_hasta=pago.paid_until)

    def procesar_webhook(self, payload: bytes, firma: str | None) -> None:
        evento = stripe_pagos.leer_evento(payload, firma)
        if evento.type not in (
            "checkout.session.completed",
            "checkout.session.async_payment_succeeded",
            "checkout.session.expired",
        ):
            return
        sesion = evento.data.object
        pago = self._pago_stripe(sesion.id)
        if pago is not None and pago.status == "pending":
            self._aplicar_sesion(pago, sesion)

    def _aplicar_sesion(self, pago: PlanPayment, sesion) -> None:
        """Acredita un pago pendiente si Stripe ya lo cobró (o lo da por vencido).

        El pago fija el plan por el que se pagó, aunque el superadmin lo haya cambiado
        mientras el administrador estaba en Stripe.
        """
        if sesion.status == "expired":
            pago.status = "expired"
            self.db.commit()
            return
        if sesion.payment_status != "paid":
            return
        if sesion.currency != stripe_pagos.MONEDA or sesion.amount_total != stripe_pagos.centavos(pago.amount_bs):
            logger.error("Monto de Stripe distinto al del plan: pago=%s sesion=%s", pago.id, sesion.id)
            raise BusinessException(
                "El monto cobrado por Stripe no coincide con el del plan. Revisalo en el dashboard de Stripe."
            )
        institucion = self.db.get(Institution, pago.institution_id)
        institucion.plan_code = pago.plan_code
        institucion.plan_paid_until = self._nuevo_vencimiento(institucion)
        pago.status = "paid"
        pago.paid_at = datetime.now(timezone.utc)
        pago.paid_until = institucion.plan_paid_until
        self.bitacora.registrar(
            modulo="planes",
            accion="pago_stripe",
            usuario_id=pago.created_by,
            detalles=(
                f"institucion={institucion.id} plan={pago.plan_code} monto_bs={pago.amount_bs} "
                f"pagado_hasta={pago.paid_until} sesion={sesion.id}"
            ),
        )
        self.db.commit()

    # ─── Auxiliares ─────────────────────────────────────────────────────────

    def _pago_stripe(self, session_id: str) -> PlanPayment | None:
        # Bloquea la fila: el webhook y la confirmación al volver pueden llegar a la vez.
        return self.db.scalar(
            select(PlanPayment).where(PlanPayment.stripe_session_id == session_id).with_for_update()
        )

    @staticmethod
    def _nuevo_vencimiento(institucion: Institution) -> date:
        """Un año más desde hoy o desde el vencimiento actual, si todavía no llegó."""
        hoy = hoy_bolivia()
        desde = max(hoy, institucion.plan_paid_until) if institucion.plan_paid_until else hoy
        return desde + _DURACION_PAGO

    def _plan_de_universidad(self, codigo: str) -> SaasPlan:
        plan = self.db.get(SaasPlan, codigo)
        if plan is None or plan.audience != "university":
            raise BusinessException("El plan indicado no existe.")
        return plan

    def _validar_sigla_libre(self, sigla: str, institucion_propia: uuid.UUID | None) -> None:
        stmt = select(Institution.id).where(Institution.slug == sigla.lower())
        if institucion_propia is not None:
            stmt = stmt.where(Institution.id != institucion_propia)
        if self.db.scalar(stmt) is not None:
            raise ConflictException(f"Ya hay una universidad registrada con la sigla {sigla.upper()}.")

    def _solicitud_pendiente(self, solicitud_id: uuid.UUID) -> UniversitySignupRequest:
        solicitud = self.db.get(UniversitySignupRequest, solicitud_id)
        if solicitud is None:
            raise ResourceNotFoundException("No se encontró la solicitud.")
        if solicitud.status != "pending":
            raise ConflictException("La solicitud ya fue revisada.")
        return solicitud

    def _cliente(self, institution_id: uuid.UUID) -> Institution:
        institucion = self.db.get(Institution, institution_id)
        if institucion is None or not institucion.is_tenant:
            raise ResourceNotFoundException("No se encontró la universidad.")
        return institucion

    @staticmethod
    def _solicitud_dto(solicitud: UniversitySignupRequest, plan: SaasPlan) -> SolicitudUniversidadResponse:
        return SolicitudUniversidadResponse(
            id=solicitud.id,
            institucion_id=solicitud.institution_id,
            nombre=solicitud.name,
            sigla=solicitud.acronym,
            ciudad=solicitud.city,
            responsable_nombre=solicitud.contact_name,
            responsable_correo=solicitud.contact_email,
            responsable_telefono=solicitud.contact_phone,
            plan=plan.code,
            plan_nombre=plan.name,
            estado=solicitud.status,
            motivo_rechazo=solicitud.rejection_reason,
            fecha=solicitud.created_at,
        )
