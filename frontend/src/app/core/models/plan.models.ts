/** Plan del SaaS para universidades (backend/app/features/planes). null en un límite = sin límite. */
export interface Plan {
  codigo: string;
  nombre: string;
  precio_anual_bs: number;
  max_egresados: number | null;
  max_moderadores: number | null;
  reportes: boolean;
  marca_propia: boolean;
}

export type EstadoPago = 'gratis' | 'al_dia' | 'pendiente' | 'vencido';

/** Plan contratado por una universidad y los límites que rigen hoy. */
export interface PlanDeUniversidad {
  codigo: string;
  nombre: string;
  precio_anual_bs: number;
  estado_pago: EstadoPago;
  pago_hasta: string | null;
  /** Plan cuyos límites rigen: el Básico si el pago no está al día. */
  vigente: string;
  max_egresados: number | null;
  max_moderadores: number | null;
  reportes: boolean;
  marca_propia: boolean;
}

/** Pago acreditado del plan de una universidad (tarjeta vía Stripe o manual). */
export interface PagoPlan {
  id: string;
  universidad_id: string;
  universidad: string;
  plan: string;
  plan_nombre: string;
  monto_bs: number;
  metodo: 'stripe' | 'manual';
  pagado_hasta: string | null;
  fecha: string;
  registrado_por: string | null;
}

/** Resultado de verificar en Stripe un pago al volver del checkout. */
export interface ConfirmacionPago {
  estado: 'paid' | 'pending' | 'expired';
  plan_nombre: string;
  pagado_hasta: string | null;
}

export interface InstitucionDisponible {
  id: string;
  nombre: string;
  ciudad: string | null;
}

export interface SolicitudUniversidadPayload {
  institucion_id: string | null;
  nombre: string;
  sigla: string;
  ciudad: string | null;
  responsable_nombre: string;
  responsable_correo: string;
  responsable_telefono: string | null;
  plan: string;
}

export interface SolicitudUniversidad {
  id: string;
  institucion_id: string | null;
  nombre: string;
  sigla: string;
  ciudad: string | null;
  responsable_nombre: string;
  responsable_correo: string;
  responsable_telefono: string | null;
  plan: string;
  plan_nombre: string;
  estado: 'pending' | 'approved' | 'rejected';
  motivo_rechazo: string | null;
  fecha: string;
}

export interface AprobacionUniversidad {
  universidad_id: string;
  universidad: string;
  plan: string;
  admin_correo: string;
  detalle: string;
}

export function textoLimite(valor: number | null): string {
  return valor === null ? 'Sin límite' : valor.toLocaleString('es-BO');
}

export function textoPrecio(precioAnual: number): string {
  return precioAnual === 0 ? 'Gratis' : `Bs ${precioAnual.toLocaleString('es-BO')} / año`;
}
