import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { BitacoraFiltros, BitacoraLog, EstadoBitacora, OpcionesListado } from './bitacora.model';
import { environment } from '../../../../environments/environment';

const API_BASE = `${environment.apiUrl}/bitacora`;

/** Bitácora confidencial: cada consulta viaja con la clave de desarrollador. */
@Injectable({ providedIn: 'root' })
export class BitacoraService {
  private readonly http = inject(HttpClient);

  private construirParams(
    filtros: Partial<BitacoraFiltros>,
    opciones: OpcionesListado = {},
  ): HttpParams {
    let params = new HttpParams();
    if (filtros.usuario?.trim()) params = params.set('usuario', filtros.usuario.trim());
    if (filtros.modulo?.trim()) params = params.set('modulo', filtros.modulo.trim());
    if (filtros.accion?.trim()) params = params.set('accion', filtros.accion.trim());
    if (filtros.fechaDesde)
      params = params.set('fecha_desde', new Date(filtros.fechaDesde).toISOString());
    if (filtros.fechaHasta)
      params = params.set('fecha_hasta', new Date(filtros.fechaHasta).toISOString());
    if (opciones.limite) params = params.set('limite', opciones.limite);
    if (opciones.sinAccesos) params = params.set('sin_accesos', true);
    return params;
  }

  private headers(clave: string | null): HttpHeaders {
    return clave ? new HttpHeaders({ 'X-Clave-Desarrollador': clave }) : new HttpHeaders();
  }

  estado(): Observable<EstadoBitacora> {
    return this.http.get<EstadoBitacora>(`${API_BASE}/estado`);
  }

  /** Comprueba la clave (423 si no es la correcta) y deja constancia del acceso. */
  abrir(clave: string): Observable<void> {
    return this.http.post<void>(`${API_BASE}/abrir`, { clave });
  }

  listar(
    clave: string | null,
    filtros: Partial<BitacoraFiltros>,
    opciones: OpcionesListado = {},
  ): Observable<BitacoraLog[]> {
    return this.http.get<BitacoraLog[]>(API_BASE, {
      headers: this.headers(clave),
      params: this.construirParams(filtros, opciones),
    });
  }

  exportar(
    clave: string | null,
    formato: 'excel' | 'pdf',
    filtros: Partial<BitacoraFiltros>,
  ): Observable<Blob> {
    return this.http.get(`${API_BASE}/export/${formato}`, {
      headers: this.headers(clave),
      params: this.construirParams(filtros),
      responseType: 'blob',
    });
  }
}
