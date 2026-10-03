import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../../environments/environment';
import {
  AsignarRolRespuesta,
  NuevoUsuarioStaff,
  Rol,
  UniversidadCliente,
  UsuarioAdmin,
} from './gestion-roles.model';

const API_BASE = environment.apiUrl;

@Injectable({ providedIn: 'root' })
export class GestionRolesService {
  constructor(private readonly http: HttpClient) {}

  private headers(token: string): HttpHeaders {
    return new HttpHeaders({ Authorization: `Bearer ${token}` });
  }

  listarRoles(token: string): Observable<Rol[]> {
    return this.http.get<Rol[]>(`${API_BASE}/admin/roles`, { headers: this.headers(token) });
  }

  listarUsuarios(token: string): Observable<UsuarioAdmin[]> {
    return this.http.get<UsuarioAdmin[]>(`${API_BASE}/admin/usuarios`, { headers: this.headers(token) });
  }

  crearUsuario(token: string, datos: NuevoUsuarioStaff): Observable<UsuarioAdmin> {
    return this.http.post<UsuarioAdmin>(`${API_BASE}/admin/usuarios`, datos, { headers: this.headers(token) });
  }

  listarUniversidades(): Observable<UniversidadCliente[]> {
    return this.http.get<UniversidadCliente[]>(`${API_BASE}/catalogos/instituciones`);
  }

  asignarRol(token: string, usuarioId: string, rol: string): Observable<AsignarRolRespuesta> {
    return this.http.put<AsignarRolRespuesta>(
      `${API_BASE}/admin/usuarios/${usuarioId}/rol`,
      { rol },
      { headers: this.headers(token) },
    );
  }
}
