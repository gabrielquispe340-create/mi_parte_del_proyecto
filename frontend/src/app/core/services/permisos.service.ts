import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, catchError, map, of } from 'rxjs';

import { environment } from '../../../environments/environment';

const PERMISOS_KEY = 'permisos';
const ROLES_STAFF = ['platform_admin', 'moderator'];

interface MisPermisos {
  permisos: string[];
  superadmin: boolean;
}

/**
 * Privilegios por componente del panel de administración (requisito general 2).
 *
 * El backend calcula qué menús, formularios, botones y etiquetas puede usar cada
 * persona según su rol y sus grupos, y los vuelve a comprobar en cada endpoint: ocultar
 * un componente acá es comodidad, no seguridad. Los permisos solo aplican al personal de
 * la universidad; egresados y empresas no tienen componentes restringidos por grupo.
 */
@Injectable({ providedIn: 'root' })
export class PermisosService {
  private readonly http = inject(HttpClient);

  private readonly codigos = signal<ReadonlySet<string>>(new Set(leerGuardados()));
  private readonly aplica = signal<boolean>(ROLES_STAFF.includes(leer('rol') ?? ''));
  /** False en una sesión abierta antes de que existieran los permisos: hay que pedirlos. */
  private readonly conocidos = signal<boolean>(leer(PERMISOS_KEY) !== null);

  readonly lista = computed(() => [...this.codigos()]);

  puede(codigo: string): boolean {
    return !this.aplica() || this.codigos().has(codigo);
  }

  /** Al iniciar sesión o renovar el token: los permisos llegan con la respuesta. */
  establecer(rol: string, permisos: string[] | undefined): void {
    this.aplica.set(ROLES_STAFF.includes(rol));
    this.guardar(permisos ?? []);
  }

  /** Los pide solo si todavía no se conocen (lo usa el guard antes de decidir). */
  asegurar(): Observable<boolean> {
    return this.conocidos() ? of(true) : this.refrescar();
  }

  /** Vuelve a pedirlos: un cambio de grupo se ve sin cerrar sesión. */
  refrescar(): Observable<boolean> {
    if (!this.aplica()) return of(true);
    return this.http.get<MisPermisos>(`${environment.apiUrl}/auth/permisos`).pipe(
      map((respuesta) => {
        this.guardar(respuesta.permisos);
        return true;
      }),
      catchError(() => of(false)),
    );
  }

  olvidar(): void {
    this.aplica.set(false);
    this.conocidos.set(false);
    this.codigos.set(new Set());
    try {
      localStorage.removeItem(PERMISOS_KEY);
    } catch {
      /* sin almacenamiento local alcanza con la señal */
    }
  }

  private guardar(permisos: string[]): void {
    this.codigos.set(new Set(permisos));
    this.conocidos.set(true);
    try {
      localStorage.setItem(PERMISOS_KEY, JSON.stringify(permisos));
    } catch {
      /* sin almacenamiento local alcanza con la señal */
    }
  }
}

function leer(clave: string): string | null {
  try {
    return localStorage.getItem(clave);
  } catch {
    return null;
  }
}

function leerGuardados(): string[] {
  try {
    const guardados: unknown = JSON.parse(leer(PERMISOS_KEY) ?? '[]');
    return Array.isArray(guardados) ? guardados.filter((c): c is string => typeof c === 'string') : [];
  } catch {
    return [];
  }
}
