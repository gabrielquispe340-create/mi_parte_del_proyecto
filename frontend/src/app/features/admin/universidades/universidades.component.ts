import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { environment } from '../../../../environments/environment';
import {
  ConfirmacionPago,
  EstadoPago,
  PagoPlan,
  Plan,
  PlanDeUniversidad,
  SolicitudUniversidad,
  textoLimite,
  textoPrecio,
} from '../../../core/models/plan.models';
import { PlanesService } from '../../../core/services/planes.service';
import { ToastService } from '../../../core/services/toast.service';
import { PaginadorComponent, paginar } from '../../../shared/components/paginador/paginador.component';
import { copiarAlPortapapeles, generarPassword } from '../../../shared/utils/password';
import { AuthService } from '../../auth/auth.service';

interface ResumenInstitucion {
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
  moderadores: number;
  plan: PlanDeUniversidad | null;
}

interface Aprobacion {
  solicitud: SolicitudUniversidad;
  password: string;
  guardando: boolean;
  error: string;
  /** Credenciales del admin una vez aprobada (se muestran una sola vez). */
  creada: { universidad: string; correo: string; password: string; detalle: string } | null;
  copia: 'idle' | 'ok' | 'error';
}

const ETIQUETA_PAGO: Record<EstadoPago, string> = {
  gratis: 'Gratis',
  al_dia: 'Pago al día',
  pendiente: 'Pago pendiente',
  vencido: 'Pago vencido',
};

interface AvisoPago {
  tipo: 'ok' | 'info' | 'error';
  texto: string;
}

function mensajeDeError(err: HttpErrorResponse, porDefecto: string): string {
  return typeof err.error?.detail === 'string' ? err.error.detail : porDefecto;
}

