import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { VacanteResumen } from '../../../core/models/vacante.models';
import { VacanteService } from '../../../core/services/vacante.service';
import { AuthService } from '../../auth/auth.service';
import { IaService } from '../ia.service';
import { CandidatoSugerido, SugerenciasCandidatosResponse } from '../recomendaciones.models';

@Component({
  selector: 'app-sugerencias-candidatos',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './sugerencias-candidatos.component.html',
  styleUrl: './sugerencias-candidatos.component.scss',
})
export class SugerenciasCandidatosComponent implements OnInit {
  private readonly iaService = inject(IaService);
  private readonly vacanteService = inject(VacanteService);
  private readonly router = inject(Router);
  readonly auth = inject(AuthService);

  // Vacantes disponibles de la empresa
  vacantes = signal<VacanteResumen[]>([]);
  vacanteSeleccionadaId = signal<string>('');

  // Sugerencias y Ranking IA (HU-24)
  sugerencias = signal<SugerenciasCandidatosResponse | null>(null);
  umbralMinimo = signal<number>(0);
  isLoading = signal<boolean>(false);
  errorMensaje = signal<string | null>(null);

  // Modal Detalle Criterios
  candidatoSeleccionado = signal<CandidatoSugerido | null>(null);

  ngOnInit(): void {
    if (!this.auth.estaAutenticado()) {
      this.router.navigate(['/auth/login']);
      return;
    }
    this.cargarVacantesEmpresa();
  }

  cargarVacantesEmpresa(): void {
    this.vacanteService.buscarVacantes({ limit: 50 }).subscribe({
      next: (resp) => {
        this.vacantes.set(resp.items);
        if (resp.items.length > 0) {
          this.vacanteSeleccionadaId.set(resp.items[0].id);
          this.consultarSugerencias();
        }
      },
      error: () => {
        this.errorMensaje.set('No se pudieron cargar las ofertas de empleo.');
      },
    });
  }

  onCambiarVacante(): void {
    if (this.vacanteSeleccionadaId()) {
      this.consultarSugerencias();
    }
  }

  onCambiarUmbral(nuevoUmbral: number): void {
    this.umbralMinimo.set(nuevoUmbral);
    this.consultarSugerencias();
  }

  consultarSugerencias(): void {
    const vacId = this.vacanteSeleccionadaId();
    if (!vacId) return;

    this.isLoading.set(true);
    this.errorMensaje.set(null);

    this.iaService.sugerenciasCandidatos(vacId, this.umbralMinimo()).subscribe({
      next: (data) => {
        this.sugerencias.set(data);
        this.isLoading.set(false);
      },
      error: (err) => {
        this.isLoading.set(false);
        if (err.status === 503) {
          this.errorMensaje.set('El microservicio de IA está temporalmente fuera de línea. Mostrando pool estándar.');
        } else {
          this.errorMensaje.set(err.error?.detail || 'Error al obtener las sugerencias de candidatos por afinidad.');
        }
      },
    });
  }

  verCriterios(candidato: CandidatoSugerido): void {
    this.candidatoSeleccionado.set(candidato);
  }

  cerrarModalCriterios(): void {
    this.candidatoSeleccionado.set(null);
  }

  getBadgeColor(score: number): string {
    if (score >= 85) return 'badge-green';
    if (score >= 70) return 'badge-blue';
    if (score >= 50) return 'badge-amber';
    return 'badge-gray';
  }
}

