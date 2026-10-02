import { HttpClient } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { environment } from '../../../../environments/environment';
import { PaginadorComponent, paginar } from '../../../shared/components/paginador/paginador.component';
import { AuthService } from '../../auth/auth.service';
import { ETIQUETAS_ROL } from '../gestion-roles/gestion-roles.model';

interface ResumenUniversidad {
  id: string;
  nombre: string;
  sigla: string | null;
  ciudad: string | null;
  egresados_total: number;
  egresados_verificados: number;
  egresados_pendientes: number;
  empresas_aprobadas: number;
  empresas_pendientes: number;
  vacantes_publicadas: number;
  postulaciones: number;
  plan?: { nombre: string; estado_pago: string } | null;
}

interface ActividadApi {
  fecha: string;
  usuario: string | null;
  modulo: string;
  accion: string;
  detalles: string | null;
  resultado: boolean;
}

interface PanelAdmin {
  universidades: ResumenUniversidad[];
  totales: {
    egresados: number;
    egresados_verificados: number;
    empresas_habilitadas: number;
    vacantes_publicadas: number;
    postulaciones: number;
  };
  pendientes: { egresados: number; empresas: number; vacantes: number; universidades: number };
  accesos_hoy: number;
  accesos_fallidos_hoy: number;
  actividad: ActividadApi[];
}

type Tono = 'exito' | 'peligro' | 'info' | 'neutro';

interface Tarea {
  clave: 'universidades' | 'egresados' | 'empresas' | 'vacantes';
  titulo: string;
  ayuda: string;
  cantidad: number;
  ruta: string;
  query: Record<string, string> | null;
}

interface Kpi {
  etiqueta: string;
  valor: number;
  detalle: string;
  progreso?: number;
}

interface Actividad {
  texto: string;
  usuario: string | null;
  hace: string;
  fechaCompleta: string;
  tono: Tono;
}

const TEXTO_ACCION: Record<string, string> = {
  decidir_egresado: 'Revisó la validación de un egresado',
  decidir_empresa: 'Revisó la verificación de una empresa',
  suspender_empresa: 'Suspendió una empresa',
  eliminar_empresa_logico: 'Dio de baja una empresa',
  restaurar_empresa: 'Reactivó una empresa',
  configurar_empresa: 'Cambió los permisos de una empresa',
  moderate_job_posting: 'Moderó una oferta laboral',
  create_job_posting: 'Creó una oferta laboral',
  update_job_posting: 'Editó una oferta laboral',
  change_job_status: 'Cambió el estado de una oferta',
  delete_job_posting: 'Eliminó una oferta laboral',
  asignar_rol: 'Cambió el rol de un usuario',
  crear_usuario: 'Creó una cuenta institucional',
  cambiar_password: 'Cambió su contraseña',
  registro_egresado: 'Se registró un nuevo egresado',
  registro_empresa: 'Se registró una nueva empresa',
  configurar_etapas: 'Configuró las etapas de selección de una vacante',
  solicitud_universidad: 'Una universidad pidió sumarse a EGRESA',
  aprobar_universidad: 'Aprobó el alta de una universidad',
  rechazar_universidad: 'Rechazó el alta de una universidad',
  cambiar_plan: 'Cambió el plan de una universidad',
  registrar_pago: 'Registró el pago manual de un plan',
  pago_stripe: 'Pagó el plan con tarjeta',
  avanzar_etapa: 'Avanzó a un candidato de etapa',
  descartar_candidato: 'Descartó a un candidato',
  comparar_candidatos: 'Comparó candidatos de una vacante',
  retirar_postulacion: 'Retiró una postulación',
};

const ACCIONES_NEGATIVAS = new Set([
  'suspender_empresa',
  'eliminar_empresa_logico',
  'delete_job_posting',
  'descartar_candidato',
  'retirar_postulacion',
]);

