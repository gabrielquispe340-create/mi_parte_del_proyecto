export interface AdjuntoMensajeOut {
  id: string;
  original_filename: string;
  mime_type?: string | null;
  file_size?: number | null;
  created_at: string;
}

export interface MensajeOut {
  id: string;
  conversation_id: string;
  sender_id: string;
  sender_nombre: string;
  sender_rol: 'empresa' | 'candidato';
  es_mio: boolean;
  content: string;
  created_at: string;
  adjunto?: AdjuntoMensajeOut | null;
}

export interface ConversacionPostulacionOut {
  conversation_id?: string | null;
  application_id: string;
  vacante_titulo: string;
  empresa_nombre: string;
  candidato_nombre: string;
  candidato_carrera?: string | null;
  estado_postulacion: string;
  total_mensajes: number;
  no_leidos: number;
  mensajes: MensajeOut[];
}
