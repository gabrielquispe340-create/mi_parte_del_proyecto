"""HU-22: denuncia de ofertas sospechosas y su revisión por la universidad."""

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException, ConflictException, ResourceNotFoundException
from app.features.bitacora.service import BitacoraService
from app.features.moderacion import reglas
from app.features.moderacion.repository import DenunciaRepository
from app.features.moderacion.schema import (
    DenunciaCreadaResponse,
    DenunciaCreateRequest,
    DenunciaItem,
    DenunciasPendientesResponse,
    MiDenunciaResponse,
    ResolucionDenunciaRequest,
    ResolucionDenunciaResponse,
    VacanteDenunciadaItem,
)
from app.features.notificaciones.emisor import emitir_notificacion
from app.models.moderacion import ModerationReport
from app.models.vacante import JobPosting, JobStatus
from app.security.dependencies import CurrentUser
from app.security.tenant import AlcanceStaff, empresa_habilitada_en, institucion_de_candidato
from app.shared.email_service import EmailService

_ENLACE_MIS_VACANTES = "/vacantes/mis-vacantes"


def _titulo(vacante: JobPosting) -> str:
    """Título de la vacante recortado para que quepa en el título de una notificación (200)."""
    return vacante.title if len(vacante.title) <= 80 else vacante.title[:79].rstrip() + "…"


def _nombre_empresa(vacante: JobPosting) -> str:
    if vacante.company is None:
        return "Empresa"
    return vacante.company.trade_name or vacante.company.legal_name


