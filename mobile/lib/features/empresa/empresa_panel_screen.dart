import 'package:flutter/material.dart';

import '../../core/models/sesion.dart';
import '../../core/services/api_config.dart';
import '../../core/services/mensaje_service.dart';
import '../../core/services/push_service.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/abrir_afuera.dart';
import '../../core/widgets/boton_ayuda.dart';
import '../auth/login_screen.dart';
import '../mensajes/bandeja_mensajes_screen.dart';
import 'agenda_tab.dart';
import 'postulantes_tab.dart';

/// App de empresas: solo lo que conviene tener a mano en el celular
/// (postulantes nuevos, entrevistas del día y mensajes con los candidatos).
/// Publicar vacantes y mover el proceso de selección sigue en la web.
class EmpresaPanelScreen extends StatefulWidget {
  final Sesion sesion;

  const EmpresaPanelScreen({super.key, required this.sesion});

  @override
  State<EmpresaPanelScreen> createState() => _EmpresaPanelScreenState();
}

class _EmpresaPanelScreenState extends State<EmpresaPanelScreen> {
  static const _postulantes = 0;
  static const _mensajes = 2;

  int _indice = _postulantes;
  int _noLeidos = 0;

  /// Las pestañas se construyen recién la primera vez que se visitan.
  final _visitadas = {_postulantes};

  /// Al volver a una pestaña se recarga, para ver lo que llegó mientras tanto.
  final _versiones = [0, 0, 0];

  @override
  void initState() {
    super.initState();
    _contarNoLeidos();
    PushService.instancia.activar(widget.sesion.accessToken);
  }

  /// El contador de la pestaña Mensajes es un extra: si falla, no se muestra.
  Future<void> _contarNoLeidos() async {
    try {
      final conversaciones = await MensajeService().conversaciones(widget.sesion.accessToken);
      _actualizarNoLeidos(conversaciones.fold(0, (total, c) => total + c.noLeidos));
    } catch (_) {
      // La pestaña Mensajes muestra el error al abrirla.
    }
  }

  void _actualizarNoLeidos(int total) {
    if (mounted && total != _noLeidos) setState(() => _noLeidos = total);
  }

  void _irA(int indice) {
    setState(() {
      if (!_visitadas.add(indice) && indice != _indice) _versiones[indice]++;
      _indice = indice;
    });
    // La bandeja informa sus no leídos al cargar; desde las otras pestañas se consulta.
    if (indice != _mensajes) _contarNoLeidos();
  }

  void _cerrarSesion() {
    PushService.instancia.desactivar();
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (_) => false,
    );
  }

  Widget _siVisitada(int indice, Widget pestana) => _visitadas.contains(indice) ? pestana : const SizedBox.shrink();

  @override
  Widget build(BuildContext context) {
    final token = widget.sesion.accessToken;
    final menu = MenuCuentaEmpresa(onCerrarSesion: _cerrarSesion);
    List<Widget> acciones(String temaAyuda) => [BotonAyuda(temaAyuda, esEmpresa: true), menu];

    return PopScope(
      // El botón atrás de Android vuelve primero a Postulantes en vez de cerrar la app.
      canPop: _indice == _postulantes,
      onPopInvokedWithResult: (seCerro, _) {
        if (!seCerro) _irA(_postulantes);
      },
      child: Scaffold(
        body: IndexedStack(
          index: _indice,
          children: [
            PostulantesTab(
              key: ValueKey('postulantes-${_versiones[0]}'),
              accessToken: token,
              acciones: acciones('postulantes'),
            ),
            _siVisitada(
              1,
              AgendaTab(key: ValueKey('agenda-${_versiones[1]}'), accessToken: token, acciones: acciones('agenda')),
            ),
            _siVisitada(
              2,
              BandejaMensajesScreen(
                key: ValueKey('mensajes-${_versiones[2]}'),
                accessToken: token,
                esEmpresa: true,
                acciones: acciones('mensajes'),
                onNoLeidos: _actualizarNoLeidos,
              ),
            ),
          ],
        ),
        bottomNavigationBar: DecoratedBox(
          decoration: const BoxDecoration(border: Border(top: BorderSide(color: AppColors.borde))),
          child: NavigationBar(
            selectedIndex: _indice,
            onDestinationSelected: _irA,
            destinations: [
              const NavigationDestination(
                icon: Icon(Icons.person_search_outlined),
                selectedIcon: Icon(Icons.person_search_rounded),
                label: 'Postulantes',
              ),
              const NavigationDestination(
                icon: Icon(Icons.event_outlined),
                selectedIcon: Icon(Icons.event_rounded),
                label: 'Entrevistas',
              ),
              NavigationDestination(
                icon: Badge(
                  isLabelVisible: _noLeidos > 0,
                  label: Text(_noLeidos > 99 ? '99+' : '$_noLeidos'),
                  child: const Icon(Icons.forum_outlined),
                ),
                selectedIcon: Badge(
                  isLabelVisible: _noLeidos > 0,
                  label: Text(_noLeidos > 99 ? '99+' : '$_noLeidos'),
                  child: const Icon(Icons.forum_rounded),
                ),
                label: 'Mensajes',
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Menú de la cuenta en la barra superior de cada pestaña.
class MenuCuentaEmpresa extends StatelessWidget {
  final VoidCallback onCerrarSesion;
  const MenuCuentaEmpresa({super.key, required this.onCerrarSesion});

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<String>(
      tooltip: 'Tu cuenta',
      icon: const Icon(Icons.account_circle_outlined),
      onSelected: (opcion) {
        if (opcion == 'web') {
          abrirAfuera(
            context,
            Uri.parse(ApiConfig.urlWeb),
            ApiConfig.urlWeb,
            'No se pudo abrir el navegador. Copiamos la dirección.',
          );
        } else {
          onCerrarSesion();
        }
      },
      itemBuilder: (_) => const [
        PopupMenuItem(
          value: 'web',
          child: ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.open_in_new_rounded),
            title: Text('Abrir el panel web'),
            subtitle: Text('Vacantes y proceso de selección'),
          ),
        ),
        PopupMenuItem(
          value: 'salir',
          child: ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.logout_rounded),
            title: Text('Cerrar sesión'),
          ),
        ),
      ],
    );
  }
}
