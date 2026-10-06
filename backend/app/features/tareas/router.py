"""Tareas automáticas diarias: estado, historial y ejecución manual. Solo el superadmin."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.exceptions import ResourceNotFoundException
from app.common.request_context import get_client_ip
from app.core.config import get_settings
from app.core.database import get_db
from app.features.bitacora.service import BitacoraService
from app.features.tareas import planificador as plan
from app.features.tareas.schema import CorridaResponse, TareaResponse, TareasResponse
from app.features.tareas.tareas import TAREAS
from app.models.tarea import ScheduledTaskRun
from app.models.usuario import AppUser
from app.security.tenant import AlcanceStaff, get_superadmin

router = APIRouter(prefix="/admin/tareas", tags=["tareas"])

_HISTORIAL = 10


@router.get("", response_model=TareasResponse)
def listar(_: AlcanceStaff = Depends(get_superadmin), db: Session = Depends(get_db)):
    hora = get_settings().tareas_hora_diaria
    activo = plan.planificador_activo()
    inicio_hoy = plan.inicio_del_dia()
    tareas = []
    for tarea in TAREAS.values():
        corridas = db.scalars(
            select(ScheduledTaskRun)
            .where(ScheduledTaskRun.task == tarea.clave)
            .order_by(ScheduledTaskRun.started_at.desc())
            .limit(_HISTORIAL)
        ).all()
        hecha_hoy = any(
            c.trigger == "automatico" and c.status == "success" and c.started_at >= inicio_hoy for c in corridas
        )
        historial = [CorridaResponse.model_validate(plan.resultado_de(c)) for c in corridas]
        tareas.append(
            TareaResponse(
                clave=tarea.clave,
                nombre=tarea.nombre,
                descripcion=tarea.descripcion,
                horario=f"Todos los días desde las {hora:02d}:00 (hora de Bolivia)",
                proxima=plan.proxima_ejecucion(hecha_hoy) if activo else None,
                ultima=historial[0] if historial else None,
                historial=historial,
            )
        )
    return TareasResponse(planificador_activo=activo, hora_diaria=hora, tareas=tareas)


@router.post("/{clave}/ejecutar", response_model=CorridaResponse)
def ejecutar_ahora(
    clave: str,
    request: Request,
    alcance: AlcanceStaff = Depends(get_superadmin),
    db: Session = Depends(get_db),
):
    """Corre la tarea en el momento (no cuenta como la ejecución automática del día)."""
    if clave not in TAREAS:
        raise ResourceNotFoundException("No existe esa tarea automática.")
    usuario = db.get(AppUser, alcance.usuario.id_usuario)
    correo = usuario.email if usuario else None
    BitacoraService(db).registrar(
        modulo="tareas",
        accion="ejecutar_tarea",
        usuario_id=alcance.usuario.id_usuario,
        ip=get_client_ip(request),
        detalles=f"tarea={clave}",
    )
    db.commit()
    db.close()  # la tarea abre sus propias sesiones
    return plan.ejecutar(clave, disparador="manual", autor=correo)
