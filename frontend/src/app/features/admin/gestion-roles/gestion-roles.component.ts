import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { PaginadorComponent, paginar } from '../../../shared/components/paginador/paginador.component';
import { copiarAlPortapapeles, generarPassword } from '../../../shared/utils/password';
import { AuthService } from '../../auth/auth.service';
import {
  ETIQUETAS_ROL,
  NuevoUsuarioStaff,
  Rol,
  UniversidadCliente,
  UsuarioAdmin,
} from './gestion-roles.model';
import { GestionRolesService } from './gestion-roles.service';
import { PermisoDirective } from '../../../shared/directives/permiso.directive';

interface Credenciales {
  correo: string;
  password: string;
  rol: string;
  institucion: string | null;
}

function mensajeDeError(err: HttpErrorResponse, porDefecto: string): string {
  return typeof err.error?.detail === 'string' ? err.error.detail : porDefecto;
}

@Component({
  selector: 'app-gestion-roles',
  standalone: true,
  imports: [FormsModule, PaginadorComponent, RouterLink, PermisoDirective],
  templateUrl: './gestion-roles.html',
  styleUrl: './gestion-roles.scss',
})
export class GestionRolesComponent {
  private readonly service = inject(GestionRolesService);
  readonly auth = inject(AuthService);

  readonly etiquetasRol = ETIQUETAS_ROL;
  readonly esSuperadmin = computed(() => !this.auth.institucion());

  // Alta de personal institucional (admin / moderador)
  readonly modalAbierto = signal(false);
  readonly universidades = signal<UniversidadCliente[]>([]);
  readonly creando = signal(false);
  readonly errorNuevo = signal('');
  readonly credenciales = signal<Credenciales | null>(null);
  readonly estadoCopia = signal<'idle' | 'ok' | 'error'>('idle');
  nuevo: NuevoUsuarioStaff = this.formularioVacio();

  readonly rolesAsignables = signal<Rol[]>([]);
  readonly usuarios = signal<UsuarioAdmin[]>([]);
  readonly seleccionados = signal<Record<string, string>>({});
  readonly busqueda = signal('');
  readonly cargando = signal(false);
  readonly guardandoId = signal<string | null>(null);
  readonly error = signal('');
  readonly mensaje = signal('');
  readonly pagina = signal(1);
  readonly tamanio = signal(10);

  readonly filtrados = computed(() => {
    const texto = this.busqueda().trim().toLowerCase();
    if (!texto) return this.usuarios();
    return this.usuarios().filter(
      (u) =>
        u.correo.toLowerCase().includes(texto) ||
        this.rolPrincipal(u).toLowerCase().includes(texto),
    );
  });

  readonly usuariosPagina = computed(() => paginar(this.filtrados(), this.pagina(), this.tamanio()));

  buscar(texto: string): void {
    this.busqueda.set(texto);
    this.pagina.set(1);
  }

  rolPrincipal(usuario: UsuarioAdmin): string {
    if (usuario.roles.length > 0) return ETIQUETAS_ROL[usuario.roles[0]] ?? usuario.roles[0];
    if (usuario.es_miembro_empresa) return 'Empresa';
    return 'Sin rol';
  }

  rolActual(usuario: UsuarioAdmin): string {
    const sel = this.seleccionados()[usuario.id];
    if (sel) return sel;
    if (usuario.roles.length > 0) return usuario.roles[0];
    return '';
  }

  cambioPendiente(usuario: UsuarioAdmin): boolean {
    const actual = usuario.roles[0] ?? '';
    return this.rolActual(usuario) !== actual;
  }

  ngOnInit(): void {
    this.cargar();
  }

  cargar(): void {
    const token = this.auth.token();
    if (!token) {
      this.error.set('Inicia sesión como administrador para gestionar los roles.');
      return;
    }

    this.cargando.set(true);
    this.error.set('');
    this.service.listarUsuarios(token).subscribe({
      next: (usuarios) => {
        this.usuarios.set(usuarios);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set('No se pudo cargar la lista de usuarios. Verifica que seas administrador.');
        this.cargando.set(false);
      },
    });

    this.service.listarRoles(token).subscribe({
      next: (roles) => this.rolesAsignables.set(roles),
      error: () => {
        /* el listado de usuarios no depende de este catálogo */
      },
    });
  }

