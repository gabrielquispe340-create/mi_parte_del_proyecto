import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  Recomendaciones,
  SugerenciasCandidatosResponse,
  VacanteRecomendada,
} from './recomendaciones.models';

const BASE = `${environment.apiUrl}/ia`;

/** Módulo 5.1.11: Recomendación de vacantes (HU-23) y Sugerencia de candidatos (HU-24). */
@Injectable({ providedIn: 'root' })
export class IaService {
  private readonly http = inject(HttpClient);

  /** HU-23: Vacantes recomendadas por afinidad para el egresado. */
  recomendaciones(): Observable<Recomendaciones> {
    return this.http.get<Recomendaciones>(`${BASE}/recomendaciones`);
  }

  detalle(vacanteId: string): Observable<VacanteRecomendada> {
    return this.http.get<VacanteRecomendada>(`${BASE}/recomendaciones/${vacanteId}`);
  }

  /** HU-24: Ranking inteligente de candidatos sugeridos por afinidad para la empresa. */
  sugerenciasCandidatos(vacanteId: string, umbralMinimo = 0): Observable<SugerenciasCandidatosResponse> {
    const params = new HttpParams().set('umbral_minimo', umbralMinimo);
    return this.http.get<SugerenciasCandidatosResponse>(`${BASE}/sugerencias-candidatos/${vacanteId}`, {
      params,
    });
  }
}

