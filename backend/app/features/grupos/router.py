import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.common.request_context import get_client_ip
from app.core.database import get_db
from app.features.grupos.schema import CatalogoPermisosResponse, GrupoResponse, GuardarGrupoRequest, PersonalResponse
from app.features.grupos.service import GrupoService
from app.security.permisos import requiere_permiso
from app.security.tenant import AlcanceStaff

router = APIRouter(prefix="/admin", tags=["grupos-permisos"])

_gestiona_grupos = requiere_permiso("menu.grupos")


@router.get("/permisos/catalogo", response_model=CatalogoPermisosResponse)
def catalogo(_: AlcanceStaff = Depends(_gestiona_grupos), db: Session = Depends(get_db)):
    return GrupoService(db).catalogo()


@router.get("/grupos", response_model=list[GrupoResponse])
def listar(
    institucion_id: uuid.UUID | None = Query(None),
    alcance: AlcanceStaff = Depends(_gestiona_grupos),
    db: Session = Depends(get_db),
):
    return GrupoService(db).listar(alcance, institucion_id)


@router.get("/grupos/personal", response_model=list[PersonalResponse])
def personal(
    institucion_id: uuid.UUID | None = Query(None),
    alcance: AlcanceStaff = Depends(_gestiona_grupos),
    db: Session = Depends(get_db),
):
    return GrupoService(db).personal(alcance, institucion_id)


@router.post("/grupos", response_model=GrupoResponse, status_code=201)
def crear(
    data: GuardarGrupoRequest,
    request: Request,
    alcance: AlcanceStaff = Depends(_gestiona_grupos),
    db: Session = Depends(get_db),
):
    return GrupoService(db).crear(data, alcance, get_client_ip(request))


@router.put("/grupos/{grupo_id}", response_model=GrupoResponse)
def actualizar(
    grupo_id: uuid.UUID,
    data: GuardarGrupoRequest,
    request: Request,
    alcance: AlcanceStaff = Depends(_gestiona_grupos),
    db: Session = Depends(get_db),
):
    return GrupoService(db).actualizar(grupo_id, data, alcance, get_client_ip(request))


@router.delete("/grupos/{grupo_id}", status_code=204)
def eliminar(
    grupo_id: uuid.UUID,
    request: Request,
    alcance: AlcanceStaff = Depends(_gestiona_grupos),
    db: Session = Depends(get_db),
):
    GrupoService(db).eliminar(grupo_id, alcance, get_client_ip(request))
    return Response(status_code=204)
