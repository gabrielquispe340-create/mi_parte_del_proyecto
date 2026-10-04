import { VacanteResumen } from '../../core/models/vacante.models';

/** Un criterio de la afinidad (HU-23, HU-24) y cuánto lo cumple el candidato. */
export interface CriterioAfinidad {
  clave: 'carrera' | 'habilidades' | 'experiencia' | 'idiomas' | string;
  nombre: string;
  peso: number;
  cumplimiento: number;
  estado: 'cumple' | 'parcial' | 'no_cumple' | string;
  detalle: string;
  coincidencias: string[];
  faltantes: string[];
}

/** HU-23: Vacante recomendada para el egresado */
export interface VacanteRecomendada {
  vacante: VacanteResumen;
  afinidad: number;
  criterios: CriterioAfinidad[];
  ya_postulado: boolean;
}

export interface Recomendaciones {
  calculado_en: string;
  total: number;
  perfil_faltantes: string[];
  items: VacanteRecomendada[];
}

/** HU-24: Candidato sugerido por afinidad para la empresa */
export interface CandidatoSugerido {
  candidate_id: string;
  user_id: string;
  application_id?: string | null;
  first_name: string;
  last_name: string;
  professional_headline?: string | null;
  carrera_principal?: string | null;
  city?: string | null;
  afinidad_porcentaje: number;
  nivel_coincidencia: string;
  razones_principales: string[];
  criterios: CriterioAfinidad[];
  current_status?: string | null;
  applied_at?: string | null;
}

export interface SugerenciasCandidatosResponse {
  vacante_id: string;
  vacante_titulo: string;
  calculado_en: string;
  umbral_minimo: number;
  total_postulantes: number;
  total_coincidentes: number;
  items: CandidatoSugerido[];
}

