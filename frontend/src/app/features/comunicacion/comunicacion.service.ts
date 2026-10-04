import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  ConversacionPostulacionOut,
  MensajeOut,
} from './comunicacion.models';

@Injectable({ providedIn: 'root' })
export class ComunicacionService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/comunicacion`;

  obtenerMensajesPostulacion(idPostulacion: string): Observable<ConversacionPostulacionOut> {
    return this.http.get<ConversacionPostulacionOut>(
      `${this.base}/postulaciones/${idPostulacion}/mensajes`
    );
  }

  enviarMensajePostulacion(
    idPostulacion: string,
    contenido: string,
    archivo?: File | null
  ): Observable<MensajeOut> {
    const formData = new FormData();
    if (contenido.trim()) {
      formData.append('contenido', contenido.trim());
    }
    if (archivo) {
      formData.append('archivo', archivo, archivo.name);
    }
    return this.http.post<MensajeOut>(
      `${this.base}/postulaciones/${idPostulacion}/mensajes`,
      formData
    );
  }

  descargarAdjunto(idAdjunto: string): Observable<Blob> {
    return this.http.get(`${this.base}/adjuntos/${idAdjunto}`, {
      responseType: 'blob',
    });
  }
}
