import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ToastService } from '../../../core/services/toast.service';
import { PaginadorComponent, paginar } from '../../../shared/components/paginador/paginador.component';
import { Respaldo, RespaldosService, Restauracion, TipoRespaldo } from './respaldos.service';

const ETIQUETA_TIPO: Record<TipoRespaldo, string> = {
  manual: 'Manual',
  previa_restauracion: 'Antes de restaurar',
  subido: 'Subida',
  automatica: 'Automática',
};
const DIAS_AVISO = 7;
const CONFIRMACION = 'RESTAURAR';

interface Restaurando {
  respaldo: Respaldo;
  password: string;
  confirmacion: string;
  procesando: 'no' | 'simulacro' | 'real';
  error: string;
  resultado: Restauracion | null;
}

function mensajeDeError(err: HttpErrorResponse, porDefecto: string): string {
  return typeof err.error?.detail === 'string' ? err.error.detail : porDefecto;
}

/** Backup/Restore de toda la plataforma (requisito 6). Solo el superadmin. */
@Component({
  selector: 'app-respaldos',
  standalone: true,
  imports: [FormsModule, RouterLink, PaginadorComponent],
  templateUrl: './respaldos.component.html',
  styleUrl: './respaldos.component.scss',
})
export class RespaldosComponent implements OnInit {
  private readonly servicio = inject(RespaldosService);
  private readonly toast = inject(ToastService);

  readonly etiquetaTipo = ETIQUETA_TIPO;
  readonly palabraConfirmacion = CONFIRMACION;

  readonly respaldos = signal<Respaldo[]>([]);
  readonly cargando = signal(true);
  readonly error = signal('');
  readonly creando = signal(false);
  readonly subiendo = signal(false);
  readonly descargandoId = signal<string | null>(null);
  readonly eliminandoId = signal<string | null>(null);
  readonly restaurando = signal<Restaurando | null>(null);
  readonly pagina = signal(1);
  readonly tamanio = signal(10);
  nota = '';

  readonly respaldosPagina = computed(() => paginar(this.respaldos(), this.pagina(), this.tamanio()));
  readonly ultimo = computed(() => this.respaldos().find((r) => r.tipo !== 'subido') ?? null);
  readonly diasDesdeUltimo = computed(() => {
    const ultimo = this.ultimo();
    return ultimo ? Math.floor((Date.now() - new Date(ultimo.fecha).getTime()) / 86_400_000) : null;
  });
  readonly hayQueRespaldar = computed(() => {
    const dias = this.diasDesdeUltimo();
    return dias === null || dias >= DIAS_AVISO;
  });

  ngOnInit(): void {
    this.cargar();
  }

  cargar(): void {
    this.servicio.listar().subscribe({
      next: (lista) => {
        this.respaldos.set(lista);
        this.cargando.set(false);
      },
      error: (err: HttpErrorResponse) => {
        this.error.set(mensajeDeError(err, 'No se pudieron cargar las copias de seguridad.'));
        this.cargando.set(false);
      },
    });
  }

  crear(): void {
    if (this.creando()) return;
    this.creando.set(true);
    this.servicio.crear(this.nota.trim() || null).subscribe({
      next: (r) => {
        this.creando.set(false);
        this.nota = '';
        this.respaldos.update((lista) => [r, ...lista]);
        this.pagina.set(1);
        this.toast.success(`Copia creada: ${r.tablas} tablas y ${this.numero(r.filas)} filas. Descargala y guardala fuera del servidor.`);
      },
      error: (err: HttpErrorResponse) => {
        this.creando.set(false);
        this.toast.error(mensajeDeError(err, 'No se pudo crear la copia de seguridad.'));
      },
    });
  }

  subir(evento: Event): void {
    const input = evento.target as HTMLInputElement;
    const archivo = input.files?.[0];
    input.value = '';
    if (!archivo) return;
    this.subiendo.set(true);
    this.servicio.subir(archivo).subscribe({
      next: (r) => {
        this.subiendo.set(false);
        this.respaldos.update((lista) => [r, ...lista]);
        this.pagina.set(1);
        this.toast.success('Copia subida. Ya podés verificarla o restaurarla.');
      },
      error: (err: HttpErrorResponse) => {
        this.subiendo.set(false);
        this.toast.error(mensajeDeError(err, 'No se pudo subir la copia.'));
      },
    });
  }

  descargar(r: Respaldo): void {
    this.descargandoId.set(r.id);
    this.servicio.descargar(r.id).subscribe({
      next: (respuesta) => {
        this.descargandoId.set(null);
        const url = URL.createObjectURL(respuesta.body as Blob);
        const enlace = document.createElement('a');
        enlace.href = url;
        enlace.download = r.archivo;
        enlace.click();
        URL.revokeObjectURL(url);
      },
      error: () => {
        this.descargandoId.set(null);
        this.toast.error('No se pudo descargar la copia.');
      },
    });
  }

  confirmarEliminar(r: Respaldo): void {
    this.servicio.eliminar(r.id).subscribe({
      next: () => {
        this.eliminandoId.set(null);
        this.respaldos.update((lista) => lista.filter((x) => x.id !== r.id));
        this.toast.success('Copia eliminada.');
      },
      error: (err: HttpErrorResponse) => {
        this.eliminandoId.set(null);
        this.toast.error(mensajeDeError(err, 'No se pudo eliminar la copia.'));
      },
    });
  }

  // ─── Restauración ─────────────────────────────────────────────────────

  abrirRestauracion(respaldo: Respaldo): void {
    this.restaurando.set({ respaldo, password: '', confirmacion: '', procesando: 'no', error: '', resultado: null });
  }

  cerrarRestauracion(): void {
    const actual = this.restaurando();
    if (actual?.procesando !== 'no') return;
    this.restaurando.set(null);
    if (actual.resultado && !actual.resultado.simulacro) this.cargar();
  }

  actualizar(campo: 'password' | 'confirmacion', valor: string): void {
    this.restaurando.update((r) => (r ? { ...r, [campo]: valor, error: '' } : r));
  }

  puedeRestaurar(r: Restaurando): boolean {
    return r.password.length > 0 && r.confirmacion.trim().toUpperCase() === CONFIRMACION;
  }

  ejecutar(simulacro: boolean): void {
    const r = this.restaurando();
    if (!r || r.procesando !== 'no') return;
    if (!r.password) {
      this.restaurando.set({ ...r, error: 'Ingresá tu contraseña para confirmar que sos vos.' });
      return;
    }
    this.restaurando.set({ ...r, procesando: simulacro ? 'simulacro' : 'real', error: '' });
    this.servicio.restaurar(r.respaldo.id, r.password, r.confirmacion, simulacro).subscribe({
      next: (resultado) => this.restaurando.set({ ...r, procesando: 'no', resultado, password: '' }),
      error: (err: HttpErrorResponse) =>
        this.restaurando.set({
          ...r,
          procesando: 'no',
          error: mensajeDeError(err, 'No se pudo completar la operación. No se cambió nada.'),
        }),
    });
  }

  // ─── Formato ──────────────────────────────────────────────────────────

  fecha(valor: string | null): string {
    if (!valor) return '—';
    return new Date(valor).toLocaleString('es-BO', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  tamanioLegible(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  numero(valor: number): string {
    return valor.toLocaleString('es-BO');
  }
}
