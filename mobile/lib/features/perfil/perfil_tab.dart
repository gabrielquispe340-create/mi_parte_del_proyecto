import 'package:flutter/material.dart';

import '../../core/models/perfil_egresado.dart';
import '../../core/models/sesion.dart';
import '../../core/services/perfil_service.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/formatos.dart';
import '../../core/widgets/insignia.dart';
import '../../core/widgets/vistas_estado.dart';
import '../auth/cambiar_password_screen.dart';
import '../inicio/inicio_tab.dart';
import '../notificaciones/notificaciones_screen.dart';
import '../notificaciones/preferencias_notificaciones_screen.dart';
import 'editar_perfil_screen.dart';
import 'mi_cv_screen.dart';

/// Pestaña de perfil: datos del egresado, su CV y la cuenta.
class PerfilTab extends StatefulWidget {
  final Sesion sesion;
  final ValueChanged<Sesion> onSesionActualizada;
  final VoidCallback onCerrarSesion;

  const PerfilTab({
    super.key,
    required this.sesion,
    required this.onSesionActualizada,
    required this.onCerrarSesion,
  });

  @override
  State<PerfilTab> createState() => _PerfilTabState();
}

class _PerfilTabState extends State<PerfilTab> {
  final _servicio = PerfilService();
  late Future<PerfilEgresado> _futuro = _servicio.obtenerMiPerfil(widget.sesion.accessToken);

  void _recargar() {
    if (mounted) setState(() => _futuro = _servicio.obtenerMiPerfil(widget.sesion.accessToken));
  }

  Future<void> _editar(PerfilEgresado perfil) async {
    final actualizado = await Navigator.of(context).push<PerfilEgresado>(
      MaterialPageRoute(builder: (_) => EditarPerfilScreen(accessToken: widget.sesion.accessToken, perfil: perfil)),
    );
    if (actualizado != null && mounted) setState(() => _futuro = Future.value(actualizado));
  }

