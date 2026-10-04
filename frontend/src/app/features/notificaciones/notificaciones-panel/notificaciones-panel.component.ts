import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Notificacion, PreferenciasNotificacion } from '../../../core/models/notificacion.models';
import { NotificacionService } from '../../../core/services/notificacion.service';
import { AuthService } from '../../auth/auth.service';

@Component({
  selector: 'app-notificaciones-panel',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './notificaciones-panel.component.html',
  styleUrl: './notificaciones-panel.component.scss',
})
export class NotificacionesPanelComponent implements OnInit {
  private readonly notifService = inject(NotificacionService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  tabActiva: 'historial' | 'preferencias' = 'historial';
  filtroActual: 'todas' | 'no_leidas' = 'todas';

  // Historial
  notificaciones: Notificacion[] = [];
  total = 0;
  noLeidas = 0;
  isLoadingHistorial = false;

  // Preferencias
  preferencias: PreferenciasNotificacion = {
    email_notifications: true,
    push_enabled: true,
    in_app_enabled: true,
    notify_stage_changes: true,
    notify_job_matches: true,
    notify_interview_events: true,
    notify_messages: true,
  };
  isLoadingPreferencias = false;
  isSavingPreferencias = false;
  get pushSoportado(): boolean {
    return typeof window !== 'undefined' && 'Notification' in window;
  }
  get permisoPushConcedido(): boolean {
    return this.notifService.tienePermisoWebPush();
  }

  // Toast / Mensajes
  mensajeExito: string | null = null;
  mensajeError: string | null = null;

  ngOnInit(): void {
    if (!this.auth.estaAutenticado()) {
      this.router.navigate(['/auth/login']);
      return;
    }
    this.cargarHistorial();
    this.cargarPreferencias();
  }

  async togglePushPermiso(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    if (input.checked) {
      const concedido = await this.notifService.solicitarPermisoWebPush();
      if (!concedido) {
        this.preferencias.push_enabled = false;
        input.checked = false;
        this.mostrarMensaje('El navegador no tiene permiso para enviar notificaciones Push. Habilítalo en los ajustes del sitio.', true);
      } else {
        this.preferencias.push_enabled = true;
        this.mostrarMensaje('Notificaciones Push del navegador activadas exitosamente.');
      }
    } else {
      this.preferencias.push_enabled = false;
    }
  }

  probarNotificacionPush(): void {
    if (!this.notifService.tienePermisoWebPush()) {
      this.notifService.solicitarPermisoWebPush().then((concedido) => {
        if (concedido) {
          this.notifService.emitirNotificacionWebPush('🔔 Notificación Push de Prueba', {
            body: '¡Excelente! Las notificaciones Push de escritorio están funcionando activas en tu navegador.',
            link: '/notificaciones',
          });
        } else {
          this.mostrarMensaje('Debes permitir las notificaciones en el navegador para recibir Push.', true);
        }
      });
    } else {
      this.notifService.emitirNotificacionWebPush('🔔 Notificación Push de Prueba', {
        body: '¡Excelente! Las notificaciones Push de escritorio están funcionando activas en tu navegador.',
        link: '/notificaciones',
      });
      this.mostrarMensaje('Se ha enviado la notificación Push a tu sistema operativo / navegador.');
    }
  }

  cargarHistorial(): void {
    this.isLoadingHistorial = true;
    const soloNoLeidas = this.filtroActual === 'no_leidas';
    this.notifService.listarNotificaciones(50, 0, soloNoLeidas).subscribe({
      next: (res) => {
        this.notificaciones = res.items;
        this.total = res.total;
        this.noLeidas = res.no_leidas;
        this.isLoadingHistorial = false;
      },
      error: () => {
        this.isLoadingHistorial = false;
        this.mostrarMensaje('Error al cargar el historial de notificaciones.', true);
      },
    });
  }

  cambiarFiltro(filtro: 'todas' | 'no_leidas'): void {
    this.filtroActual = filtro;
    this.cargarHistorial();
  }

  marcarComoLeida(notif: Notificacion): void {
    if (notif.leida) return;
    this.notifService.marcarComoLeida(notif.id).subscribe({
      next: () => {
        notif.leida = true;
        notif.read_at = new Date().toISOString();
        this.noLeidas = Math.max(0, this.noLeidas - 1);
      },
    });
  }

  marcarTodasComoLeidas(): void {
    this.notifService.marcarTodasComoLeidas().subscribe({
      next: () => {
        this.notificaciones.forEach((n) => {
          n.leida = true;
          n.read_at = new Date().toISOString();
        });
        this.noLeidas = 0;
        this.mostrarMensaje('Todas las notificaciones fueron marcadas como leídas.');
      },
    });
  }

  eliminarNotificacion(notif: Notificacion, event: Event): void {
    event.stopPropagation();
    this.notifService.eliminarNotificacion(notif.id).subscribe({
      next: () => {
        this.notificaciones = this.notificaciones.filter((n) => n.id !== notif.id);
        this.total = Math.max(0, this.total - 1);
        if (!notif.leida) {
          this.noLeidas = Math.max(0, this.noLeidas - 1);
        }
        this.mostrarMensaje('Notificación eliminada.');
      },
    });
  }

  navegarNotificacion(notif: Notificacion): void {
    this.marcarComoLeida(notif);
    if (notif.link) {
      this.router.navigateByUrl(notif.link);
    }
  }

  // --- PREFERENCIAS ---
  cargarPreferencias(): void {
    this.isLoadingPreferencias = true;
    this.notifService.obtenerPreferencias().subscribe({
      next: (p) => {
        this.preferencias = p;
        this.isLoadingPreferencias = false;
      },
      error: () => {
        this.isLoadingPreferencias = false;
      },
    });
  }

  guardarPreferencias(): void {
    this.isSavingPreferencias = true;
    this.notifService.actualizarPreferencias(this.preferencias).subscribe({
      next: (p) => {
        this.preferencias = p;
        this.isSavingPreferencias = false;
        this.mostrarMensaje('Preferencias de notificación guardadas exitosamente.');
      },
      error: () => {
        this.isSavingPreferencias = false;
        this.mostrarMensaje('No se pudieron guardar las preferencias.', true);
      },
    });
  }

  getIconoTipo(tipo: string): string {
    switch (tipo) {
      case 'stage_change':
        return '📈';
      case 'job_match':
        return '✨';
      case 'interview_scheduled':
      case 'interview_status':
        return '📅';
      case 'message_received':
        return '💬';
      default:
        return '🔔';
    }
  }

  mostrarMensaje(msg: string, isError = false): void {
    if (isError) {
      this.mensajeError = msg;
      setTimeout(() => (this.mensajeError = null), 4000);
    } else {
      this.mensajeExito = msg;
      setTimeout(() => (this.mensajeExito = null), 4000);
    }
  }
}
