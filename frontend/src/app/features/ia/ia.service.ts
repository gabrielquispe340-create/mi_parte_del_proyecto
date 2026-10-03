import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Recomendaciones, VacanteRecomendada } from './recomendaciones.models';

const BASE = `${environment.apiUrl}/ia`;

/** Módulo 5.1.11: recomendación de vacantes por afinidad (HU-23). */
@Injectable({ providedIn: 'root' })
export class IaService {
  private readonly http = inject(HttpClient);

  /** 503 si el servicio de IA no está disponible: el resto de la plataforma sigue funcionando. */
  recomendaciones(): Observable<Recomendaciones> {
    return this.http.get<Recomendaciones>(`${BASE}/recomendaciones`);
  }

  detalle(vacanteId: string): Observable<VacanteRecomendada> {
    return this.http.get<VacanteRecomendada>(`${BASE}/recomendaciones/${vacanteId}`);
  }
}
