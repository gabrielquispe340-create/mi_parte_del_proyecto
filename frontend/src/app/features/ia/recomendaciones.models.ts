import { VacanteResumen } from '../../core/models/vacante.models';

/** Un criterio de la afinidad (HU-23) y cuánto lo cumple el egresado. */
export interface CriterioAfinidad {
  clave: 'carrera' | 'habilidades' | 'experiencia' | 'idiomas';
  nombre: string;
  peso: number;
  cumplimiento: number;
  estado: 'cumple' | 'parcial' | 'no_cumple';
  detalle: string;
  coincidencias: string[];
  faltantes: string[];
}

export interface VacanteRecomendada {
  vacante: VacanteResumen;
  afinidad: number;
  /** Vacío si la vacante no detalla requisitos comparables (afinidad neutral). */
  criterios: CriterioAfinidad[];
  ya_postulado: boolean;
}

export interface Recomendaciones {
  calculado_en: string;
  total: number;
  /** Secciones vacías del perfil que bajan la afinidad. */
  perfil_faltantes: string[];
  items: VacanteRecomendada[];
}
