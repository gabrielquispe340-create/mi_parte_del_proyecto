import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
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
  private readonly router = inject(Router);
  private readonly apiUrl = `${environment.apiUrl}/notificaciones`;

  /** Signal reactivo con la cantidad de notificaciones no leídas para el navbar */
  readonly noLeidasCount = signal<number>(0);

  /** Guarda IDs de notificaciones ya conocidas para evitar disparar push repetidos */
  private notificacionesConocidas = new Set<string>();
  private pollingTimer: any = null;

  constructor() {
    this.iniciarSincronizacionEnSegundoPlano();
  }

  private headers(): HttpHeaders {
    const token = this.auth.token();
    if (token) {
      return new HttpHeaders({ Authorization: `Bearer ${token}` });
    }
    return new HttpHeaders();
  }

  /** Solicita permiso nativo al navegador para notificaciones Web Push */
  async solicitarPermisoWebPush(): Promise<boolean> {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      return false;
    }
    if (Notification.permission === 'granted') {
      return true;
    }
    if (Notification.permission !== 'denied') {
      const permission = await Notification.requestPermission();
      return permission === 'granted';
    }
    return false;
  }

  /** Verifica si el navegador tiene permiso concedido para Web Push */
  tienePermisoWebPush(): boolean {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      return false;
    }
    return Notification.permission === 'granted';
  }

  /** Emite una notificación Push nativa en el sistema operativo / navegador */
  emitirNotificacionWebPush(
    titulo: string,
    opciones?: { body?: string | null; link?: string | null; icon?: string }
  ): void {
    if (this.tienePermisoWebPush()) {
      try {
        const notif = new Notification(titulo, {
          body: opciones?.body || 'Tienes un nuevo aviso en la Bolsa de Trabajo UAGRM',
          icon: opciones?.icon || '/favicon.ico',
          badge: '/favicon.ico',
        });

        if (opciones?.link) {
          notif.onclick = () => {
            window.focus();
            if (opciones.link) {
              this.router.navigateByUrl(opciones.link);
            }
          };
        }
      } catch (err) {
        console.warn('No se pudo emitir la notificación Web Push nativa:', err);
      }
    }
  }

  /** Inicia un polling periódico cada 30 segundos para detectar nuevas alertas y lanzar Push */
  iniciarSincronizacionEnSegundoPlano(): void {
    if (typeof window === 'undefined') return;
    if (this.pollingTimer) clearInterval(this.pollingTimer);

    this.pollingTimer = setInterval(() => {
      if (this.auth.estaAutenticado()) {
        this.verificarNuevasNotificaciones();
      }
    }, 30000);
  }

  /** Verifica si hay notificaciones entrantes y dispara el Web Push si corresponde */
  verificarNuevasNotificaciones(): void {
    this.listarNotificaciones(10, 0, true).subscribe({
      next: (res) => {
        const items = res.items;
        for (const notif of items) {
          if (!this.notificacionesConocidas.has(notif.id)) {
            this.notificacionesConocidas.add(notif.id);
            // Disparar Web Push nativo en el escritorio / navegador
            this.emitirNotificacionWebPush(notif.title, {
              body: notif.body,
              link: notif.link,
            });
          }
        }
      },
      error: () => {},
    });
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
          res.items.forEach((n) => this.notificacionesConocidas.add(n.id));
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

