import 'dart:convert';

import 'package:http/http.dart' as http;

/// Error con un mensaje listo para mostrar al usuario.
class ApiException implements Exception {
  final String mensaje;
  final int? codigo;
  const ApiException(this.mensaje, {this.codigo});

  @override
  String toString() => mensaje;
}

const mensajeSinConexion = 'No se pudo conectar con el servidor. Revisá tu conexión a internet e intentá de nuevo.';
const _espera = Duration(seconds: 20);

Map<String, String> encabezados(String? accessToken, {bool json = false}) => {
      if (accessToken != null) 'Authorization': 'Bearer $accessToken',
      if (json) 'Content-Type': 'application/json',
    };

/// FastAPI responde JSON sin charset, y http lo decodificaría como latin-1
/// ("LogÃ­stica"); por eso siempre se decodifica como UTF-8.
dynamic decodificar(http.Response respuesta) =>
    respuesta.bodyBytes.isEmpty ? null : jsonDecode(utf8.decode(respuesta.bodyBytes));

/// Mensaje del backend ("detail") o, si no hay uno legible, el mensaje por defecto.
String mensajeDeError(http.Response respuesta, String porDefecto) {
  try {
    final cuerpo = decodificar(respuesta);
    final detalle = cuerpo is Map ? cuerpo['detail'] : null;
    if (detalle is String && detalle.isNotEmpty) return detalle;
  } catch (_) {
    // Respuesta que no es JSON (por ejemplo, un error del proxy).
  }
  return porDefecto;
}

Future<http.Response> obtener(Uri uri, {String? accessToken}) async {
  try {
    return await http.get(uri, headers: encabezados(accessToken)).timeout(_espera);
  } catch (_) {
    throw const ApiException(mensajeSinConexion);
  }
}

Future<http.Response> enviar(Uri uri, {String? accessToken, Object? cuerpo}) async {
  try {
    return await http
        .post(uri, headers: encabezados(accessToken, json: true), body: jsonEncode(cuerpo ?? const {}))
        .timeout(_espera);
  } catch (_) {
    throw const ApiException(mensajeSinConexion);
  }
}
