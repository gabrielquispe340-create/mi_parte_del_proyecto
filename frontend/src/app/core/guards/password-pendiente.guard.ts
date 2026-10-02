import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { DEBE_CAMBIAR_PASSWORD_KEY } from '../../features/auth/auth.service';

/**
 * Mientras la cuenta tenga una contraseña temporal (creada por un admin), cualquier
 * pantalla protegida redirige al cambio de contraseña.
 */
export const passwordPendienteGuard: CanActivateFn = () => {
  if (localStorage.getItem('token') && localStorage.getItem(DEBE_CAMBIAR_PASSWORD_KEY) === '1') {
    return inject(Router).createUrlTree(['/cuenta/contrasena']);
  }
  return true;
};
