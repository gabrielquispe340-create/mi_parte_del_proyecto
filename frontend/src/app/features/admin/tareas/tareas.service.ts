import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../../environments/environment';

export type EstadoCorrida = 'running' | 'success' | 'failure';

export interface Corrida {
  id: string;
  tarea: string;
  disparador: 'automatico' | 'manual';
  estado: EstadoCorrida;
  resumen: string | null;
  autor: string | null;
  inicio: string;
  fin: string | null;
}

export interface TareaAutomatica {
  clave: string;
  nombre: string;
  descripcion: string;
  horario: string;
  proxima: string | null;
  ultima: Corrida | null;
  historial: Corrida[];
}

export interface PanelTareas {
  planificador_activo: boolean;
  hora_diaria: number;
  tareas: TareaAutomatica[];
}

/** Tareas automáticas diarias (copia de seguridad, vacantes vencidas, boletín). Solo el superadmin. */
@Injectable({ providedIn: 'root' })
export class TareasService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/admin/tareas`;

  listar(): Observable<PanelTareas> {
    return this.http.get<PanelTareas>(this.base);
  }

  ejecutar(clave: string): Observable<Corrida> {
    return this.http.post<Corrida>(`${this.base}/${clave}/ejecutar`, {});
  }
}
