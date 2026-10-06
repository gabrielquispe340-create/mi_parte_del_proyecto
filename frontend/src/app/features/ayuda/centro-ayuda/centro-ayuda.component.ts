import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { AuthService } from '../../auth/auth.service';
import {
  AUDIENCIAS,
  Audiencia,
  TEMAS_AYUDA,
  TemaAyuda,
  audienciaDeRol,
  buscarTemas,
} from '../ayuda.contenido';

/** Centro de ayuda (requisito 4): todos los temas, con buscador y filtro por tipo de cuenta. */
@Component({
  selector: 'app-centro-ayuda',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './centro-ayuda.component.html',
  styleUrl: './centro-ayuda.component.scss',
})
export class CentroAyudaComponent implements OnInit {
  private readonly ruta = inject(ActivatedRoute);
  readonly auth = inject(AuthService);

  readonly audiencias = AUDIENCIAS;
  readonly consulta = signal('');
  readonly audiencia = signal<Audiencia | 'todas'>('todas');
  readonly abierto = signal<string | null>(null);

  readonly volverA = computed(() => {
    const rol = this.auth.rol();
    if (!this.auth.token()) return '/vacantes';
    return rol === 'platform_admin' || rol === 'moderator'
      ? '/admin'
      : rol === 'empresa'
        ? '/dashboard'
        : '/vacantes';
  });

  readonly temas = computed(() => {
    const audiencia = this.audiencia();
    const base =
      audiencia === 'todas' ? TEMAS_AYUDA : TEMAS_AYUDA.filter((t) => t.audiencia === audiencia);
    return buscarTemas(this.consulta(), base);
  });

  readonly porAudiencia = computed(() =>
    AUDIENCIAS.map((a) => ({
      ...a,
      temas: this.temas().filter((t) => t.audiencia === a.clave),
    })).filter((g) => g.temas.length > 0),
  );

  ngOnInit(): void {
    const propia = audienciaDeRol(this.auth.rol());
    if (propia && this.auth.token()) this.audiencia.set(propia);
    const tema = this.ruta.snapshot.queryParamMap.get('tema');
    const elegido = TEMAS_AYUDA.find((t) => t.id === tema);
    if (elegido) {
      this.audiencia.set('todas');
      this.abierto.set(elegido.id);
      setTimeout(
        () => document.getElementById('tema-' + elegido.id)?.scrollIntoView({ block: 'start' }),
        50,
      );
    }
  }

  alternar(tema: TemaAyuda): void {
    this.abierto.update((actual) => (actual === tema.id ? null : tema.id));
  }

  buscar(texto: string): void {
    this.consulta.set(texto);
    if (texto.trim()) this.audiencia.set('todas');
  }
}
