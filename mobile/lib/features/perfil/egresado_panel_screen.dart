import 'package:flutter/material.dart';

import '../../core/models/perfil_egresado.dart';
import '../../core/models/sesion.dart';
import '../../core/services/perfil_service.dart';
import '../auth/cambiar_password_screen.dart';
import '../auth/login_screen.dart';
import '../notificaciones/notificaciones_screen.dart';
import '../postulaciones/mis_postulaciones_screen.dart';
import '../recomendaciones/recomendaciones_screen.dart';
import '../vacantes/vacantes_screen.dart';
import '../../core/services/notificacion_service.dart';
import 'editar_perfil_screen.dart';
import 'mi_cv_screen.dart';

/// Panel principal del egresado: muestra su perfil real (GET /perfiles/me)
/// y accesos a las funcionalidades disponibles, en vez de una pantalla
/// genérica de "sesión iniciada".
class EgresadoPanelScreen extends StatefulWidget {
  final Sesion sesion;

  const EgresadoPanelScreen({super.key, required this.sesion});

  @override
  State<EgresadoPanelScreen> createState() => _EgresadoPanelScreenState();
}

class _EgresadoPanelScreenState extends State<EgresadoPanelScreen> {
  final _servicio = PerfilService();
  final _notifService = NotificacionService();
  late Future<PerfilEgresado> _futuroPerfil;
  int _noLeidas = 0;

  /// Se reemplaza al cambiar la contraseña, porque el backend emite tokens nuevos.
  late Sesion _sesion = widget.sesion;

  @override
  void initState() {
    super.initState();
    _futuroPerfil = _servicio.obtenerMiPerfil(_sesion.accessToken);
    _cargarNotificaciones();
  }

  Future<void> _cargarNotificaciones() async {
    final count = await _notifService.obtenerContadorNoLeidas(_sesion.accessToken);
    if (!mounted) return;
    setState(() => _noLeidas = count);
  }

