import { Component, computed, effect, input, model } from '@angular/core';

/** Devuelve los elementos de una página para listados que se paginan en el cliente. */
export function paginar<T>(items: readonly T[], pagina: number, tamanio: number): T[] {
  const inicio = (pagina - 1) * tamanio;
  return items.slice(inicio, inicio + tamanio);
}

/**
 * Barra de paginación común a los listados del panel de administración.
 * Sirve tanto para paginación en el cliente (`[(pagina)]` + `paginar()`) como en el
 * servidor (`[pagina]` + `(paginaChange)` para volver a pedir los datos).
 */
@Component({
  selector: 'app-paginador',
  standalone: true,
  template: `
    @if (total() > 0) {
      <nav class="paginador" aria-label="Paginación">
        <span class="resumen">
          Mostrando <strong>{{ desde() }}–{{ hasta() }}</strong> de <strong>{{ total() }}</strong> {{ etiqueta() }}
        </span>

        <div class="controles">
          <label class="tamanio">
            Filas
            <select [value]="tamanio()" (change)="cambiarTamanio($any($event.target).value)">
              @for (opcion of opcionesTamanio(); track opcion) {
                <option [value]="opcion" [selected]="opcion === tamanio()">{{ opcion }}</option>
              }
            </select>
          </label>

          @if (totalPaginas() > 1) {
            <button type="button" class="paso" (click)="ir(pagina() - 1)" [disabled]="pagina() === 1" aria-label="Página anterior">
              ‹
            </button>
            @for (p of paginas(); track $index) {
              @if (p === null) {
                <span class="elipsis">…</span>
              } @else {
                <button
                  type="button"
                  class="numero"
                  [class.activa]="p === pagina()"
                  [attr.aria-current]="p === pagina() ? 'page' : null"
                  (click)="ir(p)"
                >
                  {{ p }}
                </button>
              }
            }
            <button
              type="button"
              class="paso"
              (click)="ir(pagina() + 1)"
              [disabled]="pagina() === totalPaginas()"
              aria-label="Página siguiente"
            >
              ›
            </button>
          }
        </div>
      </nav>
    }
  `,
  styles: [
    `
      .paginador {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
        padding: 12px 20px;
        border-top: 1px solid #f1f5f9;
        font-size: 0.8125rem;
        color: #64748b;
      }

      .resumen strong {
        color: #334155;
        font-weight: 600;
      }

      .controles {
        display: flex;
        align-items: center;
        gap: 4px;
        flex-wrap: wrap;
      }

      .tamanio {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-right: 10px;

        select {
          padding: 4px 6px;
          border: 1px solid #cbd5e1;
          border-radius: 6px;
          background: #ffffff;
          font: inherit;
          color: #334155;
          cursor: pointer;
        }
      }

      button {
        min-width: 32px;
        height: 32px;
        padding: 0 8px;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        background: #ffffff;
        color: #334155;
        font: inherit;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.15s ease;

        &:hover:not(:disabled):not(.activa) {
          border-color: #a5b4fc;
          background: #eef2ff;
        }

        &:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }
      }

      .paso {
        font-size: 1rem;
      }

      .numero.activa {
        background: linear-gradient(90deg, #5b66d6 0%, #8254ca 100%);
        border-color: transparent;
        color: #ffffff;
        cursor: default;
      }

      .elipsis {
        padding: 0 4px;
        color: #94a3b8;
      }
    `,
  ],
})
export class PaginadorComponent {
  readonly total = input.required<number>();
  readonly pagina = model(1);
  readonly tamanio = model(10);
  readonly opcionesTamanio = input<number[]>([10, 25, 50]);
  readonly etiqueta = input('registros');

  readonly totalPaginas = computed(() => Math.max(1, Math.ceil(this.total() / this.tamanio())));
  readonly desde = computed(() => (this.total() === 0 ? 0 : (this.pagina() - 1) * this.tamanio() + 1));
  readonly hasta = computed(() => Math.min(this.pagina() * this.tamanio(), this.total()));

  /** Primera, última y las vecinas de la actual; null marca un salto (…). */
  readonly paginas = computed<(number | null)[]>(() => {
    const total = this.totalPaginas();
    const actual = this.pagina();
    const visibles = [...new Set([1, actual - 1, actual, actual + 1, total])]
      .filter((p) => p >= 1 && p <= total)
      .sort((a, b) => a - b);

    const resultado: (number | null)[] = [];
    visibles.forEach((p, i) => {
      if (i > 0 && p - visibles[i - 1] > 1) resultado.push(null);
      resultado.push(p);
    });
    return resultado;
  });

  constructor() {
    // Si la lista se achica (un filtro, una aprobación), no quedarse en una página vacía.
    // Se corrige fuera del ciclo de detección de cambios para no alterar al padre a mitad de él.
    effect(() => {
      const ultima = this.totalPaginas();
      if (this.pagina() > ultima) queueMicrotask(() => this.pagina.set(ultima));
    });
  }

  ir(pagina: number): void {
    if (pagina < 1 || pagina > this.totalPaginas() || pagina === this.pagina()) return;
    this.pagina.set(pagina);
  }

  cambiarTamanio(valor: string): void {
    this.tamanio.set(Number(valor));
    this.pagina.set(1);
  }
}
