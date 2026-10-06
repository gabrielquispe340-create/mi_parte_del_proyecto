import { Injectable, signal } from '@angular/core';

/**
 * Clave de desarrollador de la bitácora confidencial (requisito 3).
 *
 * Vive solo en memoria mientras la pestaña está abierta: no se guarda en localStorage ni
 * en el servidor. Al recargar la página o cerrar sesión hay que volver a ingresarla.
 */
@Injectable({ providedIn: 'root' })
export class BitacoraClaveService {
  readonly clave = signal<string | null>(null);

  guardar(clave: string): void {
    this.clave.set(clave);
  }

  olvidar(): void {
    this.clave.set(null);
  }
}
