import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/models/sesion.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/marca.dart';
import '../perfil/egresado_panel_screen.dart';
import 'login_screen.dart';

const _urlWeb = 'https://egresa.up.railway.app';

/// Punto de entrada post-login. La app móvil es para egresados; las cuentas
/// de empresa y de administración se gestionan desde la web.
class HomeScreen extends StatelessWidget {
  final Sesion sesion;

  const HomeScreen({super.key, required this.sesion});

  String get _rolLegible => switch (sesion.rol) {
        'empresa' => 'empresa',
        'moderator' => 'moderador',
        'platform_admin' => sesion.institucionNombre == null ? 'superadministrador' : 'administrador universitario',
        _ => sesion.rol,
      };

  @override
  Widget build(BuildContext context) {
    if (sesion.rol == 'candidate') {
      return EgresadoPanelScreen(sesion: sesion);
    }
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Align(alignment: Alignment.centerLeft, child: MarcaEgresa(tamano: 22)),
              const Spacer(),
              Container(
                width: 72,
                height: 72,
                alignment: Alignment.center,
                decoration: const BoxDecoration(color: AppColors.primarioSuave, shape: BoxShape.circle),
                child: const Icon(Icons.desktop_windows_outlined, size: 34, color: AppColors.primario),
              ),
              const SizedBox(height: 20),
              Text(
                'Tu cuenta se gestiona desde la web',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text(
                'Ingresaste como $_rolLegible. La app móvil está pensada para egresados; '
                'el panel de ${sesion.rol == 'empresa' ? 'tu empresa' : 'administración'} está disponible en la web.',
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.textoSuave),
              ),
              const Spacer(),
              FilledButton.icon(
                onPressed: () => launchUrl(Uri.parse(_urlWeb), mode: LaunchMode.externalApplication),
                icon: const Icon(Icons.open_in_new_rounded),
                label: const Text('Abrir EGRESA en el navegador'),
              ),
              const SizedBox(height: 10),
              OutlinedButton(
                onPressed: () => Navigator.of(context).pushAndRemoveUntil(
                  MaterialPageRoute(builder: (_) => const LoginScreen()),
                  (_) => false,
                ),
                child: const Text('Cerrar sesión'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
