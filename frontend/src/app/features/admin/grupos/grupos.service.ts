import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../../environments/environment';
import { CatalogoPermisos, Grupo, GuardarGrupo, Personal } from './grupos.model';

const API = `${environment.apiUrl}/admin`;

@Injectable({ providedIn: 'root' })
export class GruposService {
  private readonly http = inject(HttpClient);

  catalogo(): Observable<CatalogoPermisos> {
    return this.http.get<CatalogoPermisos>(`${API}/permisos/catalogo`);
  }

  listar(institucionId: string | null): Observable<Grupo[]> {
    return this.http.get<Grupo[]>(`${API}/grupos`, { params: parametros(institucionId) });
  }

  personal(institucionId: string | null): Observable<Personal[]> {
    return this.http.get<Personal[]>(`${API}/grupos/personal`, { params: parametros(institucionId) });
  }

  crear(datos: GuardarGrupo): Observable<Grupo> {
    return this.http.post<Grupo>(`${API}/grupos`, datos);
  }

  actualizar(id: string, datos: GuardarGrupo): Observable<Grupo> {
    return this.http.put<Grupo>(`${API}/grupos/${id}`, datos);
  }

  eliminar(id: string): Observable<void> {
    return this.http.delete<void>(`${API}/grupos/${id}`);
  }
}

function parametros(institucionId: string | null): HttpParams {
  return institucionId ? new HttpParams().set('institucion_id', institucionId) : new HttpParams();
}
