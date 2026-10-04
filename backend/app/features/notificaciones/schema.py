import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class NotificacionDTO(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    notification_type: str
    title: str
    body: str | None = None
    link: str | None = None
    read_at: datetime | None = None
    created_at: datetime
    leida: bool = False

    model_config = ConfigDict(from_attributes=True)


class NotificacionesListResponse(BaseModel):
    total: int
    no_leidas: int
    items: list[NotificacionDTO]


class ContadorNoLeidasResponse(BaseModel):
    no_leidas: int


class PreferenciasNotificacionDTO(BaseModel):
    email_enabled: bool = True
    push_enabled: bool = True
    in_app_enabled: bool = True
    notify_stage_changes: bool = True
    notify_job_matches: bool = True
    notify_interview_events: bool = True
    notify_messages: bool = True

    model_config = ConfigDict(from_attributes=True)


class PreferenciasNotificacionUpdateRequest(BaseModel):
    email_enabled: bool | None = None
    email_notifications: bool | None = None
    push_enabled: bool | None = None
    in_app_enabled: bool | None = None
    notify_stage_changes: bool | None = None
    notify_job_matches: bool | None = None
    notify_interview_events: bool | None = None
    notify_messages: bool | None = None


class CrearNotificacionInternaRequest(BaseModel):
    user_id: uuid.UUID
    notification_type: str = Field(..., max_length=50)
    title: str = Field(..., min_length=2, max_length=200)
    body: str | None = None
    link: str | None = None