/** Lee un valor `clave=valor` de los detalles que guarda la bitácora. */
function dato(detalles: string | null, clave: string): string | null {
  const encontrado = detalles?.match(new RegExp(`(?:^|\\s)${clave}=(\\S+)`));
  return encontrado ? encontrado[1] : null;
}

function haceCuanto(fecha: Date): string {
  const minutos = Math.floor((Date.now() - fecha.getTime()) / 60000);
  if (minutos < 1) return 'hace un momento';
  if (minutos < 60) return `hace ${minutos} min`;
  const horas = Math.floor(minutos / 60);
  if (horas < 24) return `hace ${horas} h`;
  const dias = Math.floor(horas / 24);
  if (dias < 7) return dias === 1 ? 'ayer' : `hace ${dias} días`;
  return fecha.toLocaleDateString('es-BO', { day: 'numeric', month: 'short' });
}

function describir(a: ActividadApi): Actividad {
  const fecha = new Date(a.fecha);
  let texto = TEXTO_ACCION[a.accion] ?? a.accion.replaceAll('_', ' ');
  let tono: Tono = 'neutro';

  const aprobado = dato(a.detalles, 'aprobado');
  if (aprobado !== null && (a.accion === 'decidir_egresado' || a.accion === 'decidir_empresa')) {
    const sujeto = a.accion === 'decidir_egresado' ? 'un egresado' : 'una empresa';
    texto = aprobado === 'True' ? `Aprobó a ${sujeto}` : `Rechazó a ${sujeto}`;
    tono = aprobado === 'True' ? 'exito' : 'peligro';
  } else if (a.accion === 'asignar_rol') {
    const usuario = dato(a.detalles, 'usuario');
    const rol = dato(a.detalles, 'rol_nuevo');
    if (usuario && rol) texto = `Asignó el rol ${ETIQUETAS_ROL[rol] ?? rol} a ${usuario}`;
    tono = 'info';
  } else if (a.accion === 'crear_usuario') {
    const usuario = dato(a.detalles, 'usuario');
    const rol = dato(a.detalles, 'rol');
    if (usuario && rol) texto = `Creó la cuenta de ${ETIQUETAS_ROL[rol] ?? rol} ${usuario}`;
    tono = 'info';
  } else if (a.accion === 'solicitud_universidad' || a.accion === 'aprobar_universidad') {
    const sigla = dato(a.detalles, 'sigla');
    if (sigla) texto = `${TEXTO_ACCION[a.accion]} (${sigla})`;
    tono = a.accion === 'aprobar_universidad' ? 'exito' : 'info';
  } else if (a.accion === 'registrar_pago' || a.accion === 'pago_stripe') {
    tono = 'exito';
  } else if (a.accion === 'rechazar_universidad') {
    tono = 'peligro';
  } else if (a.accion.startsWith('registro_')) {
    tono = 'info';
  } else if (ACCIONES_NEGATIVAS.has(a.accion)) {
    tono = 'peligro';
  }

  if (!a.resultado) {
    texto = `${texto} (falló)`;
    tono = 'peligro';
  }

  return { texto, usuario: a.usuario, hace: haceCuanto(fecha), fechaCompleta: fecha.toLocaleString('es-BO'), tono };
}

