import { Component, Input, Output, EventEmitter, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { SeleccionService } from '../seleccion.service';
import { CandidatoComparacionResponse } from '../seleccion.models';

@Component({
  selector: 'app-comparacion-modal',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './comparacion-modal.component.html',
  styleUrls: ['./comparacion-modal.component.scss']
})
export class ComparacionModalComponent implements OnInit {
  @Input({ required: true }) idVacante!: string;
  @Input({ required: true }) postulacionIds!: string[];
  @Output() close = new EventEmitter<void>();
  /** Emite el id de la postulación descartada. */
  @Output() candidateDiscarded = new EventEmitter<string>();

  private readonly svc = inject(SeleccionService);

  candidatos = signal<CandidatoComparacionResponse[]>([]);
  cargando = signal(true);
  error = signal<string | null>(null);

  postulacionADescartar = signal<string | null>(null);
  nombreADescartar = signal<string>('');
  procesandoDescarte = signal(false);
  errorDescarte = signal<string | null>(null);

  ngOnInit(): void {
    if (this.postulacionIds.length < 2 || this.postulacionIds.length > 3) {
      this.error.set('Seleccioná entre 2 y 3 candidatos para comparar.');
      this.cargando.set(false);
      return;
    }
    this.cargarDatos();
  }

  cargarDatos(): void {
    this.cargando.set(true);
    this.error.set(null);
    this.svc.compararCandidatos(this.idVacante, { postulaciones: this.postulacionIds }).subscribe({
      next: (data) => {
        this.candidatos.set(data);
        this.cargando.set(false);
      },
      error: (e: HttpErrorResponse) => {
        this.error.set(e.error?.detail ?? 'Error al cargar la comparación.');
        this.cargando.set(false);
      }
    });
  }

  abrirConfirmacionDescarte(idPostulacion: string, nombre: string): void {
    this.postulacionADescartar.set(idPostulacion);
    this.nombreADescartar.set(nombre);
  }

  cerrarConfirmacionDescarte(): void {
    if (this.procesandoDescarte()) return;
    this.postulacionADescartar.set(null);
    this.nombreADescartar.set('');
  }

  confirmarDescarte(): void {
    const id = this.postulacionADescartar();
    if (!id) return;
    
    this.procesandoDescarte.set(true);
    this.errorDescarte.set(null);
    this.svc.descartarCandidato(id, { motivo: 'Descartado desde vista de comparación' }).subscribe({
      next: () => {
        this.procesandoDescarte.set(false);
        this.cerrarConfirmacionDescarte();

        const remaining = this.candidatos().filter(c => c.postulacion_id !== id);
        this.candidatos.set(remaining);
        this.candidateDiscarded.emit(id);
        
        if (remaining.length < 2) {
          this.close.emit();
        }
      },
      error: (e: HttpErrorResponse) => {
        this.procesandoDescarte.set(false);
        this.cerrarConfirmacionDescarte();
        this.errorDescarte.set(e.error?.detail ?? 'No se pudo descartar al candidato. Intentá de nuevo.');
      }
    });
  }

  iniciales(nombre: string): string {
    return nombre
      .split(' ')
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p[0].toUpperCase())
      .join('');
  }

  /** El perfil guarda el nivel sin tilde ("basico"); acá se muestra bien escrito. */
  nivelIdioma(nivel: string): string {
    const niveles: Record<string, string> = {
      basico: 'Básico',
      intermedio: 'Intermedio',
      avanzado: 'Avanzado',
      fluido: 'Fluido',
      nativo: 'Nativo',
    };
    return niveles[nivel?.toLowerCase()] ?? nivel;
  }

  /** Mismos cortes que la afinidad en el resto de la plataforma. */
  nivelAfinidad(porcentaje: number): 'alta' | 'media' | 'baja' {
    if (porcentaje >= 75) return 'alta';
    if (porcentaje >= 50) return 'media';
    return 'baja';
  }
}
