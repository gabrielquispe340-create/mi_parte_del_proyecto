import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  DetallePostulacion,
  EntrevistaOut,
  FiltroPostulaciones,
  PostulacionItem,
  ResumenPostulaciones,
} from './postulaciones.models';

@Injectable({ providedIn: 'root' })
export class PostulacionesService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/postulaciones`;

  obtenerMisPostulaciones(filtros?: FiltroPostulaciones): Observable<ResumenPostulaciones> {
    let params = new HttpParams();
    if (filtros?.estado) {
      params = params.set('estado', filtros.estado);
    }
    if (filtros?.fecha_desde) {
      params = params.set('fecha_desde', filtros.fecha_desde);
    }
    if (filtros?.fecha_hasta) {
      params = params.set('fecha_hasta', filtros.fecha_hasta);
    }
    if (filtros?.busqueda && filtros.busqueda.trim()) {
      params = params.set('busqueda', filtros.busqueda.trim());
    }

    return this.http.get<ResumenPostulaciones>(`${this.baseUrl}/mis-postulaciones`, { params });
  }

  obtenerDetalle(id: string): Observable<DetallePostulacion> {
    return this.http.get<DetallePostulacion>(`${this.baseUrl}/${id}`);
  }

  retirarPostulacion(id: string, motivo?: string): Observable<PostulacionItem> {
    return this.http.post<PostulacionItem>(`${this.baseUrl}/${id}/retirar`, { motivo });
  }

  listarEntrevistas(idPostulacion: string): Observable<EntrevistaOut[]> {
    return this.http.get<EntrevistaOut[]>(`${this.baseUrl}/${idPostulacion}/entrevistas`);
  }

  confirmarEntrevista(idEntrevista: string): Observable<EntrevistaOut> {
    return this.http.post<EntrevistaOut>(`${this.baseUrl}/entrevistas/${idEntrevista}/confirmar`, {});
  }

  rechazarEntrevista(idEntrevista: string, motivo: string): Observable<EntrevistaOut> {
    return this.http.post<EntrevistaOut>(`${this.baseUrl}/entrevistas/${idEntrevista}/rechazar`, { motivo });
  }
}

