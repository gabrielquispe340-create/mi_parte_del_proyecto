import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AdjuntoMensajeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    created_at: datetime


class MensajeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    sender_nombre: str
    sender_rol: str  # "empresa" | "candidato"
    es_mio: bool
    content: str
    created_at: datetime
    adjunto: Optional[AdjuntoMensajeOut] = None


class ConversacionPostulacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: Optional[uuid.UUID] = None
    application_id: uuid.UUID
    vacante_titulo: str
    empresa_nombre: str
    candidato_nombre: str
    candidato_carrera: Optional[str] = None
    estado_postulacion: str
    total_mensajes: int = 0
    no_leidos: int = 0
    mensajes: list[MensajeOut] = []


class ResumenMensajesPostulacionOut(BaseModel):
    application_id: uuid.UUID
    total_mensajes: int = 0
    no_leidos: int = 0
    ultimo_mensaje_at: Optional[datetime] = None
