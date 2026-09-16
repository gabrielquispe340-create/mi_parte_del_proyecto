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
  @Output() candidateDiscarded = new EventEmitter<void>();

  private readonly svc = inject(SeleccionService);

  candidatos = signal<CandidatoComparacionResponse[]>([]);
  cargando = signal(true);
  error = signal<string | null>(null);

  ngOnInit(): void {
    if (this.postulacionIds.length < 2 || this.postulacionIds.length > 3) {
      this.error.set('Debe seleccionar entre 2 y 3 candidatos.');
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

  descartarCandidato(idPostulacion: string): void {
    if (!confirm('¿Seguro que deseas descartar a este candidato?')) return;
    
    this.svc.descartarCandidato(idPostulacion, { motivo: 'Descartado desde vista de comparación' }).subscribe({
      next: () => {
        const remaining = this.candidatos().filter(c => c.postulacion_id !== idPostulacion);
        this.candidatos.set(remaining);
        this.candidateDiscarded.emit(); // Notificar al padre para actualizar el tablero
        
        if (remaining.length < 2) {
          // Ya no se puede comparar
          alert('Queda menos de 2 candidatos, la comparación se cerrará.');
          this.close.emit();
        }
      },
      error: (e: HttpErrorResponse) => {
        alert(e.error?.detail ?? 'Error al descartar.');
      }
    });
  }
}
