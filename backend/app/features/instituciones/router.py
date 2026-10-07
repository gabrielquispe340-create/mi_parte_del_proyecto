import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.instituciones.schema import (
    InstitucionEmpresaResponse,
    PanelAdminResponse,
    ResumenInstitucionResponse,
)
from app.features.instituciones.service import InstitucionService
from app.security.dependencies import CurrentUser, require_roles
from app.security.permisos import permisos_de, requiere_permiso
from app.security.tenant import AlcanceStaff

router = APIRouter(prefix="/instituciones", tags=["instituciones-multitenant"])


@router.get("/empresa", response_model=list[InstitucionEmpresaResponse])
def listar_instituciones_de_mi_empresa(
    current_user: CurrentUser = Depends(require_roles("empresa")),
    db: Session = Depends(get_db),
):
    return InstitucionService(db).instituciones_de_empresa(current_user.id_usuario)


@router.post("/empresa/{institucion_id}/solicitar", response_model=InstitucionEmpresaResponse)
def solicitar_acceso_a_institucion(
    institucion_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_roles("empresa")),
    db: Session = Depends(get_db),
):
    return InstitucionService(db).solicitar_acceso(current_user.id_usuario, institucion_id)


@router.get("/resumen", response_model=list[ResumenInstitucionResponse])
def resumen_por_institucion(
    alcance: AlcanceStaff = Depends(requiere_permiso("menu.universidades")), db: Session = Depends(get_db)
):
    return InstitucionService(db).resumen(alcance.institution_id)


@router.get("/panel", response_model=PanelAdminResponse)
def panel_de_administracion(
    alcance: AlcanceStaff = Depends(requiere_permiso("menu.dashboard")), db: Session = Depends(get_db)
):
    """Datos del dashboard del admin, limitados a su universidad (o globales para el superadmin)."""
    panel = InstitucionService(db).panel(alcance.institution_id)
    # Las etiquetas del dashboard que el grupo del usuario no ve tampoco viajan en la respuesta.
    permisos = permisos_de(db, alcance)
    if "etiqueta.dashboard.indicadores" not in permisos:
        panel.totales = None
    if "etiqueta.dashboard.actividad" not in permisos:
        panel.actividad = []
        panel.accesos_hoy = 0
        panel.accesos_fallidos_hoy = 0
    return panel
