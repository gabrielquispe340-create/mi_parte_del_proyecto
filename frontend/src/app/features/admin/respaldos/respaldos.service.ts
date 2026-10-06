import { HttpClient, HttpResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../../environments/environment';

export type TipoRespaldo = 'manual' | 'previa_restauracion' | 'subido' | 'automatica';

export interface Respaldo {
  id: string;
  archivo: string;
  tamanio_bytes: number;
  tablas: number;
  filas: number;
  tipo: TipoRespaldo;
  nota: string | null;
  creado_por: string | null;
  fecha: string;
  ultima_restauracion: string | null;
  /** false si el .zip ya no está en el servidor. */
  disponible: boolean;
}

export interface Restauracion {
  simulacro: boolean;
  tablas: number;
  filas: number;
  bitacora_conservada: number;
  vaciadas_extra: string[];
  respaldo_previo: Respaldo | null;
  mensaje: string;
}

const BASE = `${environment.apiUrl}/admin/respaldos`;

/** Backup/Restore de toda la plataforma (solo superadmin). */
@Injectable({ providedIn: 'root' })
export class RespaldosService {
  private readonly http = inject(HttpClient);

  listar(): Observable<Respaldo[]> {
    return this.http.get<Respaldo[]>(BASE);
  }

  crear(nota: string | null): Observable<Respaldo> {
    return this.http.post<Respaldo>(BASE, { nota });
  }

  subir(archivo: File): Observable<Respaldo> {
    const datos = new FormData();
    datos.append('archivo', archivo);
    return this.http.post<Respaldo>(`${BASE}/subir`, datos);
  }

  descargar(id: string): Observable<HttpResponse<Blob>> {
    return this.http.get(`${BASE}/${id}/descargar`, { responseType: 'blob', observe: 'response' });
  }

  restaurar(id: string, password: string, confirmacion: string, simulacro: boolean): Observable<Restauracion> {
    return this.http.post<Restauracion>(`${BASE}/${id}/restaurar`, { password, confirmacion, simulacro });
  }

  eliminar(id: string): Observable<void> {
    return this.http.delete<void>(`${BASE}/${id}`);
  }
}