  void _recargar() {
    setState(() {
      _futuroPerfil = _servicio.obtenerMiPerfil(_sesion.accessToken);
    });
    _cargarNotificaciones();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Mi panel'),
        actions: [
          Stack(
            alignment: Alignment.center,
            children: [
              IconButton(
                icon: const Icon(Icons.notifications_outlined),
                tooltip: 'Notificaciones',
                onPressed: () async {
                  await Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => NotificacionesScreen(accessToken: _sesion.accessToken),
                    ),
                  );
                  _cargarNotificaciones();
                },
              ),
              if (_noLeidas > 0)
                Positioned(
                  top: 8,
                  right: 8,
                  child: Container(
                    padding: const EdgeInsets.all(4),
                    decoration: const BoxDecoration(
                      color: Colors.red,
                      shape: BoxShape.circle,
                    ),
                    constraints: const BoxConstraints(minWidth: 16, minHeight: 16),
                    child: Text(
                      '$_noLeidas',
                      style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                      textAlign: TextAlign.center,
                    ),
                  ),
                ),
            ],
          ),
          IconButton(
            icon: const Icon(Icons.edit_outlined),
            tooltip: 'Editar perfil',
            onPressed: () async {
              final perfilActual = await _futuroPerfil;
              if (!context.mounted) return;
              final actualizado = await Navigator.of(context).push<PerfilEgresado>(
                MaterialPageRoute(
                  builder: (_) => EditarPerfilScreen(accessToken: _sesion.accessToken, perfil: perfilActual),
                ),
              );
              if (actualizado != null) {
                setState(() => _futuroPerfil = Future.value(actualizado));
              }
            },
          ),
          IconButton(
            icon: const Icon(Icons.key_outlined),
            tooltip: 'Cambiar contraseña',
            onPressed: () async {
              final nueva = await Navigator.of(context).push<Sesion>(
                MaterialPageRoute(builder: (_) => CambiarPasswordScreen(accessToken: _sesion.accessToken)),
              );
              if (nueva != null) setState(() => _sesion = nueva);
            },
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Cerrar sesión',
            onPressed: () {
              Navigator.of(context).pushReplacement(
                MaterialPageRoute(builder: (_) => const LoginScreen()),
              );
            },
          ),
        ],
      ),
      body: FutureBuilder<PerfilEgresado>(
        future: _futuroPerfil,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.error_outline, color: Colors.red.shade400, size: 48),
                    const SizedBox(height: 12),
                    Text('${snapshot.error}', textAlign: TextAlign.center),
                    const SizedBox(height: 12),
                    ElevatedButton(onPressed: _recargar, child: const Text('Reintentar')),
                  ],
                ),
              ),
            );
          }

          final perfil = snapshot.data!;
          return RefreshIndicator(
            onRefresh: () async => _recargar(),
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                _tarjetaPerfil(context, perfil),
                const SizedBox(height: 20),
                Text('Accesos', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                _accesoMiCv(context),
                const SizedBox(height: 12),
                _accesoNotificaciones(context),
                const SizedBox(height: 12),
                _accesoVacantes(context),
                const SizedBox(height: 12),
                _accesoRecomendaciones(context),
                const SizedBox(height: 12),
                _accesoMisPostulaciones(context),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _tarjetaPerfil(BuildContext context, PerfilEgresado perfil) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 28,
                  backgroundColor: Colors.indigo.shade100,
                  child: Text(
                    perfil.nombres.isNotEmpty ? perfil.nombres[0].toUpperCase() : '?',
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.indigo.shade700),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        perfil.nombreCompleto,
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
                      ),
                      if (perfil.tituloProfesional != null && perfil.tituloProfesional!.isNotEmpty)
                        Text(perfil.tituloProfesional!, style: TextStyle(color: Colors.grey[700])),
                      if (perfil.ciudad != null && perfil.ciudad!.isNotEmpty)
                        Text(perfil.ciudad!, style: TextStyle(color: Colors.grey[500], fontSize: 13)),
                      if (_sesion.institucionNombre != null)
                        Text(_sesion.institucionNombre!, style: TextStyle(color: Colors.indigo.shade400, fontSize: 13)),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                _etiquetaEstado(perfil.estadoValidacion),
                const SizedBox(width: 8),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Perfil completo: ${perfil.porcentajeCompletitud}%', style: const TextStyle(fontSize: 12)),
                      const SizedBox(height: 4),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: perfil.porcentajeCompletitud / 100,
                          minHeight: 6,
                          backgroundColor: Colors.grey.shade200,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if (perfil.resumenProfesional != null && perfil.resumenProfesional!.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(perfil.resumenProfesional!),
            ],
          ],
        ),
      ),
    );
  }

  Widget _etiquetaEstado(String estado) {
    final Color color;
    final String texto;
    switch (estado) {
      case 'APROBADO':
        color = Colors.green;
        texto = 'Validado';
        break;
      case 'RECHAZADO':
        color = Colors.red;
        texto = 'Rechazado';
        break;
      default:
        color = Colors.orange;
        texto = 'Pendiente';
    }
    return Chip(
      label: Text(texto, style: const TextStyle(color: Colors.white, fontSize: 12)),
      backgroundColor: color,
      visualDensity: VisualDensity.compact,
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
    );
  }

  Widget _accesoMiCv(BuildContext context) {
    return Card(
      child: ListTile(
        leading: const Icon(Icons.description_outlined),
        title: const Text('Mi CV'),
        subtitle: const Text('Formación, experiencia, idiomas, certificaciones y habilidades'),
        trailing: const Icon(Icons.chevron_right),
        onTap: () {
          Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => MiCvScreen(accessToken: _sesion.accessToken),
            ),
          );
        },
      ),
    );
  }

  Widget _accesoMisPostulaciones(BuildContext context) {
    return Card(
      child: ListTile(
        leading: const Icon(Icons.assignment_turned_in_outlined),
        title: const Text('Mis postulaciones'),
        subtitle: const Text('Seguí el estado de tus postulaciones y retiralas si querés'),
        trailing: const Icon(Icons.chevron_right),
        onTap: () {
          Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => MisPostulacionesScreen(accessToken: _sesion.accessToken),
            ),
          );
        },
      ),
    );
  }

  Widget _accesoRecomendaciones(BuildContext context) {
    return Card(
      child: ListTile(
        leading: const Icon(Icons.auto_awesome_outlined),
        title: const Text('Vacantes recomendadas'),
        subtitle: const Text('Ordenadas por afinidad con tu perfil, con el porqué de cada porcentaje'),
        trailing: const Icon(Icons.chevron_right),
        onTap: () {
          Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => RecomendacionesScreen(accessToken: _sesion.accessToken),
            ),
          );
        },
      ),
    );
  }

  Widget _accesoVacantes(BuildContext context) {
    return Card(
      child: ListTile(
        leading: const Icon(Icons.work_outline),
        title: const Text('Vacantes disponibles'),
        subtitle: const Text('Explorá las ofertas publicadas por las empresas'),
        trailing: const Icon(Icons.chevron_right),
        onTap: () {
          Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => VacantesScreen(accessToken: _sesion.accessToken),
            ),
          );
        },
      ),
    );
  }

  Widget _accesoNotificaciones(BuildContext context) {
    return Card(
      child: ListTile(
        leading: Badge(
          isLabelVisible: _noLeidas > 0,
          label: Text('$_noLeidas'),
          child: const Icon(Icons.notifications_active_outlined, color: Colors.indigo),
        ),
        title: const Text('Notificaciones y Alertas'),
        subtitle: const Text('Avisos de postulaciones, vacantes afines y preferencias'),
        trailing: const Icon(Icons.chevron_right),
        onTap: () async {
          await Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => NotificacionesScreen(accessToken: _sesion.accessToken),
            ),
          );
          _cargarNotificaciones();
        },
      ),
    );
  }
}
