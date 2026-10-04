export interface Notificacion {
  id: string;
  user_id: string;
  notification_type: string;
  title: string;
  body?: string | null;
  link?: string | null;
  read_at?: string | null;
  created_at: string;
  leida: boolean;
}

export interface NotificacionesListResponse {
  total: number;
  no_leidas: number;
  items: Notificacion[];
}

export interface ContadorNoLeidas {
  no_leidas: number;
}

export interface PreferenciasNotificacion {
  email_enabled?: boolean;
  email_notifications?: boolean;
  push_enabled?: boolean;
  in_app_enabled?: boolean;
  notify_stage_changes: boolean;
  notify_job_matches: boolean;
  notify_interview_events: boolean;
  notify_messages: boolean;
}
