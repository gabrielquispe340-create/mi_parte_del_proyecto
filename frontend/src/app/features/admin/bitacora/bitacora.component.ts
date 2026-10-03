import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { PaginadorComponent, paginar } from '../../../shared/components/paginador/paginador.component';
import { AuthService } from '../../auth/auth.service';
import { BitacoraLog, BitacoraFiltros } from './bitacora.model';
import { BitacoraService } from './bitacora.service';

@Component({
  selector: 'app-bitacora',
  standalone: true,
  imports: [CommonModule, FormsModule, PaginadorComponent],
  templateUrl: './bitacora.component.html',
  styleUrl: './bitacora.component.scss',
})
export class BitacoraComponent implements OnInit {
  readonly logs = signal<BitacoraLog[]>([]);
  readonly cargando = signal(false);
  readonly error = signal<string | null>(null);
  readonly pagina = signal(1);
  readonly tamanio = signal(15);

  readonly logsPagina = computed(() => paginar(this.logs(), this.pagina(), this.tamanio()));

  filtros: BitacoraFiltros = {
    usuarioId: null,
    modulo: '',
    accion: '',
    fechaDesde: '',
    fechaHasta: '',
  };

  constructor(
    private readonly bitacoraService: BitacoraService,
    readonly auth: AuthService,
  ) {}

  ngOnInit(): void {
    this.buscar();
  }

  buscar(): void {
    const token = this.auth.token();
    if (!token) {
      this.error.set('Inicia sesión como administrador para consultar la bitácora.');
      return;
    }

    this.cargando.set(true);
    this.error.set(null);
    this.bitacoraService.listar(token, this.filtros).subscribe({
      next: (logs) => {
        this.logs.set(logs);
        this.pagina.set(1);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set('No se pudo cargar la bitácora. Verifica los filtros.');
        this.cargando.set(false);
      },
    });
  }

  exportar(formato: 'excel' | 'pdf'): void {
    const token = this.auth.token();
    if (!token) {
      this.error.set('Inicia sesión como administrador para exportar la bitácora.');
      return;
    }

    this.bitacoraService.exportar(token, formato, this.filtros).subscribe({
      next: (blob) => this.descargar(blob, formato === 'excel' ? 'bitacora.xlsx' : 'bitacora.pdf'),
      error: () => this.error.set('No se pudo exportar la bitácora.'),
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
