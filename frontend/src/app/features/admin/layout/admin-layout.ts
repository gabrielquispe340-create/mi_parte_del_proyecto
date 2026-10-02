import { Component, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../../auth/auth.service';

interface ItemMenu {
  ruta: string;
  etiqueta: string;
  tipoIcono: 'dashboard' | 'universidades' | 'roles' | 'validacion' | 'empresas' | 'moderacion' | 'bitacora' | 'respaldos';
  exacta: boolean;
  /** Solo para el superadmin del SaaS (admin sin universidad). */
  soloSuperadmin?: boolean;
}

const ITEMS_MENU: ItemMenu[] = [
  { ruta: '/admin', tipoIcono: 'dashboard', etiqueta: 'Dashboard', exacta: true },
  { ruta: '/admin/universidades', tipoIcono: 'universidades', etiqueta: 'Universidades', exacta: false },
  { ruta: '/admin/roles', tipoIcono: 'roles', etiqueta: 'Gestión de roles', exacta: false },
  { ruta: '/admin/validacion-egresados', tipoIcono: 'validacion', etiqueta: 'Validación de egresados', exacta: false },
  { ruta: '/admin/empresas', tipoIcono: 'empresas', etiqueta: 'Gestión de empresas', exacta: false },
  { ruta: '/admin/moderacion-vacantes', tipoIcono: 'moderacion', etiqueta: 'Moderación de ofertas', exacta: false },
  { ruta: '/admin/bitacora', tipoIcono: 'bitacora', etiqueta: 'Bitácora del sistema', exacta: false },
  { ruta: '/admin/respaldos', tipoIcono: 'respaldos', etiqueta: 'Copias de seguridad', exacta: false, soloSuperadmin: true },
];

@Component({
  selector: 'app-admin-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './admin-layout.html',
  styleUrl: './admin-layout.scss',
})
export class AdminLayout {
  readonly auth = inject(AuthService);

  readonly correoInicial = (this.auth.correo() || 'A').charAt(0).toUpperCase();

  readonly itemsMenu = computed(() => {
    const superadmin = !this.auth.institucion() && this.auth.rol() === 'platform_admin';
    return ITEMS_MENU.filter((item) => !item.soloSuperadmin || superadmin);
  });

  cerrarSesion(): void {
    this.auth.cerrarSesion();
  }
}
