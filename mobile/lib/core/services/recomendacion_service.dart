import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/recomendacion.dart';
import 'api_config.dart';

/// Excepción con el mensaje de error legible que ya devuelve el backend.
/// [noDisponible] es true cuando el servicio de recomendaciones está apagado
/// (503, CP04 de la HU-23), para mostrar un aviso en vez de un error.
class RecomendacionException implements Exception {
  final String mensaje;
  final bool noDisponible;
  const RecomendacionException(this.mensaje, {this.noDisponible = false});

  @override
  String toString() => mensaje;
}

/// Consume GET /ia/recomendaciones (backend/app/features/ia/router.py), el mismo
/// endpoint que usa la web: vacantes vigentes ordenadas por afinidad con el perfil.
class RecomendacionService {
  Future<Recomendaciones> obtener(String accessToken) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/ia/recomendaciones');

    late final http.Response respuesta;
    try {
      respuesta = await http
          .get(uri, headers: {'Authorization': 'Bearer $accessToken'})
          .timeout(const Duration(seconds: 30));
    } catch (_) {
      throw const RecomendacionException(
        'No se pudo conectar con el servidor. Verificá que el backend esté corriendo y la URL configurada.',
      );
    }

    final cuerpo = jsonDecode(utf8.decode(respuesta.bodyBytes)) as Map<String, dynamic>;

    if (respuesta.statusCode == 200) {
      return Recomendaciones.fromJson(cuerpo);
    }

    final detalle = cuerpo['detail'];
    if (respuesta.statusCode == 503) {
      throw RecomendacionException(
        detalle is String ? detalle : 'El servicio de recomendaciones no está disponible en este momento.',
        noDisponible: true,
      );
    }
    throw RecomendacionException(detalle is String ? detalle : 'No se pudieron calcular tus recomendaciones.');
  }
}