@Component({
  selector: 'app-universidades',
  standalone: true,
  imports: [FormsModule, PaginadorComponent],
  templateUrl: './universidades.component.html',
  styleUrl: './universidades.component.scss',
})
export class UniversidadesComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly planesService = inject(PlanesService);
  private readonly toast = inject(ToastService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly auth = inject(AuthService);

  readonly etiquetaPago = ETIQUETA_PAGO;
  readonly textoLimite = textoLimite;
  readonly textoPrecio = textoPrecio;

  readonly resumen = signal<ResumenInstitucion[]>([]);
  readonly cargando = signal(true);
  readonly error = signal<string | null>(null);
  readonly pagina = signal(1);
  readonly tamanio = signal(6);

  // Solo superadmin
  readonly solicitudes = signal<SolicitudUniversidad[]>([]);
  readonly planes = signal<Plan[]>([]);
  readonly procesandoId = signal<string | null>(null);
  readonly rechazandoId = signal<string | null>(null);
  readonly aprobacion = signal<Aprobacion | null>(null);
  readonly planElegido = signal<Record<string, string>>({});
  motivoRechazo = '';

  // Pagos: el admin de cada universidad paga con tarjeta; el historial lo ven ambos.
  readonly pagos = signal<PagoPlan[]>([]);
  readonly paginaPagos = signal(1);
  readonly tamanioPagos = signal(5);
  readonly pagando = signal(false);
  readonly avisoPago = signal<AvisoPago | null>(null);
  readonly pagosPagina = computed(() => paginar(this.pagos(), this.paginaPagos(), this.tamanioPagos()));

  readonly resumenPagina = computed(() => paginar(this.resumen(), this.pagina(), this.tamanio()));

  readonly esSuperadmin = computed(() => !this.auth.institucion());
  readonly esAdminUniversidad = computed(() => !this.esSuperadmin() && this.auth.rol() === 'platform_admin');
  readonly totales = computed(() =>
    this.resumen().reduce(
      (acc, u) => ({
        egresados: acc.egresados + u.egresados_total,
        postulaciones: acc.postulaciones + u.postulaciones,
        // Facturación simulada: solo cuentan los planes con el pago al día.
        facturacion: acc.facturacion + (u.plan?.estado_pago === 'al_dia' ? u.plan.precio_anual_bs : 0),
        pagosPendientes:
          acc.pagosPendientes + (u.plan && ['pendiente', 'vencido'].includes(u.plan.estado_pago) ? 1 : 0),
      }),
      { egresados: 0, postulaciones: 0, facturacion: 0, pagosPendientes: 0 },
    ),
  );

  ngOnInit(): void {
    this.atenderRegresoDeStripe();
    this.cargar();
    this.cargarPagos();
    if (this.esSuperadmin()) {
      this.cargarSolicitudes();
      this.planesService.listarPlanes().subscribe({ next: (planes) => this.planes.set(planes) });
    }
  }

  cargar(): void {
    this.http.get<ResumenInstitucion[]>(`${environment.apiUrl}/instituciones/resumen`).subscribe({
      next: (datos) => {
        this.resumen.set(datos);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set('No se pudo cargar el resumen de universidades.');
        this.cargando.set(false);
      },
    });
  }

  cargarPagos(): void {
    this.planesService.listarPagos().subscribe({ next: (lista) => this.pagos.set(lista) });
  }

  cargarSolicitudes(): void {
    this.planesService.listarSolicitudes().subscribe({ next: (lista) => this.solicitudes.set(lista) });
  }

  porcentajeUso(usados: number, maximo: number | null): number {
    if (maximo === null || maximo === 0) return 0;
    return Math.min(100, Math.round((usados / maximo) * 100));
  }

  // ─── Plan y pago (superadmin) ───────────────────────────────────────────

  planSeleccionado(u: ResumenInstitucion): string {
    return this.planElegido()[u.id] ?? u.plan?.codigo ?? 'basico';
  }

  elegirPlan(u: ResumenInstitucion, codigo: string): void {
    this.planElegido.update((sel) => ({ ...sel, [u.id]: codigo }));
  }

  aplicarPlan(u: ResumenInstitucion): void {
    const codigo = this.planSeleccionado(u);
    if (!u.plan || u.plan.codigo === codigo) return;
    this.procesandoId.set(u.id);
    this.planesService.cambiarPlan<ResumenInstitucion>(u.id, codigo).subscribe({
      next: (actualizada) => {
        this.reemplazar(actualizada);
        this.toast.success(`${u.sigla ?? u.nombre}: plan cambiado a ${actualizada.plan?.nombre}.`);
      },
      error: (err: HttpErrorResponse) => {
        this.procesandoId.set(null);
        this.toast.error(mensajeDeError(err, 'No se pudo cambiar el plan.'));
      },
    });
  }

  registrarPago(u: ResumenInstitucion): void {
    this.procesandoId.set(u.id);
    this.planesService.registrarPago<ResumenInstitucion>(u.id).subscribe({
      next: (actualizada) => {
        this.reemplazar(actualizada);
        this.cargarPagos();
        this.toast.success(`${u.sigla ?? u.nombre}: pago registrado hasta el ${this.fecha(actualizada.plan?.pago_hasta)}.`);
      },
      error: (err: HttpErrorResponse) => {
        this.procesandoId.set(null);
        this.toast.error(mensajeDeError(err, 'No se pudo registrar el pago.'));
      },
    });
  }

  // ─── Pago con tarjeta (admin de la universidad) ─────────────────────────

  pagarConTarjeta(): void {
    if (this.pagando()) return;
    this.pagando.set(true);
    this.planesService.iniciarPagoConTarjeta().subscribe({
      // Stripe Checkout es una página externa: al terminar vuelve a esta ruta con ?pago=...
      next: ({ url }) => window.location.assign(url),
      error: (err: HttpErrorResponse) => {
        this.pagando.set(false);
        this.toast.error(mensajeDeError(err, 'No se pudo iniciar el pago con tarjeta.'));
      },
    });
  }

  private atenderRegresoDeStripe(): void {
    const pago = this.route.snapshot.queryParamMap.get('pago');
    if (!pago) return;
    // Se limpia la URL para que recargar la página no vuelva a mostrar el aviso.
    void this.router.navigate([], { queryParams: { pago: null }, queryParamsHandling: 'merge', replaceUrl: true });
    if (pago === 'cancelado') {
      this.avisoPago.set({ tipo: 'info', texto: 'Cancelaste el pago. Tu plan sigue igual; podés pagarlo cuando quieras.' });
      return;
    }
    this.avisoPago.set({ tipo: 'info', texto: 'Verificando el pago con Stripe…' });
    this.planesService.confirmarPago(pago).subscribe({
      next: (r) => {
        this.avisoPago.set(this.avisoDeConfirmacion(r));
        if (r.estado === 'paid') {
          this.cargar();
          this.cargarPagos();
        }
      },
      error: (err: HttpErrorResponse) =>
        this.avisoPago.set({ tipo: 'error', texto: mensajeDeError(err, 'No se pudo verificar el pago con Stripe.') }),
    });
  }

  private avisoDeConfirmacion(r: ConfirmacionPago): AvisoPago {
    if (r.estado === 'paid') {
      return { tipo: 'ok', texto: `¡Pago recibido! Tu plan ${r.plan_nombre} está al día hasta el ${this.fecha(r.pagado_hasta)}.` };
    }
    if (r.estado === 'expired') {
      return { tipo: 'error', texto: 'La sesión de pago venció sin completarse. Podés intentarlo de nuevo.' };
    }
    return { tipo: 'info', texto: 'Stripe todavía está procesando el pago. Actualizá la página en unos minutos.' };
  }

  fecha(valor: string | null | undefined): string {
    if (!valor) return '—';
    const [anio, mes, dia] = valor.slice(0, 10).split('-');
    return `${dia}/${mes}/${anio}`;
  }

  private reemplazar(actualizada: ResumenInstitucion): void {
    this.resumen.update((lista) => lista.map((u) => (u.id === actualizada.id ? actualizada : u)));
    this.planElegido.update((sel) => {
      const copia = { ...sel };
      delete copia[actualizada.id];
      return copia;
    });
    this.procesandoId.set(null);
  }

  // ─── Solicitudes de alta (superadmin) ───────────────────────────────────

  abrirAprobacion(solicitud: SolicitudUniversidad): void {
    this.aprobacion.set({ solicitud, password: generarPassword(), guardando: false, error: '', creada: null, copia: 'idle' });
  }

  cerrarAprobacion(): void {
    this.aprobacion.set(null);
  }

  regenerarPassword(): void {
    this.aprobacion.update((a) => (a ? { ...a, password: generarPassword() } : a));
  }

  actualizarPassword(valor: string): void {
    this.aprobacion.update((a) => (a ? { ...a, password: valor } : a));
  }

  confirmarAprobacion(): void {
    const a = this.aprobacion();
    if (!a || a.guardando) return;
    if (a.password.length < 8) {
      this.aprobacion.set({ ...a, error: 'La contraseña temporal debe tener al menos 8 caracteres.' });
      return;
    }
    this.aprobacion.set({ ...a, guardando: true, error: '' });
    this.planesService.aprobar(a.solicitud.id, a.password).subscribe({
      next: (r) => {
        this.aprobacion.set({
          ...a,
          guardando: false,
          creada: { universidad: r.universidad, correo: r.admin_correo, password: a.password, detalle: r.detalle },
        });
        this.solicitudes.update((lista) => lista.filter((s) => s.id !== a.solicitud.id));
        this.cargar();
      },
      error: (err: HttpErrorResponse) =>
        this.aprobacion.set({ ...a, guardando: false, error: mensajeDeError(err, 'No se pudo aprobar la solicitud.') }),
    });
  }

  copiarCredenciales(): void {
    const a = this.aprobacion();
    if (!a?.creada) return;
    const texto = [
      `Acceso a EGRESA — Administrador de ${a.creada.universidad}`,
      `Ingreso: ${window.location.origin}/auth/login`,
      `Correo: ${a.creada.correo}`,
      `Contraseña temporal: ${a.creada.password} (se cambia en el primer ingreso)`,
    ].join('\n');
    void copiarAlPortapapeles(texto).then((ok) =>
      this.aprobacion.update((actual) => (actual ? { ...actual, copia: ok ? 'ok' : 'error' } : actual)),
    );
  }

  iniciarRechazo(solicitud: SolicitudUniversidad): void {
    this.rechazandoId.set(solicitud.id);
    this.motivoRechazo = '';
  }

  confirmarRechazo(solicitud: SolicitudUniversidad): void {
    const motivo = this.motivoRechazo.trim();
    if (motivo.length < 3) {
      this.toast.warning('Indicá el motivo del rechazo.');
      return;
    }
    this.procesandoId.set(solicitud.id);
    this.planesService.rechazar(solicitud.id, motivo).subscribe({
      next: () => {
        this.procesandoId.set(null);
        this.rechazandoId.set(null);
        this.solicitudes.update((lista) => lista.filter((s) => s.id !== solicitud.id));
        this.toast.success(`Solicitud de ${solicitud.sigla} rechazada.`);
      },
      error: (err: HttpErrorResponse) => {
        this.procesandoId.set(null);
        this.toast.error(mensajeDeError(err, 'No se pudo rechazar la solicitud.'));
      },
    });
  }
}
