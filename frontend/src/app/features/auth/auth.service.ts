import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, catchError, tap, throwError } from 'rxjs';

import { environment } from '../../../environments/environment';
import { MessageResponse, RegistroEmpresaRequest } from '../../core/models/auth.models';
import { PushService } from '../../core/services/push.service';
import { TimeoutService } from '../../core/services/timeout.service';
import { ETIQUETAS_ROL } from '../admin/gestion-roles/gestion-roles.model';

const TOKEN_KEY = 'token';
const REFRESH_KEY = 'refresh_token';
const ROL_KEY = 'rol';
const CORREO_KEY = 'correo';
const INSTITUCION_KEY = 'institucion';
/** Leída también por passwordPendienteGuard. */
export const DEBE_CAMBIAR_PASSWORD_KEY = 'debe_cambiar_password';

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  rol: string;
  roles: string[];
  institucion_id: string | null;
  institucion_nombre: string | null;
  /** La cuenta tiene una contraseña temporal creada por un admin. */
  debe_cambiar_password?: boolean;
}

/** Pantalla de inicio de cada rol tras iniciar sesión. */
export function inicioSegunRol(rol: string): string {
  return ['platform_admin', 'moderator'].includes(rol) ? '/admin' : '/dashboard';
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  readonly token = signal<string>(localStorage.getItem(TOKEN_KEY) ?? '');
  readonly rol = signal<string>(localStorage.getItem(ROL_KEY) ?? '');
  readonly correo = signal<string>(localStorage.getItem(CORREO_KEY) ?? '');
  /** Universidad (tenant) del usuario; vacía para empresas y para el superadmin global. */
  readonly institucion = signal<string>(localStorage.getItem(INSTITUCION_KEY) ?? '');
  readonly debeCambiarPassword = signal<boolean>(localStorage.getItem(DEBE_CAMBIAR_PASSWORD_KEY) === '1');
  /** Nombre del rol para mostrar; el admin sin universidad es el superadmin del SaaS. */
  readonly rolLegible = computed(() => {
    const rol = this.rol();
    if (rol === 'platform_admin' && !this.institucion()) return 'Superadministrador';
    return ETIQUETAS_ROL[rol] ?? rol;
  });

  private readonly timeout = inject(TimeoutService);
  private readonly push = inject(PushService);

  constructor(
    private readonly http: HttpClient,
    private readonly router: Router,
  ) {
    if (this.estaAutenticado()) {
      this.timeout.start(() => this.cerrarSesion());
      // Si este navegador ya dio permiso, renueva su token de avisos push (HU-21).
      void this.push.sincronizar();
    }
  }

  login(correoIngresado: string, password: string): Observable<LoginResponse> {
    return this.http
      .post<LoginResponse>(`${environment.apiUrl}/auth/login`, {
        correo: correoIngresado,
        password,
      })
      .pipe(
        tap((respuesta) => {
          localStorage.setItem(CORREO_KEY, correoIngresado);
          this.correo.set(correoIngresado);
          this.guardarSesion(respuesta);
          void this.push.sincronizar();
        }),
      );
  }

  guardarSesion(respuesta: LoginResponse): void {
    localStorage.setItem(TOKEN_KEY, respuesta.access_token);
    localStorage.setItem(REFRESH_KEY, respuesta.refresh_token);
    localStorage.setItem(ROL_KEY, respuesta.rol);
    localStorage.setItem(INSTITUCION_KEY, respuesta.institucion_nombre ?? '');
    localStorage.setItem(DEBE_CAMBIAR_PASSWORD_KEY, respuesta.debe_cambiar_password ? '1' : '');
    this.token.set(respuesta.access_token);
    this.rol.set(respuesta.rol);
    this.institucion.set(respuesta.institucion_nombre ?? '');
    this.debeCambiarPassword.set(!!respuesta.debe_cambiar_password);
    this.timeout.start(() => this.cerrarSesion());
  }

  cerrarSesion(): void {
    this.timeout.stop();
    // Antes de borrar el token de sesión: este navegador deja de recibir los avisos de la cuenta.
    this.push.desregistrar(this.token());
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(ROL_KEY);
    localStorage.removeItem(CORREO_KEY);
    localStorage.removeItem(INSTITUCION_KEY);
    localStorage.removeItem(DEBE_CAMBIAR_PASSWORD_KEY);
    this.token.set('');
    this.institucion.set('');
    this.debeCambiarPassword.set(false);
    this.rol.set('');
    this.correo.set('');
    void this.router.navigate(['/auth/login']);
  }

  estaAutenticado(): boolean {
    return this.token().length > 0;
  }

  /**
   * Renueva el access_token usando el refresh_token guardado. Usado por el
   * interceptor para renovar la sesión de forma silenciosa ante un 401, sin
   * desloguear al usuario si aún tiene actividad reciente (HU-02).
   */
  refrescarToken(): Observable<LoginResponse> {
    const refreshToken = localStorage.getItem(REFRESH_KEY);
    if (!refreshToken) {
      return throwError(() => new Error('No hay token de actualización disponible.'));
    }
    return this.http
      .post<LoginResponse>(`${environment.apiUrl}/auth/refresh`, { refresh_token: refreshToken })
      .pipe(tap((respuesta) => this.guardarSesion(respuesta)));
  }

  /** Cambia la contraseña propia; el backend devuelve tokens nuevos sin la marca de temporal. */
  cambiarPassword(passwordActual: string, passwordNueva: string): Observable<LoginResponse> {
    return this.http
      .post<LoginResponse>(`${environment.apiUrl}/auth/cambiar-password`, {
        password_actual: passwordActual,
        password_nueva: passwordNueva,
      })
      .pipe(
        tap((respuesta) => this.guardarSesion(respuesta)),
        catchError(this.handleError),
      );
  }

  /**
   * Envía la solicitud de registro de una empresa.
   * Queda en estado PENDIENTE de validación institucional.
   */
  registrarEmpresa(payload: RegistroEmpresaRequest): Observable<MessageResponse> {
    return this.http
      .post<MessageResponse>(`${environment.apiUrl}/auth/registro/empresa`, payload)
      .pipe(catchError(this.handleError));
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    let errorMessage = 'Ocurrió un error inesperado al procesar la solicitud.';
    if (error.error) {
      if (typeof error.error.detail === 'string') {
        errorMessage = error.error.detail;
      } else if (Array.isArray(error.error.detail) && error.error.detail.length > 0) {
        errorMessage = error.error.detail.map((err: { msg: string }) => err.msg).join(', ');
      } else if (error.status === 0) {
        errorMessage = 'No se pudo conectar con el servidor de la API. Verifica tu conexión.';
      }
    }
    return throwError(() => new Error(errorMessage));
  }
}
