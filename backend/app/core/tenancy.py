import uuid

from sqlalchemy import or_

# Tenant de respaldo para registros creados sin universidad (datos previos al SaaS
# o clientes antiguos): la UAGRM, universidad original de la plataforma.
INSTITUCION_POR_DEFECTO_ID = uuid.UUID("50000000-0000-0000-0000-000000000001")


def condicion_institucion(columna, institution_id: uuid.UUID):
    """Filtro SQL por universidad que trata los registros sin universidad como de la UAGRM."""
    if institution_id == INSTITUCION_POR_DEFECTO_ID:
        return or_(columna == institution_id, columna.is_(None))
    return columna == institution_id


def institucion_efectiva(institution_id: uuid.UUID | None) -> uuid.UUID:
    return institution_id or INSTITUCION_POR_DEFECTO_ID
