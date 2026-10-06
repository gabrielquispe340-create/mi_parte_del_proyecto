export interface BitacoraLog {
  id: string;
  usuario_id: string | null;
  usuario_correo: string | null;
  ip: string | null;
  modulo: string;
  accion: string;
  detalles: string | null;
  resultado: boolean;
  fecha: string;
  cifrada: boolean;
}

export interface BitacoraFiltros {
  usuario: string;
  modulo: string;
  accion: string;
  fechaDesde: string;
  fechaHasta: string;
}

export interface EstadoBitacora {
  cifrada: boolean;
  entradas_sin_cifrar: number;
}

/** Filtros extra del panel del administrador (actividad reciente). */
export interface OpcionesListado {
  limite?: number;
  sinAccesos?: boolean;
}
