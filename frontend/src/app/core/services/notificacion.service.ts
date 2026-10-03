import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from '../../features/auth/auth.service';
import {
  ContadorNoLeidas,
  Notificacion,
  NotificacionesListResponse,
  PreferenciasNotificacion,
} from '../models/notificacion.models';

@Injectable({
  providedIn: 'root',
})
export class NotificacionService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly apiUrl = `${environment.apiUrl}/notificaciones`;

  /** Signal reactivo con la cantidad de notificaciones no leídas para el navbar */
  readonly noLeidasCount = signal<number>(0);

  private headers(): HttpHeaders {
    const token = this.auth.token();
    if (token) {
      return new HttpHeaders({ Authorization: `Bearer ${token}` });
    }
    return new HttpHeaders();
  }

  /** Refresca el contador de notificaciones no leídas */
  actualizarContador(): void {
    if (!this.auth.estaAutenticado()) {
      this.noLeidasCount.set(0);
      return;
    }
    this.obtenerContadorNoLeidas().subscribe({
      next: (res) => this.noLeidasCount.set(res.no_leidas),
      error: () => this.noLeidasCount.set(0),
    });
  }

  /** Consulta el número de notificaciones no leídas */
  obtenerContadorNoLeidas(): Observable<ContadorNoLeidas> {
    return this.http.get<ContadorNoLeidas>(`${this.apiUrl}/contador-no-leidas`, {
      headers: this.headers(),
    });
  }

  /** Obtiene la lista paginada de notificaciones del usuario */
  listarNotificaciones(
    limit = 50,
    offset = 0,
    soloNoLeidas = false
  ): Observable<NotificacionesListResponse> {
    let params = new HttpParams().set('limit', limit).set('offset', offset);
    if (soloNoLeidas) {
      params = params.set('solo_no_leidas', 'true');
    }

    return this.http
      .get<NotificacionesListResponse>(this.apiUrl, {
        headers: this.headers(),
        params,
      })
      .pipe(
        tap((res) => {
          this.noLeidasCount.set(res.no_leidas);
        })
      );
  }

  /** Marca una notificación como leída */
  marcarComoLeida(notificationId: string): Observable<Notificacion> {
    return this.http
      .patch<Notificacion>(`${this.apiUrl}/${notificationId}/leer`, {}, { headers: this.headers() })
      .pipe(
        tap(() => {
          this.noLeidasCount.update((c) => Math.max(0, c - 1));
        })
      );
  }

  /** Marca todas las notificaciones pendientes como leídas */
  marcarTodasComoLeidas(): Observable<{ actualizadas: number }> {
    return this.http
      .post<{ actualizadas: number }>(
        `${this.apiUrl}/marcar-todas-leidas`,
        {},
        { headers: this.headers() }
      )
      .pipe(
        tap(() => {
          this.noLeidasCount.set(0);
        })
      );
  }

  /** Elimina una notificación del historial */
  eliminarNotificacion(notificationId: string): Observable<{ eliminado: boolean }> {
    return this.http.delete<{ eliminado: boolean }>(`${this.apiUrl}/${notificationId}`, {
      headers: this.headers(),
    });
  }

  /** Consulta las preferencias de notificación del usuario */
  obtenerPreferencias(): Observable<PreferenciasNotificacion> {
    return this.http.get<PreferenciasNotificacion>(`${this.apiUrl}/preferencias`, {
      headers: this.headers(),
    });
  }

  /** Actualiza las preferencias de notificación del usuario */
  actualizarPreferencias(
    prefs: Partial<PreferenciasNotificacion>
  ): Observable<PreferenciasNotificacion> {
    return this.http.put<PreferenciasNotificacion>(`${this.apiUrl}/preferencias`, prefs, {
      headers: this.headers(),
    });
  }
}
