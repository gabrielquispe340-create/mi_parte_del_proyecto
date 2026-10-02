import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.common.exceptions import ResourceNotFoundException
from app.features.empresa.repository import EmpresaRepository
from app.features.empresa.schema import EmpresaResponse, InstitucionDeEmpresa
from app.models.empresa import Company
from app.models.institucion import CompanyInstitution
from app.shared.email_service import EmailService

_MAPA_ESTADO = {
    "pending": "PENDIENTE",
    "in_review": "PENDIENTE",
    "verified": "VERIFICADA",
    "rejected": "RECHAZADA",
}

_MAPA_ESTADO_VINCULO = {
    "pending": "PENDIENTE",
    "approved": "VERIFICADA",
    "rejected": "RECHAZADA",
    "suspended": "SUSPENDIDA",
}

# NOTA sobre limitaciones del esquema real (ver también app/models/empresa.py):
# - notifications_enabled / applications_enabled: no existen como columnas en `company`
#   ni en ninguna otra tabla del esquema real. No hay dónde persistirlas sin agregar
#   columnas (regla de oro: no tocar el esquema de Supabase). Se aceptan los cambios
#   vía el endpoint de configuración y se devuelven en la respuesta, pero NO sobreviven
#   a un reinicio del proceso (se guardan solo en memoria, por instancia de Company
#   dentro de la sesión actual). Limitación documentada y aceptada para esta pasada.
# - legal_representative: tampoco existe columna; se acepta en el registro y se ignora.
# - "baja lógica" (deleted_at): no existe; se reutiliza account_status='suspended'
#   como equivalente más cercano, por lo que eliminar_logico/restaurar quedan
#   funcionalmente equivalentes a suspender/reactivar.
#
# Multitenant: las empresas son globales. Un superadmin (institution_id=None) actúa
# sobre la empresa en sí; el admin de una universidad actúa solo sobre el vínculo
# empresa-universidad (company_institution), sin afectar a las demás universidades.


def _a_dto(
    empresa: Company,
    motivo_rechazo: str | None,
    vinculos: list[CompanyInstitution],
    vinculo_tenant: CompanyInstitution | None = None,
) -> EmpresaResponse:
    estado = _MAPA_ESTADO.get(empresa.verification_status)
    if empresa.account_status == "suspended":
        estado = "SUSPENDIDA"
    activo = empresa.account_status != "suspended"
    if vinculo_tenant is not None:
        if activo:
            estado = _MAPA_ESTADO_VINCULO.get(vinculo_tenant.status, "PENDIENTE")
            activo = vinculo_tenant.status != "suspended"
        motivo_rechazo = vinculo_tenant.rejection_reason
    return EmpresaResponse(
        id=empresa.id,
        razon_social=empresa.trade_name or empresa.legal_name,
        nit=empresa.tax_id,
        sector=empresa.sector.name if empresa.sector else None,
        tamanio=empresa.company_size,
        direccion=empresa.address,
        telefono=empresa.phone,
        sitio_web=empresa.website,
        descripcion=empresa.description,
        representante_legal=None,
        estado_verificacion=estado or "PENDIENTE",
        motivo_rechazo=motivo_rechazo,
        notificaciones_activas=getattr(empresa, "_notificaciones_activas", True),
        postulaciones_activas=getattr(empresa, "_postulaciones_activas", True),
        activo=activo,
        fecha_registro=empresa.created_at,
        fecha_eliminacion=None,
        instituciones=[
            InstitucionDeEmpresa(
                id=v.institution_id,
                nombre=v.institution.name,
                sigla=v.institution.slug.upper() if v.institution.slug else None,
                estado=v.status,
            )
            for v in vinculos
        ],
    )


