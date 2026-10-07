import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import {
  PaginadorComponent,
  paginar,
} from '../../../shared/components/paginador/paginador.component';
import { AuthService } from '../../auth/auth.service';
import { BitacoraClaveService } from './bitacora-clave.service';
import { BitacoraFiltros, BitacoraLog, EstadoBitacora } from './bitacora.model';
import { BitacoraService } from './bitacora.service';
import { PermisoDirective } from '../../../shared/directives/permiso.directive';

const BLOQUEADA = 423;

function mensajeDeError(err: HttpErrorResponse, porDefecto: string): string {
  return typeof err.error?.detail === 'string' ? err.error.detail : porDefecto;
}

/** Bitácora confidencial (requisito 3): solo se lee con la clave de desarrollador. */
@Component({
  selector: 'app-bitacora',
  standalone: true,
  imports: [FormsModule, PaginadorComponent, PermisoDirective],
  templateUrl: './bitacora.component.html',
  styleUrl: './bitacora.component.scss',
})
export class BitacoraComponent implements OnInit {
  private readonly bitacoraService = inject(BitacoraService);
  private readonly claves = inject(BitacoraClaveService);
  readonly auth = inject(AuthService);

  readonly estado = signal<EstadoBitacora | null>(null);
  readonly logs = signal<BitacoraLog[]>([]);
  readonly cargando = signal(false);
  readonly error = signal<string | null>(null);
  readonly pagina = signal(1);
  readonly tamanio = signal(15);
  readonly abriendo = signal(false);
  readonly errorClave = signal<string | null>(null);
  readonly mostrarClave = signal(false);
  claveIngresada = '';

  readonly logsPagina = computed(() => paginar(this.logs(), this.pagina(), this.tamanio()));
  /** Con la bitácora cifrada y sin clave en memoria, se muestra la pantalla de bloqueo. */
  readonly bloqueada = computed(() => !!this.estado()?.cifrada && !this.claves.clave());

  filtros: BitacoraFiltros = {
    usuario: '',
    modulo: '',
    accion: '',
    fechaDesde: '',
    fechaHasta: '',
  };

  ngOnInit(): void {
    this.bitacoraService.estado().subscribe({
      next: (estado) => {
        this.estado.set(estado);
        if (!this.bloqueada()) this.buscar();
      },
      error: () => this.error.set('No se pudo consultar el estado de la bitácora.'),
    });
  }

  abrir(): void {
    const clave = this.claveIngresada.trim();
    if (!clave || this.abriendo()) return;
    this.abriendo.set(true);
    this.errorClave.set(null);
    this.bitacoraService.abrir(clave).subscribe({
      next: () => {
        this.abriendo.set(false);
        this.claves.guardar(clave);
        this.claveIngresada = '';
        this.buscar();
      },
      error: (err: HttpErrorResponse) => {
        this.abriendo.set(false);
        this.errorClave.set(mensajeDeError(err, 'No se pudo comprobar la clave.'));
      },
    });
  }

  cerrar(): void {
    this.claves.olvidar();
    this.logs.set([]);
  }

  buscar(): void {
    this.cargando.set(true);
    this.error.set(null);
    this.bitacoraService.listar(this.claves.clave(), this.filtros).subscribe({
      next: (logs) => {
        this.logs.set(logs);
        this.pagina.set(1);
        this.cargando.set(false);
      },
      error: (err: HttpErrorResponse) => {
        this.cargando.set(false);
        if (err.status === BLOQUEADA) {
          this.claves.olvidar();
          this.errorClave.set(mensajeDeError(err, 'Ingresá la clave de desarrollador.'));
          return;
        }
        this.error.set(mensajeDeError(err, 'No se pudo cargar la bitácora. Revisá los filtros.'));
      },
    });
  }

  limpiar(): void {
    this.filtros = { usuario: '', modulo: '', accion: '', fechaDesde: '', fechaHasta: '' };
    this.buscar();
  }

  exportar(formato: 'excel' | 'pdf'): void {
    this.bitacoraService.exportar(this.claves.clave(), formato, this.filtros).subscribe({
      next: (blob) => this.descargar(blob, formato === 'excel' ? 'bitacora.xlsx' : 'bitacora.pdf'),
      error: () => this.error.set('No se pudo exportar la bitácora.'),
    });
  }

  fecha(valor: string): string {
    return new Date(valor).toLocaleString('es-BO', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }

  private descargar(blob: Blob, nombreArchivo: string): void {
    const url = window.URL.createObjectURL(blob);
    const enlace = document.createElement('a');
    enlace.href = url;
    enlace.download = nombreArchivo;
    enlace.click();
    window.URL.revokeObjectURL(url);
  }
}