  Future<void> _abrirCv() async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => MiCvScreen(accessToken: widget.sesion.accessToken)),
    );
    if (mounted) _recargar();
  }

  Future<void> _abrirNotificaciones() async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => NotificacionesScreen(accessToken: widget.sesion.accessToken)),
    );
  }

  Future<void> _abrirPreferencias() async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => PreferenciasNotificacionesScreen(accessToken: widget.sesion.accessToken)),
    );
  }

  Future<void> _cambiarPassword() async {
    final nueva = await Navigator.of(context).push<Sesion>(
      MaterialPageRoute(builder: (_) => CambiarPasswordScreen(accessToken: widget.sesion.accessToken)),
    );
    if (nueva != null) widget.onSesionActualizada(nueva);
  }

  Future<void> _confirmarCierre() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (contexto) => AlertDialog(
        title: const Text('Cerrar sesión'),
        content: const Text('¿Querés cerrar tu sesión en este dispositivo?'),
        actions: [
          TextButton(onPressed: () => Navigator.of(contexto).pop(false), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.of(contexto).pop(true), child: const Text('Cerrar sesión')),
        ],
      ),
    );
    if (ok == true) widget.onCerrarSesion();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Mi perfil')),
      body: FutureBuilder<PerfilEgresado>(
        future: _futuro,
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            if (snapshot.connectionState == ConnectionState.waiting) return const VistaCargando();
            return VistaMensaje.error(snapshot.error, onReintentar: _recargar);
          }
          final perfil = snapshot.data!;
          return RefreshIndicator(
            onRefresh: () async => _recargar(),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
              children: [
                _Encabezado(perfil: perfil, universidad: widget.sesion.institucionNombre),
                if (perfil.resumenProfesional != null && perfil.resumenProfesional!.trim().isNotEmpty) ...[
                  const SizedBox(height: 16),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                     child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Sobre mí', style: Theme.of(context).textTheme.titleSmall),
                          const SizedBox(height: 6),
                          Text(perfil.resumenProfesional!.trim()),
                        ],
                      ),
                    ),
                  ),
                ],
                const SizedBox(height: 16),
                Card(
                  child: Column(
                    children: [
                      _Opcion(
                        icono: Icons.description_outlined,
                        titulo: 'Mi CV',
                        subtitulo: 'Formación, experiencia, idiomas, certificaciones y habilidades',
                        onTap: _abrirCv,
                      ),
                      const Divider(indent: 60),
                      _Opcion(
                        icono: Icons.notifications_active_outlined,
                        titulo: 'Notificaciones y Alertas',
                        subtitulo: 'Avisos de postulaciones, vacantes afines y push Firebase',
                        onTap: _abrirNotificaciones,
                      ),
                      const Divider(indent: 60),
                      _Opcion(
                        icono: Icons.tune_outlined,
                        titulo: 'Preferencias de Notificación',
                        subtitulo: 'Canales y frecuencias de alertas por tipo',
                        onTap: _abrirPreferencias,
                      ),
                      const Divider(indent: 60),
                      _Opcion(
                        icono: Icons.badge_outlined,
                        titulo: 'Datos personales',
                        subtitulo: 'Nombre, contacto, ciudad y disponibilidad',
                        onTap: () => _editar(perfil),
                      ),
                      const Divider(indent: 60),
                      _Opcion(
                        icono: Icons.key_outlined,
                        titulo: 'Cambiar contraseña',
                        onTap: _cambiarPassword,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                Card(
                  child: _Opcion(
                    icono: Icons.logout_rounded,
                    titulo: 'Cerrar sesión',
                    color: AppColors.peligro,
                    onTap: _confirmarCierre,
                  ),
                ),
                const SizedBox(height: 28),
                const Text(
                  'EGRESA · Bolsa de trabajo universitaria',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppColors.textoSuave, fontSize: 12),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _Encabezado extends StatelessWidget {
  final PerfilEgresado perfil;
  final String? universidad;
  const _Encabezado({required this.perfil, required this.universidad});

  @override
  Widget build(BuildContext context) {
    final porcentaje = perfil.porcentajeCompletitud.clamp(0, 100);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            CircleAvatar(
              radius: 36,
              backgroundColor: AppColors.primario,
              child: Text(
                iniciales(perfil.nombreCompleto),
                style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w700),
              ),
            ),
            const SizedBox(height: 12),
            Text(perfil.nombreCompleto, textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleLarge),
            if (perfil.tituloProfesional != null && perfil.tituloProfesional!.isNotEmpty) ...[
              const SizedBox(height: 2),
              Text(
                perfil.tituloProfesional!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.textoSuave),
              ),
            ],
            const SizedBox(height: 10),
            Wrap(
              alignment: WrapAlignment.center,
              spacing: 14,
              runSpacing: 6,
              children: [
                if (universidad != null) DatoConIcono(Icons.school_outlined, universidad!),
                if (perfil.ciudad != null && perfil.ciudad!.isNotEmpty) DatoConIcono(Icons.location_on_outlined, perfil.ciudad!),
              ],
            ),
            const SizedBox(height: 12),
            InsigniaValidacion(perfil.estadoValidacion),
            const SizedBox(height: 16),
            Row(
              children: [
                const Text('Perfil completo', style: TextStyle(color: AppColors.textoSuave, fontSize: 13)),
                const SizedBox(width: 12),
                Expanded(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(99),
                    child: LinearProgressIndicator(value: porcentaje / 100, minHeight: 7),
                  ),
                ),
                const SizedBox(width: 10),
                Text('$porcentaje%', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Opcion extends StatelessWidget {
  final IconData icono;
  final String titulo;
  final String? subtitulo;
  final VoidCallback onTap;
  final Color? color;
  const _Opcion({required this.icono, required this.titulo, this.subtitulo, required this.onTap, this.color});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      leading: Container(
        width: 36,
        height: 36,
        decoration: BoxDecoration(
          color: color == null ? AppColors.primarioSuave : AppColors.peligroSuave,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Icon(icono, size: 20, color: color ?? AppColors.primario),
      ),
      title: Text(titulo, style: color == null ? null : TextStyle(color: color)),
      subtitle: subtitulo == null ? null : Text(subtitulo!),
      trailing: color == null ? const Icon(Icons.chevron_right_rounded, color: AppColors.textoTenue) : null,
      onTap: onTap,
    );
  }
}
