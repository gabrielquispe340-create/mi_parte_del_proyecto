import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Indicador de carga centrado, con un texto opcional debajo.
class VistaCargando extends StatelessWidget {
  final String? mensaje;
  const VistaCargando({super.key, this.mensaje});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(width: 28, height: 28, child: CircularProgressIndicator(strokeWidth: 2.6)),
          if (mensaje != null) ...[
            const SizedBox(height: 16),
            Text(mensaje!, textAlign: TextAlign.center, style: const TextStyle(color: AppColors.textoSuave)),
          ],
        ],
      ),
    );
  }
}

/// Estado vacío o de error: ícono en un círculo, título, explicación y acción.
class VistaMensaje extends StatelessWidget {
  final IconData icono;
  final String titulo;
  final String? mensaje;
  final String? textoAccion;
  final VoidCallback? onAccion;
  final Color color;
  final Color fondo;

  const VistaMensaje({
    super.key,
    required this.icono,
    required this.titulo,
    this.mensaje,
    this.textoAccion,
    this.onAccion,
    this.color = AppColors.primario,
    this.fondo = AppColors.primarioSuave,
  });

  /// Error de red o del servidor, con botón para reintentar.
  factory VistaMensaje.error(Object? error, {required VoidCallback onReintentar}) => VistaMensaje(
        icono: Icons.cloud_off_rounded,
        titulo: 'No pudimos cargar la información',
        mensaje: '$error',
        textoAccion: 'Reintentar',
        onAccion: onReintentar,
        color: AppColors.peligro,
        fondo: AppColors.peligroSuave,
      );

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(color: fondo, shape: BoxShape.circle),
              child: Icon(icono, size: 34, color: color),
            ),
            const SizedBox(height: 18),
            Text(titulo, textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleMedium),
            if (mensaje != null) ...[
              const SizedBox(height: 6),
              Text(mensaje!, textAlign: TextAlign.center, style: const TextStyle(color: AppColors.textoSuave)),
            ],
            if (textoAccion != null && onAccion != null) ...[
              const SizedBox(height: 20),
              OutlinedButton(onPressed: onAccion, child: Text(textoAccion!)),
            ],
          ],
        ),
      ),
    );
  }
}
