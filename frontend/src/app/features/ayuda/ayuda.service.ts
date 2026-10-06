import { Injectable, signal } from '@angular/core';

/** Estado del panel de ayuda en línea (se abre con el botón «?» o con F1). */
@Injectable({ providedIn: 'root' })
export class AyudaService {
  readonly abierto = signal(false);

  abrir(): void {
    this.abierto.set(true);
  }

  cerrar(): void {
    this.abierto.set(false);
  }

  alternar(): void {
    this.abierto.update((v) => !v);
  }
}
