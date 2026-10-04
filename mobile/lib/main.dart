import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'core/services/push_service.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/login_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await PushService.inicializarFirebase();
  runApp(const EgresaApp());
}

class EgresaApp extends StatelessWidget {
  const EgresaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'EGRESA',
      debugShowCheckedModeBanner: false,
      scaffoldMessengerKey: mensajeroGlobal,
      theme: AppTheme.claro(),
      locale: const Locale('es'),
      supportedLocales: const [Locale('es')],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      // Android dibuja la app detrás de la barra de navegación del sistema:
      // se reserva ese espacio para que no tape el final de las pantallas.
      builder: (context, child) => AnnotatedRegion<SystemUiOverlayStyle>(
        value: AppTheme.barrasSistema,
        child: ColoredBox(
          color: AppColors.superficie,
          child: SafeArea(top: false, left: false, right: false, child: child!),
        ),
      ),
      home: const LoginScreen(),
    );
  }
}
