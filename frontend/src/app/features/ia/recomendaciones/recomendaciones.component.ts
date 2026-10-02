import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ToastService } from '../../../core/services/toast.service';
import { PaginadorComponent, paginar } from '../../../shared/components/paginador/paginador.component';
import { PostulacionModalComponent } from '../../../shared/components/postulacion-modal/postulacion-modal.component';
import { IaService } from '../ia.service';
import { CriterioAfinidad, Recomendaciones, VacanteRecomendada } from '../recomendaciones.models';

type Estado = 'cargando' | 'listo' | 'no_disponible' | 'error';

const MODALIDAD: Record<string, string> = { onsite: 'Presencial', remote: 'Remoto', hybrid: 'Híbrido' };
const SENIORITY: Record<string, string> = {
  internship: 'Pasantía',
  junior: 'Junior',
  mid: 'Semi senior',
  senior: 'Senior',
  lead: 'Líder',
};
const ICONO_ESTADO: Record<CriterioAfinidad['estado'], string> = { cumple: '✓', parcial: '◐', no_cumple: '✗' };

/** HU-23: vacantes ordenadas por afinidad con el perfil del egresado, con el porqué de cada una. */
@Component({
  selector: 'app-recomendaciones',
  standalone: true,
  imports: [RouterLink, PaginadorComponent, PostulacionModalComponent],
  templateUrl: './recomendaciones.component.html',
  styleUrl: './recomendaciones.component.scss',
})
export class RecomendacionesComponent implements OnInit {
  private readonly ia = inject(IaService);
  private readonly toast = inject(ToastService);

  readonly filtros = [
    { minimo: 0, texto: 'Todas' },
    { minimo: 50, texto: '50% o más' },
    { minimo: 75, texto: '75% o más' },
  ];
  readonly iconoEstado = ICONO_ESTADO;

  readonly estado = signal<Estado>('cargando');
  readonly mensaje = signal('');
  readonly datos = signal<Recomendaciones | null>(null);
  readonly minimo = signal(0);
  readonly abiertas = signal<ReadonlySet<string>>(new Set());
  readonly pagina = signal(1);
  readonly tamanio = signal(10);
  readonly postulandoA = signal<VacanteRecomendada | null>(null);

  readonly filtradas = computed(() => (this.datos()?.items ?? []).filter((r) => r.afinidad >= this.minimo()));
  readonly paginaActual = computed(() => paginar(this.filtradas(), this.pagina(), this.tamanio()));
  readonly horaCalculo = computed(() => {
    const valor = this.datos()?.calculado_en;
    return valor ? new Date(valor).toLocaleTimeString('es-BO', { hour: '2-digit', minute: '2-digit' }) : '';
  });

  ngOnInit(): void {
    this.cargar();
  }

  cargar(): void {
    this.estado.set('cargando');
    this.ia.recomendaciones().subscribe({
      next: (datos) => {
        this.datos.set(datos);
        this.estado.set('listo');
      },
      error: (err: HttpErrorResponse) => {
        const detalle = typeof err.error?.detail === 'string' ? err.error.detail : '';
        // CP04: sin IA se avisa, pero la búsqueda y las postulaciones siguen disponibles.
        this.estado.set(err.status === 503 ? 'no_disponible' : 'error');
        this.mensaje.set(detalle || 'No se pudieron calcular tus recomendaciones.');
      },
    });
  }

  filtrar(minimo: number): void {
    this.minimo.set(minimo);
    this.pagina.set(1);
  }

  alternar(id: string): void {
    this.abiertas.update((actual) => {
      const copia = new Set(actual);
      if (!copia.delete(id)) copia.add(id);
      return copia;
    });
  }

  nivel(afinidad: number): 'alta' | 'media' | 'baja' {
    return afinidad >= 75 ? 'alta' : afinidad >= 50 ? 'media' : 'baja';
  }

  empresa(r: VacanteRecomendada): string {
    return r.vacante.company.trade_name || r.vacante.company.legal_name;
  }

  datosVacante(r: VacanteRecomendada): string {
    const v = r.vacante;
    return [v.city, MODALIDAD[v.work_modality] ?? v.work_modality, SENIORITY[v.seniority_level] ?? v.seniority_level]
      .filter(Boolean)
      .join(' · ');
  }

  resumenDescripcion(texto: string): string {
    return texto.length > 280 ? `${texto.slice(0, 280).trimEnd()}…` : texto;
  }

  postularme(r: VacanteRecomendada): void {
    this.postulandoA.set(r);
  }

  postulacionExitosa(): void {
    const r = this.postulandoA();
    this.postulandoA.set(null);
    this.toast.success(`Te postulaste a ${r?.vacante.title ?? 'la vacante'}. La seguís en Mis postulaciones.`);
    // Las vacantes con postulación vigente ya no se recomiendan.
    this.datos.update((d) =>
      d && r ? { ...d, total: d.total - 1, items: d.items.filter((i) => i.vacante.id !== r.vacante.id) } : d,
    );
  }
}