class EmpresaService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = EmpresaRepository(db)
        self.email_service = EmailService()

    def _dto(self, empresa: Company, institution_id: uuid.UUID | None = None) -> EmpresaResponse:
        return self._listar_con_motivos([empresa], institution_id)[0]

    def _listar_con_motivos(
        self, empresas: list[Company], institution_id: uuid.UUID | None = None
    ) -> list[EmpresaResponse]:
        ids = [empresa.id for empresa in empresas]
        motivos = self.repo.ultimos_motivos_rechazo(ids)
        vinculos = self.repo.vinculos_de(ids)
        resultado = []
        for empresa in empresas:
            propios = vinculos.get(empresa.id, [])
            vinculo_tenant = None
            if institution_id is not None:
                # El admin de una universidad solo ve el vínculo con su propia universidad.
                propios = [v for v in propios if v.institution_id == institution_id]
                vinculo_tenant = propios[0] if propios else None
            resultado.append(_a_dto(empresa, motivos.get(empresa.id), propios, vinculo_tenant))
        return resultado

    def listar_pendientes(self, institution_id: uuid.UUID | None = None) -> list[EmpresaResponse]:
        if institution_id is None:
            return self._listar_con_motivos(self.repo.listar_pendientes())
        return self._listar_con_motivos(self.repo.listar_vinculadas(institution_id, ["pending"]), institution_id)

    def listar_todas(
        self, incluir_inactivas: bool = False, institution_id: uuid.UUID | None = None
    ) -> list[EmpresaResponse]:
        if institution_id is None:
            return self._listar_con_motivos(self.repo.listar_todas(incluir_inactivas=incluir_inactivas))
        estados = None if incluir_inactivas else ["pending", "approved", "rejected"]
        return self._listar_con_motivos(self.repo.listar_vinculadas(institution_id, estados), institution_id)

    def decidir(
        self,
        empresa_id: uuid.UUID | str,
        aprobado: bool,
        motivo_rechazo: str | None,
        institution_id: uuid.UUID | None = None,
        revisado_por: uuid.UUID | None = None,
    ) -> EmpresaResponse:
        empresa = self._obtener(empresa_id)
        if institution_id is not None:
            vinculo = self._obtener_vinculo(empresa, institution_id)
            self._actualizar_vinculo(
                vinculo, "approved" if aprobado else "rejected", None if aprobado else motivo_rechazo, revisado_por
            )
            nombre = vinculo.institution.name
            if aprobado:
                self.email_service.enviar(
                    empresa.contact_email or "",
                    "Acceso aprobado",
                    f"Tu empresa ya puede reclutar egresados de {nombre}.",
                )
            else:
                self.email_service.enviar(
                    empresa.contact_email or "",
                    "Acceso rechazado",
                    f"{nombre} rechazó tu solicitud. Motivo: {motivo_rechazo or 'no especificado'}.",
                )
            self.db.commit()
            return self._dto(empresa, institution_id)

        empresa.verification_status = "verified" if aprobado else "rejected"
        self.repo.registrar_verificacion(
            empresa.id,
            status="verified" if aprobado else "rejected",
            rejection_reason=None if aprobado else (motivo_rechazo or "no especificado"),
        )
        if not aprobado:
            self.email_service.enviar(
                empresa.contact_email or "",
                "Solicitud de registro rechazada",
                f"Tu solicitud fue rechazada. Motivo: {motivo_rechazo or 'no especificado'}.",
            )
        else:
            self.email_service.enviar(
                empresa.contact_email or "",
                "Empresa autorizada",
                "Tu empresa fue autorizada para publicar vacantes en la plataforma.",
            )
        self.db.commit()
        return self._dto(empresa)

    def suspender(
        self,
        empresa_id: uuid.UUID | str,
        motivo: str,
        institution_id: uuid.UUID | None = None,
        revisado_por: uuid.UUID | None = None,
    ) -> EmpresaResponse:
        empresa = self._obtener(empresa_id)
        if institution_id is not None:
            vinculo = self._obtener_vinculo(empresa, institution_id)
            self._actualizar_vinculo(vinculo, "suspended", motivo or "no especificado", revisado_por)
            self.email_service.enviar(
                empresa.contact_email or "",
                "Acceso suspendido",
                f"{vinculo.institution.name} suspendió tu acceso a sus egresados. Motivo: {motivo or 'no especificado'}.",
            )
            self.db.commit()
            return self._dto(empresa, institution_id)

        empresa.account_status = "suspended"
        # company_verification.status no admite 'suspended' (CHECK), se usa 'rejected'
        # como estado de historial más cercano junto con una nota aclaratoria.
        self.repo.registrar_verificacion(
            empresa.id, status="rejected", rejection_reason=motivo or "no especificado", notes="Suspensión de cuenta"
        )
        self.email_service.enviar(
            empresa.contact_email or "",
            "Empresa suspendida",
            f"Tu empresa fue suspendida de la plataforma. Motivo: {motivo or 'no especificado'}.",
        )
        self.db.commit()
        return self._dto(empresa)

    def actualizar_configuracion(
        self,
        empresa_id: uuid.UUID | str,
        notificaciones_activas: bool | None = None,
        postulaciones_activas: bool | None = None,
        institution_id: uuid.UUID | None = None,
    ) -> EmpresaResponse:
        empresa = self._obtener(empresa_id)
        if institution_id is not None:
            self._obtener_vinculo(empresa, institution_id)
        # Ver nota de limitaciones arriba: no hay columna para persistir esto en el
        # esquema real, se guarda como atributo en memoria del objeto de esta sesión.
        if notificaciones_activas is not None:
            empresa._notificaciones_activas = notificaciones_activas  # type: ignore[attr-defined]
        if postulaciones_activas is not None:
            empresa._postulaciones_activas = postulaciones_activas  # type: ignore[attr-defined]
        self.db.commit()
        return self._dto(empresa, institution_id)

    def eliminar_logico(
        self,
        empresa_id: uuid.UUID | str,
        institution_id: uuid.UUID | None = None,
        revisado_por: uuid.UUID | None = None,
    ) -> EmpresaResponse:
        """Baja lógica: el esquema real no tiene deleted_at, se modela como suspensión."""
        empresa = self._obtener(empresa_id)
        if institution_id is not None:
            vinculo = self._obtener_vinculo(empresa, institution_id)
            self._actualizar_vinculo(vinculo, "suspended", "Baja lógica en la universidad", revisado_por)
            self.db.commit()
            return self._dto(empresa, institution_id)

        empresa.account_status = "suspended"
        self.repo.registrar_verificacion(
            empresa.id, status="rejected", rejection_reason="Baja lógica de la cuenta", notes="Eliminación lógica"
        )
        self.db.commit()
        return self._dto(empresa)

    def restaurar(
        self,
        empresa_id: uuid.UUID | str,
        institution_id: uuid.UUID | None = None,
        revisado_por: uuid.UUID | None = None,
    ) -> EmpresaResponse:
        """Restaura una empresa suspendida/dada de baja lógicamente."""
        empresa = self._obtener(empresa_id)
        if institution_id is not None:
            vinculo = self._obtener_vinculo(empresa, institution_id)
            if vinculo.status == "suspended":
                self._actualizar_vinculo(vinculo, "approved", None, revisado_por)
            self.db.commit()
            return self._dto(empresa, institution_id)

        if empresa.account_status == "suspended":
            empresa.account_status = "active"
            self.repo.registrar_verificacion(empresa.id, status="verified", notes="Reactivación de cuenta")
            self.email_service.enviar(
                empresa.contact_email or "",
                "Empresa reactivada",
                "Tu empresa fue reactivada y puede volver a operar en la plataforma.",
            )
        self.db.commit()
        return self._dto(empresa)

    def _actualizar_vinculo(
        self, vinculo: CompanyInstitution, estado: str, motivo: str | None, revisado_por: uuid.UUID | None
    ) -> None:
        vinculo.status = estado
        vinculo.rejection_reason = motivo
        vinculo.reviewed_by = revisado_por
        vinculo.reviewed_at = datetime.now(timezone.utc)

    def _obtener_vinculo(self, empresa: Company, institution_id: uuid.UUID) -> CompanyInstitution:
        vinculo = self.repo.obtener_vinculo(empresa.id, institution_id)
        if vinculo is None:
            raise ResourceNotFoundException("No se encontró la empresa.")
        return vinculo

    def _obtener(self, empresa_id: uuid.UUID | str) -> Company:
        empresa = self.repo.obtener_por_id(empresa_id)
        if empresa is None:
            raise ResourceNotFoundException("No se encontró la empresa.")
        return empresa
