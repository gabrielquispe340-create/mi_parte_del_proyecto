import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ToastService } from '../../../core/services/toast.service';
import { AuthService } from '../../auth/auth.service';
import { CATEGORIAS_DENUNCIA, CategoriaDenuncia, MINIMO_FUNDAMENTO, mensajeDeError } from '../denuncias.models';
import { DenunciasService } from '../denuncias.service';

/**
 * Botón "Denunciar oferta" con su formulario (HU-22). Solo aparece con sesión iniciada;
 * si el usuario ya denunció la oferta, muestra que está en revisión.
 */
@Component({
  selector: 'app-denunciar-oferta',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './denunciar-oferta.component.html',
  styleUrl: './denunciar-oferta.component.scss',
})
export class DenunciarOfertaComponent implements OnInit {
  private readonly servicio = inject(DenunciasService);
  private readonly toast = inject(ToastService);
  readonly auth = inject(AuthService);

  readonly vacanteId = input.required<string>();
  readonly titulo = input<string>('');

  readonly categorias = CATEGORIAS_DENUNCIA;
  readonly minimo = MINIMO_FUNDAMENTO;

  readonly yaDenunciada = signal(false);
  readonly abierto = signal(false);
  readonly enviando = signal(false);
  readonly error = signal<string | null>(null);
  readonly categoria = signal<CategoriaDenuncia | null>(null);
  readonly descripcion = signal('');

  readonly largo = computed(() => this.descripcion().trim().length);
  readonly conFundamento = computed(() => this.largo() >= this.minimo);
  readonly puedeEnviar = computed(() => {
    const categoria = this.categoria();
    if (!categoria || this.enviando()) return false;
    return categoria !== 'other' || this.conFundamento();
  });

  ngOnInit(): void {
    if (!this.auth.estaAutenticado()) return;
    this.servicio.miDenuncia(this.vacanteId()).subscribe({
      next: (r) => this.yaDenunciada.set(r.denunciada),
      error: () => this.yaDenunciada.set(false),
    });
  }

  abrir(): void {
    this.categoria.set(null);
    this.descripcion.set('');
    this.error.set(null);
    this.abierto.set(true);
  }

  cerrar(): void {
    if (this.enviando()) return;
    this.abierto.set(false);
  }

  enviar(): void {
    const categoria = this.categoria();
    if (!categoria || !this.puedeEnviar()) return;
    this.enviando.set(true);
    this.error.set(null);
    this.servicio.denunciar(this.vacanteId(), categoria, this.descripcion().trim() || null).subscribe({
      next: (r) => {
        this.enviando.set(false);
        this.abierto.set(false);
        this.yaDenunciada.set(true);
        this.toast.success(r.mensaje, 6000);
      },
      error: (err: HttpErrorResponse) => {
        this.enviando.set(false);
        if (err.status === 409) {
          this.yaDenunciada.set(true);
          this.abierto.set(false);
          this.toast.info(mensajeDeError(err, 'Ya denunciaste esta oferta.'));
          return;
        }
        this.error.set(mensajeDeError(err, 'No se pudo enviar la denuncia. Intentá de nuevo.'));
      },
    });
  }
}
