import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  AprobacionUniversidad,
  ConfirmacionPago,
  InstitucionDisponible,
  PagoPlan,
  Plan,
  SolicitudUniversidad,
  SolicitudUniversidadPayload,
} from '../models/plan.models';

const BASE = `${environment.apiUrl}/planes`;

/** Planes del SaaS: catálogo y alta (públicos), gestión (superadmin) y pago con tarjeta (admin de universidad). */
@Injectable({ providedIn: 'root' })
export class PlanesService {
  private readonly http = inject(HttpClient);

  listarPlanes(): Observable<Plan[]> {
    return this.http.get<Plan[]>(BASE);
  }

  institucionesDisponibles(): Observable<InstitucionDisponible[]> {
    return this.http.get<InstitucionDisponible[]>(`${BASE}/instituciones-disponibles`);
  }

  solicitarAlta(datos: SolicitudUniversidadPayload): Observable<SolicitudUniversidad> {
    return this.http.post<SolicitudUniversidad>(`${BASE}/solicitudes`, datos);
  }

  listarSolicitudes(estado = 'pending'): Observable<SolicitudUniversidad[]> {
    return this.http.get<SolicitudUniversidad[]>(`${BASE}/solicitudes`, { params: { estado } });
  }

  aprobar(solicitudId: string, passwordAdmin: string): Observable<AprobacionUniversidad> {
    return this.http.post<AprobacionUniversidad>(`${BASE}/solicitudes/${solicitudId}/aprobar`, {
      password_admin: passwordAdmin,
    });
  }

  rechazar(solicitudId: string, motivo: string): Observable<SolicitudUniversidad> {
    return this.http.post<SolicitudUniversidad>(`${BASE}/solicitudes/${solicitudId}/rechazar`, { motivo });
  }

  /** Devuelve el resumen actualizado de la universidad. */
  cambiarPlan<T>(institucionId: string, plan: string): Observable<T> {
    return this.http.put<T>(`${BASE}/universidades/${institucionId}/plan`, { plan });
  }

  /** Pago manual (transferencia, QR) que registra el superadmin. */
  registrarPago<T>(institucionId: string): Observable<T> {
    return this.http.post<T>(`${BASE}/universidades/${institucionId}/pago`, {});
  }

  /** Crea el checkout de Stripe por un año del plan de la propia universidad. */
  iniciarPagoConTarjeta(): Observable<{ url: string }> {
    return this.http.post<{ url: string }>(`${BASE}/mi-universidad/checkout`, {});
  }

  confirmarPago(sessionId: string): Observable<ConfirmacionPago> {
    return this.http.post<ConfirmacionPago>(`${BASE}/pagos/confirmar`, { session_id: sessionId });
  }

  /** Superadmin: pagos de todas las universidades. Admin de universidad: los suyos. */
  listarPagos(): Observable<PagoPlan[]> {
    return this.http.get<PagoPlan[]>(`${BASE}/pagos`);
  }
}
