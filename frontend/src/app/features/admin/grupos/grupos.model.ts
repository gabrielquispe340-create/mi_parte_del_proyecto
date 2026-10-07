export type TipoComponente = 'menu' | 'formulario' | 'boton' | 'etiqueta';

export const ETIQUETAS_TIPO: Record<TipoComponente, string> = {
  menu: 'Menú',
  formulario: 'Formulario',
  boton: 'Botón',
  etiqueta: 'Etiqueta',
};

export interface Componente {
  codigo: string;
  tipo: TipoComponente;
  modulo: string;
  nombre: string;
  descripcion: string;
  por_defecto: string[];
  asignable_a: string[];
}

export interface CatalogoPermisos {
  componentes: Componente[];
  /** Componentes que el administrador de la universidad conserva siempre. */
  siempre_admin: string[];
}

export interface MiembroGrupo {
  id: string;
  correo: string;
  rol: string;
}

export interface Grupo {
  id: string;
  nombre: string;
  descripcion: string | null;
  institucion_id: string;
  institucion: string | null;
  permisos: string[];
  miembros: MiembroGrupo[];
  actualizado: string;
}

export interface GuardarGrupo {
  nombre: string;
  descripcion: string | null;
  institucion_id: string | null;
  permisos: string[];
  miembros: string[];
}

/** Admin o moderador de la universidad, con sus grupos y lo que ve hoy. */
export interface Personal {
  id: string;
  correo: string;
  rol: string;
  grupos: string[];
  permisos: string[];
}
