import 'dart:convert';
import 'package:http/http.dart' as http;

import '../models/notificacion.dart';
import 'api_config.dart';

class NotificacionException implements Exception {
  final String mensaje;
  const NotificacionException(this.mensaje);

  @override
  String toString() => mensaje;
}

class NotificacionService {
  /// Obtiene el contador de notificaciones no leídas
  Future<int> obtenerContadorNoLeidas(String accessToken) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/notificaciones/contador-no-leidas');
    try {
      final res = await http.get(
        uri,
        headers: {'Authorization': 'Bearer $accessToken'},
      ).timeout(const Duration(seconds: 15));

      if (res.statusCode == 200) {
        final data = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
        return (data['no_leidas'] as num?)?.toInt() ?? 0;
      }
      return 0;
    } catch (_) {
      return 0;
    }
  }

  /// Obtiene la lista paginada de notificaciones
  Future<NotificacionesListResponse> listarNotificaciones(
    String accessToken, {
    int limit = 50,
    int offset = 0,
    bool soloNoLeidas = false,
  }) async {
    final uri = Uri.parse(
      '${ApiConfig.baseUrl}/notificaciones?limit=$limit&offset=$offset&solo_no_leidas=$soloNoLeidas',
    );

    late final http.Response res;
    try {
      res = await http.get(
        uri,
        headers: {'Authorization': 'Bearer $accessToken'},
      ).timeout(const Duration(seconds: 20));
    } catch (_) {
      throw const NotificacionException('No se pudo conectar con el servidor de notificaciones.');
    }

    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
      return NotificacionesListResponse.fromJson(data);
    }

    throw const NotificacionException('Error al cargar las notificaciones.');
  }

  /// Marca una notificación como leída
  Future<void> marcarComoLeida(String accessToken, String notificacionId) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/notificaciones/$notificacionId/leer');
    try {
      await http.patch(
        uri,
        headers: {'Authorization': 'Bearer $accessToken'},
      ).timeout(const Duration(seconds: 15));
    } catch (_) {}
  }

  /// Marca todas las notificaciones como leídas
  Future<void> marcarTodasComoLeidas(String accessToken) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/notificaciones/marcar-todas-leidas');
    try {
      await http.post(
        uri,
        headers: {'Authorization': 'Bearer $accessToken'},
      ).timeout(const Duration(seconds: 15));
    } catch (_) {}
  }

  /// Elimina una notificación
  Future<void> eliminarNotificacion(String accessToken, String notificacionId) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/notificaciones/$notificacionId');
    try {
      await http.delete(
        uri,
        headers: {'Authorization': 'Bearer $accessToken'},
      ).timeout(const Duration(seconds: 15));
    } catch (_) {}
  }

  /// Obtiene las preferencias de notificación del usuario
  Future<PreferenciasNotificacion> obtenerPreferencias(String accessToken) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/notificaciones/preferencias');

    try {
      final res = await http.get(
        uri,
        headers: {'Authorization': 'Bearer $accessToken'},
      ).timeout(const Duration(seconds: 15));

      if (res.statusCode == 200) {
        final data = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
        return PreferenciasNotificacion.fromJson(data);
      }
    } catch (_) {}

    return const PreferenciasNotificacion();
  }

  /// Actualiza las preferencias de notificación del usuario
  Future<PreferenciasNotificacion> actualizarPreferencias(
    String accessToken,
    PreferenciasNotificacion prefs,
  ) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/notificaciones/preferencias');

    try {
      final res = await http.put(
        uri,
        headers: {
          'Authorization': 'Bearer $accessToken',
          'Content-Type': 'application/json',
        },
        body: jsonEncode(prefs.toJson()),
      ).timeout(const Duration(seconds: 15));

      if (res.statusCode == 200) {
        final data = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
        return PreferenciasNotificacion.fromJson(data);
      }
    } catch (_) {}

    return prefs;
  }
}