class DenunciaService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = DenunciaRepository(db)
        self.bitacora = BitacoraService(db)
        self.email = EmailService()

    # ─── Quien denuncia ──────────────────────────────────────────────────

    def denunciar(
        self,
        vacante_id: uuid.UUID,
        data: DenunciaCreateRequest,
        current_user: CurrentUser,
        ip: str | None = None,
    ) -> DenunciaCreadaResponse:
        vacante = self.repo.obtener_vacante_bloqueada(vacante_id)
        # Solo se denuncia lo que el usuario puede ver: una vacante publicada y, si es
        # egresado, de una empresa que recluta en su universidad.
        if vacante is None or vacante.status != JobStatus.PUBLISHED.value:
            raise ResourceNotFoundException("La oferta no existe o ya no está publicada.")
        universidad = institucion_de_candidato(self.db, current_user.id_usuario)
        if universidad is not None and not empresa_habilitada_en(self.db, vacante.company_id, universidad):
            raise ResourceNotFoundException("La oferta no existe o ya no está publicada.")
        if self.repo.es_miembro_de(current_user.id_usuario, vacante.company_id):
            raise BusinessException("No podés denunciar una oferta de tu propia empresa.")

        descripcion = (data.descripcion or "").strip() or None
        con_fundamento = reglas.tiene_fundamento(descripcion)
        if data.categoria == "other" and not con_fundamento:
            raise BusinessException(
                f"Si elegís «Otro motivo», contá qué pasó (al menos {reglas.MINIMO_FUNDAMENTO} caracteres)."
            )
        if self.repo.pendiente_de(current_user.id_usuario, vacante.id) is not None:
            raise ConflictException("Ya denunciaste esta oferta. La universidad la está revisando.")

        antes = reglas.denuncias_que_cuentan(self.db, vacante.id)
        denuncia = self.repo.crear(
            ModerationReport(
                reporter_id=current_user.id_usuario,
                job_id=vacante.id,
                category=data.categoria,
                description=descripcion,
                status="pending",
            )
        )
        if con_fundamento and antes + 1 == reglas.UMBRAL_OCULTAR:
            self._avisar_ocultamiento(vacante)

        self.bitacora.registrar(
            modulo="moderacion",
            accion="denunciar_vacante",
            usuario_id=current_user.id_usuario,
            ip=ip,
            detalles=f"vacante_id={vacante.id} categoria={data.categoria} cuenta={con_fundamento}",
        )
        self.db.commit()

        mensaje = "Gracias por avisar. La universidad va a revisar esta oferta."
        if not con_fundamento:
            mensaje += " Como no contaste qué pasó, tu denuncia no oculta la oferta por sí sola."
        return DenunciaCreadaResponse(id=denuncia.id, cuenta_para_umbral=con_fundamento, mensaje=mensaje)

    def mi_denuncia(self, vacante_id: uuid.UUID, current_user: CurrentUser) -> MiDenunciaResponse:
        pendiente = self.repo.pendiente_de(current_user.id_usuario, vacante_id)
        if pendiente is None:
            return MiDenunciaResponse(denunciada=False)
        return MiDenunciaResponse(denunciada=True, fecha=pendiente.created_at)

    def _avisar_ocultamiento(self, vacante: JobPosting) -> None:
        titulo = f"Tu oferta «{_titulo(vacante)}» quedó oculta"
        cuerpo = (
            "Recibió varias denuncias y no se muestra a los egresados hasta que la universidad la revise. "
            "Te vamos a avisar cuando haya una decisión."
        )
        for user_id in self.repo.miembros_de(vacante.company_id):
            emitir_notificacion(self.db, user_id, "vacante_denunciada", titulo, cuerpo, _ENLACE_MIS_VACANTES)
        if vacante.company is not None and vacante.company.contact_email:
            self.email.enviar(vacante.company.contact_email, titulo, cuerpo)

    # ─── Administrador universitario ─────────────────────────────────────

    def listar_pendientes(self, alcance: AlcanceStaff, page: int, page_size: int) -> DenunciasPendientesResponse:
        filas, total = self.repo.listar_vacantes_con_pendientes(alcance.institution_id, page, page_size)
        denuncias = self.repo.pendientes_de_vacantes([v.id for v, _ in filas])
        nombres = self.repo.nombres_de_egresados({d.reporter_id for d in denuncias})

        por_vacante: dict[uuid.UUID, list[DenunciaItem]] = {}
        for d in denuncias:
            correo = d.reporter.email if d.reporter else ""
            por_vacante.setdefault(d.job_id, []).append(
                DenunciaItem(
                    id=d.id,
                    categoria=d.category,
                    descripcion=d.description,
                    cuenta_para_umbral=reglas.tiene_fundamento(d.description),
                    denunciante_nombre=nombres.get(d.reporter_id) or correo,
                    denunciante_correo=correo,
                    created_at=d.created_at,
                )
            )

        items = []
        for vacante, ultima in filas:
            de_esta = por_vacante.get(vacante.id, [])
            que_cuentan = sum(1 for d in de_esta if d.cuenta_para_umbral)
            items.append(
                VacanteDenunciadaItem(
                    vacante_id=vacante.id,
                    titulo=vacante.title,
                    ciudad=vacante.city,
                    estado_vacante=vacante.status,
                    empresa_id=vacante.company_id,
                    empresa_nombre=_nombre_empresa(vacante),
                    oculta=que_cuentan >= reglas.UMBRAL_OCULTAR,
                    denuncias_que_cuentan=que_cuentan,
                    ultima_denuncia_at=ultima,
                    denuncias=de_esta,
                )
            )
        return DenunciasPendientesResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=max(1, math.ceil(total / page_size)),
            umbral=reglas.UMBRAL_OCULTAR,
        )

    def resolver(
        self,
        vacante_id: uuid.UUID,
        data: ResolucionDenunciaRequest,
        alcance: AlcanceStaff,
        ip: str | None = None,
    ) -> ResolucionDenunciaResponse:
        # Una universidad solo resuelve denuncias de empresas habilitadas en ella.
        if not self.repo.vacante_en_alcance(vacante_id, alcance.institution_id):
            raise ResourceNotFoundException("La oferta no existe.")
        vacante = self.repo.obtener_vacante_bloqueada(vacante_id)
        if vacante is None:
            raise ResourceNotFoundException("La oferta no existe.")

        ahora = datetime.now(timezone.utc)
        nota = (data.nota or "").strip()
        estaba_oculta = reglas.esta_oculta(self.db, vacante.id)
        # Mantener = las denuncias no tenían fundamento; suspender/eliminar = sí lo tenían.
        estado_denuncias = "dismissed" if data.decision == "mantener" else "resolved"
        denunciantes = self.repo.cerrar_pendientes(vacante.id, estado_denuncias, ahora)
        if not denunciantes:
            raise BusinessException("Esta oferta no tiene denuncias pendientes.")

        if data.decision == "suspender":
            # Como un rechazo de la HU-12: la empresa ve el motivo, la corrige y la reenvía a revisión.
            vacante.status = JobStatus.REJECTED.value
            vacante.rejection_reason = f"Suspendida tras revisar denuncias: {nota}"
        elif data.decision == "eliminar":
            # Se retira sin borrarla: las postulaciones que ya tenía siguen en el historial.
            vacante.status = JobStatus.CLOSED.value
            vacante.closed_at = ahora
            vacante.rejection_reason = f"Retirada tras revisar denuncias: {nota}"

        self._avisar_resolucion(vacante, data.decision, nota, estaba_oculta, set(denunciantes))
        self.bitacora.registrar(
            modulo="moderacion",
            accion=f"resolver_denuncias_{data.decision}",
            usuario_id=alcance.usuario.id_usuario,
            ip=ip,
            detalles=(
                f"vacante_id={vacante.id} denuncias={len(denunciantes)} "
                f"institucion={alcance.institution_id or 'global'} nota={nota or '-'}"
            ),
        )
        self.db.commit()
        return ResolucionDenunciaResponse(
            vacante_id=vacante.id,
            decision=data.decision,
            estado_vacante=vacante.status,
            denuncias_cerradas=len(denunciantes),
        )

    def _avisar_resolucion(
        self, vacante: JobPosting, decision: str, nota: str, estaba_oculta: bool, denunciantes: set[uuid.UUID]
    ) -> None:
        # A la empresa solo se le avisa si la decisión le cambia algo: vuelve a mostrarse,
        # se suspende o se retira. Mantener una oferta que nunca se ocultó no le afecta.
        aviso_empresa: tuple[str, str] | None = None
        if decision == "suspender":
            aviso_empresa = (
                f"Tu oferta «{_titulo(vacante)}» fue suspendida",
                f"La universidad revisó las denuncias. Motivo: {nota}. Podés corregirla y volver a enviarla a revisión.",
            )
        elif decision == "eliminar":
            aviso_empresa = (
                f"Tu oferta «{_titulo(vacante)}» fue retirada",
                f"La universidad revisó las denuncias y la retiró. Motivo: {nota}. Ya no recibe postulaciones.",
            )
        elif estaba_oculta:
            aviso_empresa = (
                f"Tu oferta «{_titulo(vacante)}» vuelve a estar visible",
                "La universidad revisó las denuncias y la mantuvo publicada.",
            )
        if aviso_empresa:
            titulo, cuerpo = aviso_empresa
            for user_id in self.repo.miembros_de(vacante.company_id):
                emitir_notificacion(self.db, user_id, "denuncia_resuelta", titulo, cuerpo, _ENLACE_MIS_VACANTES)
            if vacante.company is not None and vacante.company.contact_email:
                self.email.enviar(vacante.company.contact_email, titulo, cuerpo)

        resultado = {
            "mantener": "La revisamos y sigue publicada.",
            "suspender": "La revisamos y la suspendimos hasta que la empresa la corrija.",
            "eliminar": "La revisamos y la retiramos de la plataforma.",
        }[decision]
        for user_id in denunciantes:
            emitir_notificacion(
                self.db,
                user_id,
                "denuncia_resuelta",
                f"Revisamos la oferta «{_titulo(vacante)}» que denunciaste",
                f"{resultado} Gracias por ayudar a cuidar a la comunidad.",
            )
