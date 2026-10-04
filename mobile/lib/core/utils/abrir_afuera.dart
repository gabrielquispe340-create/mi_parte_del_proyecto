import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

/// El enlace lo escribe la empresa: solo se abren direcciones http(s), y si
/// viene sin esquema ("meet.google.com/abc") se asume https.
Uri? enlaceSeguro(String texto) {
  final limpio = texto.trim();
  final uri = Uri.tryParse(limpio.contains('://') ? limpio : 'https://$limpio');
  if (uri == null || !(uri.scheme == 'https' || uri.scheme == 'http') || uri.host.isEmpty) return null;
  return uri;
}

/// Abre [uri] en otra app; si no se puede, copia [texto] y avisa con [siFalla].
Future<void> abrirAfuera(BuildContext context, Uri? uri, String texto, String siFalla) async {
  var abierto = false;
  if (uri != null) {
    try {
      abierto = await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      abierto = false;
    }
  }
  if (abierto || !context.mounted) return;
  await Clipboard.setData(ClipboardData(text: texto));
  if (!context.mounted) return;
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(siFalla)));
}

Future<void> abrirVideollamada(BuildContext context, String enlace) => abrirAfuera(
  context,
  enlaceSeguro(enlace),
  enlace,
  'No se pudo abrir el enlace. Lo copiamos para que lo pegues en tu navegador.',
);

Future<void> abrirMapa(BuildContext context, String lugar) => abrirAfuera(
  context,
  Uri.https('www.google.com', '/maps/search/', {'api': '1', 'query': lugar}),
  lugar,
  'No se pudo abrir el mapa. Copiamos la dirección.',
);

Future<void> escribirCorreo(BuildContext context, String correo) =>
    abrirAfuera(context, Uri(scheme: 'mailto', path: correo), correo, 'No hay una app de correo. Copiamos la dirección.');

Future<void> llamar(BuildContext context, String telefono) => abrirAfuera(
  context,
  Uri(scheme: 'tel', path: telefono.replaceAll(RegExp(r'[^\d+]'), '')),
  telefono,
  'No se pudo abrir el teléfono. Copiamos el número.',
);
