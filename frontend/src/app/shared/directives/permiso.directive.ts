import { Directive, TemplateRef, ViewContainerRef, effect, inject, input } from '@angular/core';

import { PermisosService } from '../../core/services/permisos.service';

/**
 * Muestra el elemento solo si el usuario tiene permiso sobre ese componente del panel:
 *
 *   <button *appPermiso="'boton.reportes.exportar'">Exportar</button>
 *
 * Con varios códigos alcanza con tener uno. Se actualiza solo si cambian los permisos.
 */
@Directive({ selector: '[appPermiso]', standalone: true })
export class PermisoDirective {
  readonly appPermiso = input.required<string | string[]>();

  private readonly plantilla = inject(TemplateRef<unknown>);
  private readonly contenedor = inject(ViewContainerRef);
  private readonly permisos = inject(PermisosService);
  private visible = false;

  constructor() {
    effect(() => {
      const codigos = ([] as string[]).concat(this.appPermiso());
      const puede = codigos.some((codigo) => this.permisos.puede(codigo));
      if (puede && !this.visible) {
        this.contenedor.createEmbeddedView(this.plantilla);
      } else if (!puede && this.visible) {
        this.contenedor.clear();
      }
      this.visible = puede;
    });
  }
}
