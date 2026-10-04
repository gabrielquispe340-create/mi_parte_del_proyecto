import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb, kReleaseMode;

/// Resuelve la URL base de la API FastAPI. Los APK de release (flutter build apk)
/// usan el backend de producción en Railway; en desarrollo (flutter run) se usa
/// el backend local. El emulador de Android no puede usar "localhost" para
/// llegar a la máquina host: necesita la IP especial 10.0.2.2.
class ApiConfig {
  ApiConfig._();

  /// Cambiá esto si el backend corre en otro host/puerto.
  static const String _hostLocal = '127.0.0.1:8000';

  /// IP de la PC en la red WiFi local, para probar desde un celular físico
  /// (el celular y la PC deben estar en la MISMA red WiFi). Actualizala si
  /// cambia la IP de tu PC (correr "ipconfig" y buscar "Dirección IPv4").
  static const String _hostRedLocal = '192.168.1.110:8000';

  /// true = compilando para probar en un celular físico por WiFi.
  /// false = emulador Android / Chrome / Windows en la misma PC del backend.
  static const bool _usarRedLocal = bool.fromEnvironment(
    'CELULAR_FISICO',
    defaultValue: false,
  );

  /// Sitio web de EGRESA, para lo que se gestiona solo desde la web.
  static const String urlWeb = 'https://egresa.up.railway.app';

  /// Backend de producción (Railway): funciona con cualquier conexión a internet.
  static const String _urlProduccion = 'https://backend-production-24e5.up.railway.app/api';

  /// URL completa de otro backend; si se define, tiene prioridad sobre lo demás.
  /// Ejemplo: flutter run --dart-define=API_URL=https://otro-backend/api
  static const String _apiUrl = String.fromEnvironment('API_URL');

  static String get baseUrl {
    if (_apiUrl.isNotEmpty) {
      return _apiUrl;
    }
    if (_usarRedLocal) {
      return 'http://$_hostRedLocal/api';
    }
    if (kReleaseMode) {
      return _urlProduccion;
    }
    if (kIsWeb) {
      return 'http://$_hostLocal/api';
    }
    if (Platform.isAndroid) {
      return 'http://10.0.2.2:8000/api';
    }
    return 'http://$_hostLocal/api';
  }
}
