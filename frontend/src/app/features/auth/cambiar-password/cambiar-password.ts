import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ToastService } from '../../../core/services/toast.service';
import { AuthService, inicioSegunRol } from '../auth.service';

/**
 * Cambio de contraseña del usuario autenticado (cualquier rol). Si la cuenta tiene una
 * contraseña temporal creada por un admin, es obligatorio antes de usar la plataforma.
 */
@Component({
  selector: 'app-cambiar-password',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './cambiar-password.html',
  styleUrl: './cambiar-password.scss',
})
export class CambiarPassword {
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);

  readonly actual = signal('');
  readonly nueva = signal('');
  readonly confirmacion = signal('');
  readonly mostrar = signal(false);
  readonly guardando = signal(false);
  readonly error = signal('');

  readonly obligatorio = this.auth.debeCambiarPassword;
  readonly inicio = computed(() => inicioSegunRol(this.auth.rol()));

  readonly reglas = computed(() => [
    { texto: 'Al menos 8 caracteres', cumple: this.nueva().length >= 8 },
    { texto: 'Distinta de la contraseña actual', cumple: !!this.nueva() && this.nueva() !== this.actual() },
    { texto: 'Las dos contraseñas nuevas coinciden', cumple: !!this.nueva() && this.nueva() === this.confirmacion() },
  ]);
  readonly valido = computed(() => !!this.actual() && this.reglas().every((r) => r.cumple));

  guardar(): void {
    if (!this.valido() || this.guardando()) return;
    this.guardando.set(true);
    this.error.set('');
    this.auth.cambiarPassword(this.actual(), this.nueva()).subscribe({
      next: (respuesta) => {
        this.guardando.set(false);
        this.toast.success('Contraseña actualizada correctamente.');
        void this.router.navigate([inicioSegunRol(respuesta.rol)]);
      },
      error: (err: Error) => {
        this.guardando.set(false);
        this.error.set(err.message);
      },
    });
  }
}
