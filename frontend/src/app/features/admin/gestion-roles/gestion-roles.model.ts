export type RolSistema = 'candidate' | 'moderator' | 'platform_admin';

export const ETIQUETAS_ROL: Record<string, string> = {
  candidate: 'Egresado',
  moderator: 'Moderador',
  platform_admin: 'Administrador universitario',
  empresa: 'Empresa',
};

export interface Rol {
  id: string;
  nombre: string;
  descripcion: string | null;
}

export interface UsuarioAdmin {
  id: string;
  correo: string;
  estado: string;
  fecha_registro: string;
  ultimo_acceso: string | null;
  roles: string[];
  es_miembro_empresa: boolean;
  institucion_id: string | null;
  institucion: string | null;
}

/** Alta de personal institucional; egresados y empresas se registran solos. */
export interface NuevoUsuarioStaff {
  correo: string;
  password: string;
  rol: 'moderator' | 'platform_admin';
  institucion_id: string | null;
}

export interface UniversidadCliente {
  id: string;
  nombre: string;
  sigla: string | null;
}

export interface AsignarRolRespuesta {
  usuario: UsuarioAdmin;
  rol_anterior: string | null;
  detalle: string;
}
