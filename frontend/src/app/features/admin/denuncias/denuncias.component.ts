import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ToastService } from '../../../core/services/toast.service';
import { PaginadorComponent } from '../../../shared/components/paginador/paginador.component';
import { AuthService } from '../../auth/auth.service';
import { DecisionDenuncia, VacanteDenunciada, etiquetaCategoria, mensajeDeError } from '../../moderacion/denuncias.models';
import { DenunciasService } from '../../moderacion/denuncias.service';
import { PermisoDirective } from '../../../shared/directives/permiso.directive';

const DECISIONES: Record<DecisionDenuncia, { titulo: string; boton: string; explicacion: string }> = {
  mantener: {
    titulo: 'Mantener publicada',
    boton: 'Mantener publicada',
    explicacion: 'Las denuncias se cierran como sin fundamento y la oferta vuelve a verse si estaba oculta.',
  },
  suspender: {
    titulo: 'Suspender oferta',
    boton: 'Suspender',
    explicacion: 'La oferta deja de verse. La empresa recibe el motivo y puede corregirla y reenviarla a revisión.',
  },
  eliminar: {
    titulo: 'Eliminar oferta',
    boton: 'Eliminar',
    explicacion: 'La oferta se retira y deja de aceptar postulaciones. Las que ya tenía quedan en el historial.',
  },
};

/** HU-22: el administrador revisa las ofertas denunciadas de su universidad y decide. */
@Component({
  selector: 'app-denuncias',
  standalone: true,
  imports: [DatePipe, FormsModule, RouterLink, PaginadorComponent, PermisoDirective],
  templateUrl: './denuncias.component.html',
  styleUrl: './denuncias.component.scss',
})
export class DenunciasComponent implements OnInit {
  private readonly servicio = inject(DenunciasService);
  private readonly toast = inject(ToastService);
  readonly auth = inject(AuthService);

  readonly etiquetaCategoria = etiquetaCategoria;
  readonly decisiones = DECISIONES;

  readonly vacantes = signal<VacanteDenunciada[]>([]);
  readonly cargando = signal(false);
  readonly error = signal<string | null>(null);
  readonly total = signal(0);
  readonly umbral = signal(3);
  readonly pagina = signal(1);
  readonly tamanio = signal(10);

  // Diálogo de decisión
  readonly enRevision = signal<VacanteDenunciada | null>(null);
  readonly decision = signal<DecisionDenuncia>('mantener');
  readonly nota = signal('');
  readonly procesando = signal(false);
  readonly errorDecision = signal<string | null>(null);

  readonly notaObligatoria = computed(() => this.decision() !== 'mantener');
  readonly puedeConfirmar = computed(
    () => !this.procesando() && (!this.notaObligatoria() || this.nota().trim().length >= 5),
  );

  ngOnInit(): void {
    this.cargar();
  }

  cargar(): void {
    this.cargando.set(true);
    this.error.set(null);
    this.servicio.listarPendientes(this.pagina(), this.tamanio()).subscribe({
      next: (r) => {
        this.vacantes.set(r.items);
        this.total.set(r.total);
        this.umbral.set(r.umbral);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set('No se pudieron cargar las denuncias.');
        this.cargando.set(false);
      },
    });
  }

  irAPagina(pagina: number): void {
    this.pagina.set(pagina);
    this.cargar();
  }

  cambiarTamanio(tamanio: number): void {
    this.tamanio.set(tamanio);
    this.pagina.set(1);
    this.cargar();
  }

  abrirDecision(vacante: VacanteDenunciada, decision: DecisionDenuncia): void {
    this.enRevision.set(vacante);
    this.decision.set(decision);
    this.nota.set('');
    this.errorDecision.set(null);
  }

  cerrarDecision(): void {
    if (this.procesando()) return;
    this.enRevision.set(null);
  }

  confirmar(): void {
    const vacante = this.enRevision();
    if (!vacante || !this.puedeConfirmar()) return;
    this.procesando.set(true);
    this.errorDecision.set(null);
    this.servicio.resolver(vacante.vacante_id, this.decision(), this.nota().trim() || null).subscribe({
      next: (r) => {
        this.procesando.set(false);
        this.enRevision.set(null);
        const hecho = { mantener: 'sigue publicada', suspender: 'fue suspendida', eliminar: 'fue eliminada' }[r.decision];
        this.toast.success(`«${vacante.titulo}» ${hecho}. Se cerraron ${r.denuncias_cerradas} denuncias.`);
        // Si era la última de la página, vuelve a la anterior.
        if (this.vacantes().length === 1 && this.pagina() > 1) this.pagina.update((p) => p - 1);
        this.cargar();
      },
      error: (err: HttpErrorResponse) => {
        this.procesando.set(false);
        this.errorDecision.set(mensajeDeError(err, 'No se pudo guardar la decisión.'));
      },
    });
  }
}