function porcentaje(parte: number, total: number): number {
  return total > 0 ? Math.round((parte / total) * 100) : 0;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink, PaginadorComponent],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard implements OnInit {
  private readonly http = inject(HttpClient);
  readonly auth = inject(AuthService);

  readonly panel = signal<PanelAdmin | null>(null);
  readonly cargando = signal(true);
  readonly error = signal('');

  readonly paginaUniversidades = signal(1);
  readonly tamanioUniversidades = signal(5);

  readonly esSuperadmin = computed(() => !this.auth.institucion());
  readonly porcentaje = porcentaje;
  /** Plan de la universidad del admin (el superadmin no tiene uno propio). */
  readonly planPropio = computed(() => (this.esSuperadmin() ? null : (this.panel()?.universidades[0]?.plan ?? null)));

  readonly saludo = computed(() => {
    const hora = new Date().getHours();
    if (hora < 12) return 'Buenos días';
    if (hora < 19) return 'Buenas tardes';
    return 'Buenas noches';
  });

  readonly tareas = computed<Tarea[]>(() => {
    const p = this.panel();
    if (!p) return [];
    const superadmin = this.esSuperadmin();
    const tareas: Tarea[] = [];
    if (superadmin) {
      tareas.push({
        clave: 'universidades',
        titulo: 'Universidades por aprobar',
        ayuda: 'Pidieron sumarse a EGRESA y eligieron un plan.',
        cantidad: p.pendientes.universidades,
        ruta: '/admin/universidades',
        query: null,
      });
    }
    return [
      ...tareas,
      {
        clave: 'egresados',
        titulo: 'Egresados por validar',
        ayuda: 'Se registraron y esperan la verificación institucional.',
        cantidad: p.pendientes.egresados,
        ruta: '/admin/validacion-egresados',
        query: null,
      },
      {
        clave: 'empresas',
        titulo: superadmin ? 'Empresas por verificar' : 'Empresas que piden reclutar',
        ayuda: superadmin
          ? 'Empresas nuevas esperando la verificación de la plataforma.'
          : 'Solicitan acceso para reclutar egresados de tu universidad.',
        cantidad: p.pendientes.empresas,
        ruta: '/admin/empresas',
        query: { filtro: 'PENDIENTES' },
      },
      {
        clave: 'vacantes',
        titulo: 'Ofertas por moderar',
        ayuda: 'Vacantes enviadas a revisión antes de publicarse.',
        cantidad: p.pendientes.vacantes,
        ruta: '/admin/moderacion-vacantes',
        query: null,
      },
    ];
  });

  readonly totalPendientes = computed(() => this.tareas().reduce((suma, t) => suma + t.cantidad, 0));

  readonly kpis = computed<Kpi[]>(() => {
    const p = this.panel();
    if (!p) return [];
    const t = p.totales;
    const superadmin = this.esSuperadmin();
    const lista: Kpi[] = [];
    if (superadmin) {
      lista.push({
        etiqueta: 'Universidades clientes',
        valor: p.universidades.length,
        detalle: 'cada una con sus datos aislados',
      });
    }
    lista.push(
      {
        etiqueta: 'Egresados',
        valor: t.egresados,
        detalle: `${t.egresados_verificados} verificados (${porcentaje(t.egresados_verificados, t.egresados)}%)`,
        progreso: porcentaje(t.egresados_verificados, t.egresados),
      },
      {
        etiqueta: 'Empresas habilitadas',
        valor: t.empresas_habilitadas,
        detalle: superadmin ? 'reclutan en al menos una universidad' : 'pueden reclutar en tu universidad',
      },
      {
        etiqueta: 'Vacantes publicadas',
        valor: t.vacantes_publicadas,
        detalle: 'visibles para los egresados',
      },
      {
        etiqueta: 'Postulaciones',
        valor: t.postulaciones,
        detalle:
          t.vacantes_publicadas > 0
            ? `≈ ${(t.postulaciones / t.vacantes_publicadas).toFixed(1)} por vacante publicada`
            : 'todavía no hay vacantes publicadas',
      },
    );
    return lista;
  });

  readonly universidadesPagina = computed(() =>
    paginar(this.panel()?.universidades ?? [], this.paginaUniversidades(), this.tamanioUniversidades()),
  );

  readonly actividad = computed(() => (this.panel()?.actividad ?? []).map(describir));

  ngOnInit(): void {
    this.cargar();
  }

  cargar(): void {
    this.cargando.set(true);
    this.error.set('');
    this.http.get<PanelAdmin>(`${environment.apiUrl}/instituciones/panel`).subscribe({
      next: (datos) => {
        this.panel.set(datos);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set('No se pudo cargar el panel. Verificá que el servidor esté en línea.');
        this.cargando.set(false);
      },
    });
  }
}
