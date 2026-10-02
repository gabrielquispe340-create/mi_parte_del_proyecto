import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  AvanzarEtapaRequest,
  CandidatoPipelineItem,
  ConfigurarEtapasRequest,
  DescartarCandidatoRequest,
  Entrevista,
  EntrevistaCrear,
  EntrevistaReprogramar,
  EntrevistaRevisar,
  EtapaResponse,
  NotaInternaRequest,
  NotaInternaResponse,
  PipelineVacanteResponse,
  VacanteResumenSeleccion,
} from './seleccion.models';

@Injectable({ providedIn: 'root' })
export class SeleccionService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/seleccion`;

  listarVacantes(): Observable<VacanteResumenSeleccion[]> {
    return this.http.get<VacanteResumenSeleccion[]>(`${this.base}/vacantes`);
  }

  obtenerEtapas(idVacante: string): Observable<EtapaResponse[]> {
    return this.http.get<EtapaResponse[]>(`${this.base}/vacantes/${idVacante}/etapas`);
  }

  configurarEtapas(idVacante: string, data: ConfigurarEtapasRequest): Observable<EtapaResponse[]> {
    return this.http.put<EtapaResponse[]>(`${this.base}/vacantes/${idVacante}/etapas`, data);
  }

  obtenerPipeline(idVacante: string): Observable<PipelineVacanteResponse> {
    return this.http.get<PipelineVacanteResponse>(`${this.base}/vacantes/${idVacante}/pipeline`);
  }

  avanzarEtapa(idPostulacion: string, data: AvanzarEtapaRequest): Observable<CandidatoPipelineItem> {
    return this.http.post<CandidatoPipelineItem>(`${this.base}/postulaciones/${idPostulacion}/avanzar`, data);
  }

  descartarCandidato(idPostulacion: string, data: DescartarCandidatoRequest): Observable<CandidatoPipelineItem> {
    return this.http.post<CandidatoPipelineItem>(`${this.base}/postulaciones/${idPostulacion}/descartar`, data);
  }

  listarNotas(idPostulacion: string): Observable<NotaInternaResponse[]> {
    return this.http.get<NotaInternaResponse[]>(`${this.base}/postulaciones/${idPostulacion}/notas`);
  }

  agregarNota(idPostulacion: string, data: NotaInternaRequest): Observable<NotaInternaResponse> {
    return this.http.post<NotaInternaResponse>(`${this.base}/postulaciones/${idPostulacion}/notas`, data);
  }

  listarEntrevistas(idPostulacion: string): Observable<Entrevista[]> {
    return this.http.get<Entrevista[]>(`${this.base}/postulaciones/${idPostulacion}/entrevistas`);
  }

  proponerEntrevista(idPostulacion: string, data: EntrevistaCrear): Observable<Entrevista> {
    return this.http.post<Entrevista>(`${this.base}/postulaciones/${idPostulacion}/entrevistas`, data);
  }

  reprogramarEntrevista(idEntrevista: string, data: EntrevistaReprogramar): Observable<Entrevista> {
    return this.http.put<Entrevista>(`${this.base}/entrevistas/${idEntrevista}/reprogramar`, data);
  }

  cancelarEntrevista(idEntrevista: string): Observable<Entrevista> {
    return this.http.post<Entrevista>(`${this.base}/entrevistas/${idEntrevista}/cancelar`, {});
  }

  revisarEntrevista(idEntrevista: string, data: EntrevistaRevisar | boolean = true): Observable<Entrevista> {
    const payload = typeof data === 'boolean' ? { aprobado: data } : data;
    return this.http.post<Entrevista>(`${this.base}/entrevistas/${idEntrevista}/revisar`, payload);
  }
}

