import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import {
  Component,
  ElementRef,
  Input,
  OnChanges,
  SimpleChanges,
  ViewChild,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  AdjuntoMensajeOut,
  ConversacionPostulacionOut,
  MensajeOut,
} from '../comunicacion.models';
import { ComunicacionService } from '../comunicacion.service';

const MAX_BYTES_ADJUNTO = 5 * 1024 * 1024; // 5 MB

@Component({
  selector: 'app-hilo-mensajes',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './hilo-mensajes.component.html',
  styleUrl: './hilo-mensajes.component.scss',
})
export class HiloMensajesComponent implements OnChanges {
  private readonly svc = inject(ComunicacionService);

  @Input({ required: true }) postulacionId!: string;
  @Input() modoVista: 'empresa' | 'candidato' = 'empresa';

  @ViewChild('contenedorMensajes') contenedorMensajes?: ElementRef<HTMLDivElement>;
  @ViewChild('inputArchivo') inputArchivo?: ElementRef<HTMLInputElement>;

  conversacion = signal<ConversacionPostulacionOut | null>(null);
  mensajes = signal<MensajeOut[]>([]);
  cargando = signal<boolean>(false);
  enviando = signal<boolean>(false);
  descargandoId = signal<string | null>(null);
  error = signal<string | null>(null);

  nuevoMensaje = signal<string>('');
  archivoSeleccionado = signal<File | null>(null);

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['postulacionId'] && this.postulacionId) {
      this.limpiarFormulario();
      this.cargarConversacion();
    }
  }

  cargarConversacion(): void {
    if (!this.postulacionId) return;
    this.cargando.set(true);
    this.error.set(null);

    this.svc.obtenerMensajesPostulacion(this.postulacionId).subscribe({
      next: (data) => {
        this.conversacion.set(data);
        this.mensajes.set(data.mensajes ?? []);
        this.cargando.set(false);
        this.desplazarAlFinal();
      },
      error: (e: HttpErrorResponse) => {
        this.cargando.set(false);
        this.error.set(
          e.error?.detail ?? 'No se pudo cargar el historial de mensajes.'
        );
      },
    });
  }

  seleccionarArchivo(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    this.error.set(null);

    if (!file) {
      this.archivoSeleccionado.set(null);
      return;
    }

    if (file.size === 0) {
      this.error.set('El archivo seleccionado está vacío.');
      input.value = '';
      this.archivoSeleccionado.set(null);
      return;
    }

    if (file.size > MAX_BYTES_ADJUNTO) {
      this.error.set(
        `El archivo «${file.name}» (${this.formatearTamano(file.size)}) supera el límite máximo permitido de 5 MB.`
      );
      input.value = '';
      this.archivoSeleccionado.set(null);
      return;
    }

    this.archivoSeleccionado.set(file);
  }

  quitarArchivo(): void {
    this.archivoSeleccionado.set(null);
    if (this.inputArchivo?.nativeElement) {
      this.inputArchivo.nativeElement.value = '';
    }
  }

  puedeEnviar(): boolean {
    if (this.enviando()) return false;
    return (
      this.nuevoMensaje().trim().length > 0 ||
      this.archivoSeleccionado() !== null
    );
  }

  enviarMensaje(): void {
    if (!this.puedeEnviar() || !this.postulacionId) return;

    this.enviando.set(true);
    this.error.set(null);

    const texto = this.nuevoMensaje();
    const archivo = this.archivoSeleccionado();

    this.svc
      .enviarMensajePostulacion(this.postulacionId, texto, archivo)
      .subscribe({
        next: (msg) => {
          this.mensajes.update((lista) => [...lista, msg]);
          this.limpiarFormulario();
          this.enviando.set(false);
          this.desplazarAlFinal();
        },
        error: (e: HttpErrorResponse) => {
          this.enviando.set(false);
          this.error.set(
            e.error?.detail ?? 'No se pudo enviar el mensaje. Intenta nuevamente.'
          );
        },
      });
  }

  manejarTeclaEnter(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.enviarMensaje();
    }
  }

  descargarAdjunto(adjunto: AdjuntoMensajeOut): void {
    if (this.descargandoId()) return;
    this.descargandoId.set(adjunto.id);
    this.error.set(null);

    this.svc.descargarAdjunto(adjunto.id).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = adjunto.original_filename || 'adjunto';
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        this.descargandoId.set(null);
      },
      error: (e: HttpErrorResponse) => {
        this.descargandoId.set(null);
        this.error.set(
          e.error?.detail ?? 'No se pudo descargar el archivo adjunto.'
        );
      },
    });
  }

  formatearHora(iso: string): string {
    if (!iso) return '';
    return new Date(iso).toLocaleString('es-BO', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  formatearTamano(bytes?: number | null): string {
    if (bytes === null || bytes === undefined) return '';
    if (bytes < 1024) return `${bytes} B`;
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    const mb = kb / 1024;
    return `${mb.toFixed(2)} MB`;
  }

  private limpiarFormulario(): void {
    this.nuevoMensaje.set('');
    this.quitarArchivo();
  }

  private desplazarAlFinal(): void {
    setTimeout(() => {
      const el = this.contenedorMensajes?.nativeElement;
      if (el) {
        el.scrollTop = el.scrollHeight;
      }
    }, 50);
  }
}
