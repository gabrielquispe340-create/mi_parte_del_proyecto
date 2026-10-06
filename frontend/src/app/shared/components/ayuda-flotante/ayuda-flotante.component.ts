import { Component, HostListener, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink } from '@angular/router';
import { filter, map } from 'rxjs';

import {
  TEMAS_AYUDA,
  TemaAyuda,
  audienciaDeRol,
  buscarTemas,
  temaParaRuta,
} from '../../../features/ayuda/ayuda.contenido';
import { AyudaService } from '../../../features/ayuda/ayuda.service';
import { AuthService } from '../../../features/auth/auth.service';

/**
 * Ayuda en línea (requisito 4): un botón «?» en todas las pantallas que abre la ayuda de la
 * pantalla actual, con buscador y acceso al centro de ayuda completo. También se abre con F1.
 */
@Component({
  selector: 'app-ayuda-flotante',
  standalone: true,
  imports: [RouterLink],
  template: `
    @if (!enCentroDeAyuda() && !ayuda.abierto()) {
      <button
        type="button"
        class="boton-ayuda"
        (click)="ayuda.abrir()"
        aria-expanded="false"
        aria-controls="panel-ayuda"
        title="Ayuda (F1)"
      >
        <span aria-hidden="true">?</span><span class="sr">Abrir ayuda</span>
      </button>
    }

    @if (ayuda.abierto()) {
      <div class="fondo" (click)="ayuda.cerrar()" aria-hidden="true"></div>
      <aside
        id="panel-ayuda"
        class="panel"
        role="dialog"
        aria-modal="false"
        aria-labelledby="titulo-ayuda"
      >
        <header class="panel-cabecera">
          <span class="panel-marca">Ayuda en línea</span>
          <button type="button" class="cerrar" (click)="ayuda.cerrar()" aria-label="Cerrar ayuda">
            ✕
          </button>
        </header>

        <div class="buscador">
          <input
            type="search"
            [value]="consulta()"
            (input)="consulta.set($any($event.target).value)"
            placeholder="Buscá un tema: postular, reportes, clave…"
            aria-label="Buscar en la ayuda"
          />
        </div>

        <div class="panel-cuerpo">
          @if (consulta().trim()) {
            <p class="seccion">Resultados ({{ resultados().length }})</p>
            @for (t of resultados(); track t.id) {
              <button type="button" class="tema-link" (click)="verTema(t)">
                <strong>{{ t.titulo }}</strong>
                <span>{{ t.resumen }}</span>
              </button>
            } @empty {
              <p class="vacio">
                No encontramos nada con «{{ consulta() }}». Probá con otras palabras.
              </p>
            }
          } @else if (tema(); as t) {
            <p class="seccion">{{ elegido() ? 'Tema' : 'En esta pantalla' }}</p>
            <h2 id="titulo-ayuda">{{ t.titulo }}</h2>
            <p class="resumen">{{ t.resumen }}</p>

            @if (t.pasos.length) {
              <ol class="pasos">
                @for (paso of t.pasos; track $index) {
                  <li>{{ paso }}</li>
                }
              </ol>
            }

            @if (t.preguntas.length) {
              <p class="seccion">Preguntas frecuentes</p>
              @for (p of t.preguntas; track $index) {
                <details class="pregunta">
                  <summary>{{ p.pregunta }}</summary>
                  <p>{{ p.respuesta }}</p>
                </details>
              }
            }

            @if (elegido()) {
              <button type="button" class="volver" (click)="elegido.set(null)">
                ← Ayuda de esta pantalla
              </button>
            }

            <p class="seccion">Otros temas</p>
            <div class="otros">
              @for (o of otros(); track o.id) {
                <button type="button" class="chip" (click)="verTema(o)">{{ o.titulo }}</button>
              }
            </div>
          }
        </div>

        <footer class="panel-pie">
          <a routerLink="/ayuda" [queryParams]="{ tema: tema()?.id }" (click)="ayuda.cerrar()"
            >Abrir el centro de ayuda →</a
          >
          <span class="atajo">F1 abre y cierra</span>
        </footer>
      </aside>
    }
  `,
  styles: [
    `
      :host {
        font-family:
          system-ui,
          -apple-system,
          BlinkMacSystemFont,
          'Segoe UI',
          Roboto,
          sans-serif;
      }
      .sr {
        position: absolute;
        width: 1px;
        height: 1px;
        overflow: hidden;
        clip: rect(0 0 0 0);
      }
      .boton-ayuda {
        position: fixed;
        right: 1.25rem;
        bottom: 1.25rem;
        z-index: 900;
        display: grid;
        place-items: center;
        width: 3rem;
        height: 3rem;
        border: none;
        border-radius: 50%;
        background: linear-gradient(135deg, #1e3a8a, #4f46e5);
        color: #ffffff;
        font-size: 1.3rem;
        font-weight: 800;
        box-shadow: 0 10px 24px -8px rgba(30, 58, 138, 0.6);
        cursor: pointer;
        transition: transform 0.15s;
      }
      .boton-ayuda:hover {
        transform: translateY(-2px);
      }
      .boton-ayuda:focus-visible {
        outline: 3px solid #a5b4fc;
        outline-offset: 3px;
      }
      .fondo {
        position: fixed;
        inset: 0;
        z-index: 898;
        background: rgba(15, 23, 42, 0.18);
      }
      .panel {
        position: fixed;
        top: 0;
        right: 0;
        bottom: 0;
        z-index: 899;
        display: flex;
        flex-direction: column;
        width: min(400px, 100vw);
        background: #ffffff;
        border-left: 1px solid #e2e8f0;
        box-shadow: -16px 0 40px -20px rgba(15, 23, 42, 0.35);
        animation: entrar 0.18s ease-out;
        color: #1e293b;
      }
      @keyframes entrar {
        from {
          transform: translateX(24px);
          opacity: 0;
        }
      }
      .panel-cabecera {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1rem 1.1rem 0.6rem;
      }
      .panel-marca {
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #4f46e5;
      }
      .cerrar {
        border: none;
        background: none;
        font-size: 1rem;
        color: #64748b;
        cursor: pointer;
      }
      .buscador {
        padding: 0 1.1rem 0.75rem;
        border-bottom: 1px solid #f1f5f9;
      }
      .buscador input {
        width: 100%;
        box-sizing: border-box;
        padding: 0.6rem 0.75rem;
        border: 1px solid #cbd5e1;
        border-radius: 0.6rem;
        background: #f8fafc;
        font: inherit;
        font-size: 0.875rem;
        outline: none;
      }
      .buscador input:focus {
        border-color: #4f46e5;
        box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12);
      }
      .panel-cuerpo {
        flex: 1;
        overflow-y: auto;
        padding: 0.9rem 1.1rem 1.25rem;
      }
      .seccion {
        margin: 1rem 0 0.4rem;
        font-size: 0.7rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: #94a3b8;
      }
      .seccion:first-child {
        margin-top: 0;
      }
      h2 {
        margin: 0 0 0.35rem;
        font-size: 1.15rem;
        font-weight: 800;
        color: #0f172a;
      }
      .resumen {
        margin: 0 0 0.75rem;
        font-size: 0.875rem;
        line-height: 1.5;
        color: #475569;
      }
      .pasos {
        margin: 0;
        padding-left: 1.2rem;
        font-size: 0.86rem;
        line-height: 1.5;
        color: #334155;
      }
      .pasos li {
        margin-bottom: 0.4rem;
      }
      .pregunta {
        margin-bottom: 0.4rem;
        border: 1px solid #e2e8f0;
        border-radius: 0.6rem;
        background: #f8fafc;
      }
      .pregunta summary {
        padding: 0.55rem 0.75rem;
        font-size: 0.85rem;
        font-weight: 600;
        color: #0f172a;
        cursor: pointer;
      }
      .pregunta p {
        margin: 0;
        padding: 0 0.75rem 0.65rem;
        font-size: 0.84rem;
        line-height: 1.5;
        color: #475569;
      }
      .tema-link {
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
        width: 100%;
        margin-bottom: 0.4rem;
        padding: 0.6rem 0.75rem;
        text-align: left;
        border: 1px solid #e2e8f0;
        border-radius: 0.6rem;
        background: #ffffff;
        font: inherit;
        cursor: pointer;
      }
      .tema-link:hover {
        border-color: #a5b4fc;
        background: #f8fafc;
      }
      .tema-link strong {
        font-size: 0.875rem;
        color: #0f172a;
      }
      .tema-link span {
        font-size: 0.8rem;
        color: #64748b;
      }
      .otros {
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
      }
      .chip {
        padding: 0.3rem 0.65rem;
        border: 1px solid #e2e8f0;
        border-radius: 9999px;
        background: #ffffff;
        font: inherit;
        font-size: 0.76rem;
        color: #334155;
        cursor: pointer;
      }
      .chip:hover {
        border-color: #4f46e5;
        color: #4f46e5;
      }
      .volver {
        margin-top: 0.75rem;
        padding: 0;
        border: none;
        background: none;
        font: inherit;
        font-size: 0.82rem;
        font-weight: 600;
        color: #4f46e5;
        cursor: pointer;
      }
      .vacio {
        font-size: 0.85rem;
        color: #64748b;
      }
      .panel-pie {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.75rem 1.1rem;
        border-top: 1px solid #f1f5f9;
        font-size: 0.82rem;
      }
      .panel-pie a {
        font-weight: 700;
        color: #4f46e5;
        text-decoration: none;
      }
      .atajo {
        color: #94a3b8;
        font-size: 0.75rem;
      }
      @media (max-width: 640px) {
        .boton-ayuda {
          right: 0.9rem;
          bottom: 0.9rem;
          width: 2.75rem;
          height: 2.75rem;
        }
      }
    `,
  ],
})
export class AyudaFlotanteComponent {
  readonly ayuda = inject(AyudaService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  private readonly url = toSignal(
    this.router.events.pipe(
      filter((e): e is NavigationEnd => e instanceof NavigationEnd),
      map((e) => e.urlAfterRedirects),
    ),
    { initialValue: this.router.url },
  );

  readonly consulta = signal('');
  readonly elegido = signal<TemaAyuda | null>(null);
  readonly enCentroDeAyuda = computed(() => this.url().startsWith('/ayuda'));

  readonly temaDePantalla = computed(() => temaParaRuta(this.url(), this.auth.rol()));
  readonly tema = computed(() => this.elegido() ?? this.temaDePantalla());

  readonly temasDelUsuario = computed(() => {
    const audiencia = audienciaDeRol(this.auth.rol());
    return TEMAS_AYUDA.filter(
      (t) => !audiencia || t.audiencia === 'todos' || t.audiencia === audiencia,
    );
  });
  readonly otros = computed(() =>
    this.temasDelUsuario()
      .filter((t) => t.id !== this.tema().id)
      .slice(0, 8),
  );
  readonly resultados = computed(() => buscarTemas(this.consulta(), this.temasDelUsuario()));

  constructor() {
    // Al cambiar de pantalla, la ayuda vuelve al tema de la pantalla nueva.
    this.router.events.pipe(filter((e) => e instanceof NavigationEnd)).subscribe(() => {
      this.elegido.set(null);
      this.consulta.set('');
    });
  }

  verTema(tema: TemaAyuda): void {
    this.elegido.set(tema);
    this.consulta.set('');
  }

  @HostListener('document:keydown', ['$event'])
  atajos(evento: KeyboardEvent): void {
    if (evento.key === 'F1') {
      evento.preventDefault();
      if (!this.enCentroDeAyuda()) this.ayuda.alternar();
    } else if (evento.key === 'Escape' && this.ayuda.abierto()) {
      this.ayuda.cerrar();
    }
  }
}