  seleccionarRol(usuarioId: string, rol: string): void {
    this.seleccionados.update((sels) => ({ ...sels, [usuarioId]: rol }));
  }

  guardar(usuario: UsuarioAdmin): void {
    const rol = this.rolActual(usuario);
    if (!rol) {
      this.error.set('Selecciona un rol antes de guardar.');
      return;
    }

    this.guardandoId.set(usuario.id);
    this.error.set('');
    this.mensaje.set('');

    this.service.asignarRol(this.auth.token(), usuario.id, rol).subscribe({
      next: (respuesta) => {
        this.usuarios.update((lista) => lista.map((u) => (u.id === usuario.id ? respuesta.usuario : u)));
        this.seleccionados.update((sels) => {
          const copia = { ...sels };
          delete copia[usuario.id];
          return copia;
        });
        this.guardandoId.set(null);
        this.mensaje.set(`${respuesta.usuario.correo}: ${respuesta.detalle}`);
      },
      error: (err: HttpErrorResponse) => {
        this.guardandoId.set(null);
        this.error.set(mensajeDeError(err, 'No se pudo asignar el rol. Inténtalo de nuevo.'));
      },
    });
  }

  abrirNuevo(): void {
    this.nuevo = this.formularioVacio();
    this.errorNuevo.set('');
    this.credenciales.set(null);
    this.estadoCopia.set('idle');
    this.modalAbierto.set(true);
    if (this.esSuperadmin() && this.universidades().length === 0) {
      this.service.listarUniversidades().subscribe({
        next: (lista) => this.universidades.set(lista),
        error: () => this.errorNuevo.set('No se pudo cargar la lista de universidades.'),
      });
    }
  }

  cerrarNuevo(): void {
    this.modalAbierto.set(false);
  }

  regenerarPassword(): void {
    this.nuevo.password = generarPassword();
  }

  crearUsuario(): void {
    const correo = this.nuevo.correo.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(correo)) {
      this.errorNuevo.set('Ingresá un correo válido.');
      return;
    }
    if (this.nuevo.password.length < 8) {
      this.errorNuevo.set('La contraseña inicial debe tener al menos 8 caracteres.');
      return;
    }
    if (this.esSuperadmin() && !this.nuevo.institucion_id) {
      this.errorNuevo.set('Elegí la universidad a la que pertenece.');
      return;
    }

    const datos: NuevoUsuarioStaff = {
      correo,
      password: this.nuevo.password,
      // El admin de una universidad solo crea moderadores de la suya (el backend lo exige igual).
      rol: this.esSuperadmin() ? this.nuevo.rol : 'moderator',
      institucion_id: this.esSuperadmin() ? this.nuevo.institucion_id : null,
    };
    this.creando.set(true);
    this.errorNuevo.set('');
    this.service.crearUsuario(this.auth.token(), datos).subscribe({
      next: (usuario) => {
        this.usuarios.update((lista) => [usuario, ...lista]);
        this.busqueda.set('');
        this.pagina.set(1);
        this.credenciales.set({
          correo: usuario.correo,
          password: datos.password,
          rol: ETIQUETAS_ROL[datos.rol],
          institucion: usuario.institucion,
        });
        this.creando.set(false);
      },
      error: (err: HttpErrorResponse) => {
        this.creando.set(false);
        this.errorNuevo.set(mensajeDeError(err, 'No se pudo crear el usuario. Revisá los datos.'));
      },
    });
  }

  copiarCredenciales(): void {
    const c = this.credenciales();
    if (!c) return;
    const texto = [
      `Acceso a EGRESA — ${c.rol}${c.institucion ? ` (${c.institucion})` : ''}`,
      `Ingreso: ${window.location.origin}/auth/login`,
      `Correo: ${c.correo}`,
      `Contraseña: ${c.password}`,
    ].join('\n');
    void copiarAlPortapapeles(texto).then((ok) => this.estadoCopia.set(ok ? 'ok' : 'error'));
  }

  private formularioVacio(): NuevoUsuarioStaff {
    return {
      correo: '',
      password: generarPassword(),
      rol: this.esSuperadmin() ? 'platform_admin' : 'moderator',
      institucion_id: null,
    };
  }
}
