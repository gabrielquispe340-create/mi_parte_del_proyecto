import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/sesion.dart';
import 'api_config.dart';

/// Excepción con el mensaje de error legible que ya devuelve el backend
/// (detail de FastAPI), para no mostrar errores técnicos en la UI.
class AuthException implements Exception {
  final String mensaje;
  const AuthException(this.mensaje);

  @override
  String toString() => mensaje;
}

/// Consume el mismo endpoint /auth/login que usa el frontend web
/// (backend/app/features/auth/router.py), sin mocks: es la misma Supabase.
class AuthService {
  Future<Sesion> login(String correo, String password) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/auth/login');

    late final http.Response respuesta;
    try {
      respuesta = await http
          .post(
            uri,
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'correo': correo, 'password': password}),
          )
          .timeout(const Duration(seconds: 15));
    } catch (_) {
      throw const AuthException(
        'No se pudo conectar con el servidor. Revisá tu conexión a internet e intentá de nuevo.',
      );
    }

    final cuerpo = jsonDecode(utf8.decode(respuesta.bodyBytes)) as Map<String, dynamic>;

    if (respuesta.statusCode == 200) {
      return Sesion.fromJson(cuerpo);
    }

    final detalle = cuerpo['detail'];
    final mensaje = detalle is String
        ? detalle
        : 'Correo o contraseña incorrectos.';
    throw AuthException(mensaje);
  }

  /// POST /auth/cambiar-password: cambia la contraseña del usuario autenticado.
  /// El backend devuelve tokens nuevos, que reemplazan a los de la sesión actual.
  Future<Sesion> cambiarPassword(String accessToken, String passwordActual, String passwordNueva) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/auth/cambiar-password');

    late final http.Response respuesta;
    try {
      respuesta = await http
          .post(
            uri,
            headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer $accessToken'},
            body: jsonEncode({'password_actual': passwordActual, 'password_nueva': passwordNueva}),
          )
          .timeout(const Duration(seconds: 15));
    } catch (_) {
      throw const AuthException(
        'No se pudo conectar con el servidor. Revisá tu conexión a internet e intentá de nuevo.',
      );
    }

    final cuerpo = jsonDecode(utf8.decode(respuesta.bodyBytes)) as Map<String, dynamic>;

    if (respuesta.statusCode == 200) {
      return Sesion.fromJson(cuerpo);
    }

    final detalle = cuerpo['detail'];
    throw AuthException(detalle is String ? detalle : 'No se pudo cambiar la contraseña.');
  }
}
