import '../models/entrevista.dart';
import 'api_config.dart';
import 'api_http.dart';

/// Entrevistas del egresado (HU-20): las mismas rutas que usa la web en
/// Mis postulaciones (backend/app/features/entrevistas/router.py).
class EntrevistaService {
  /// GET /postulaciones/{id}/entrevistas, de la más nueva a la más vieja.
  Future<List<Entrevista>> listar(String accessToken, String postulacionId) async {
    final respuesta = await obtener(
      Uri.parse('${ApiConfig.baseUrl}/postulaciones/$postulacionId/entrevistas'),
      accessToken: accessToken,
    );
    if (respuesta.statusCode != 200) {
      throw ApiException(mensajeDeError(respuesta, 'No se pudieron cargar las entrevistas.'), codigo: respuesta.statusCode);
    }
    final entrevistas = <Entrevista>[];
    for (final item in decodificar(respuesta) as List<dynamic>) {
      // Una fila con datos inesperados se omite en vez de romper toda la pantalla.
      final entrevista = Entrevista.tryFromJson(item);
      if (entrevista != null) entrevistas.add(entrevista);
    }
    return entrevistas..sort((a, b) => b.creada.compareTo(a.creada));
  }

  /// Entrevistas de varias postulaciones a la vez. Si una falla se omite, para
  /// que un error puntual no deje sin datos al resto de la pantalla; la sesión
  /// vencida (401) sí se propaga, para no disfrazarla de "sin entrevistas".
  Future<Map<String, List<Entrevista>>> deVariasPostulaciones(
    String accessToken,
    Iterable<String> postulacionIds,
  ) async {
    final pares = await Future.wait(
      postulacionIds.map((id) async {
        try {
          return MapEntry(id, await listar(accessToken, id));
        } on ApiException catch (e) {
          if (e.codigo == 401) rethrow;
          return MapEntry(id, const <Entrevista>[]);
        } catch (_) {
          return MapEntry(id, const <Entrevista>[]);
        }
      }),
    );
    return Map.fromEntries(pares);
  }

  /// POST /postulaciones/entrevistas/{id}/confirmar
  Future<Entrevista> confirmar(String accessToken, String entrevistaId) async {
    final respuesta = await enviar(
      Uri.parse('${ApiConfig.baseUrl}/postulaciones/entrevistas/$entrevistaId/confirmar'),
      accessToken: accessToken,
    );
    if (respuesta.statusCode != 200) {
      throw ApiException(mensajeDeError(respuesta, 'No se pudo confirmar la entrevista.'), codigo: respuesta.statusCode);
    }
    return Entrevista.fromJson(decodificar(respuesta) as Map<String, dynamic>);
  }

  /// POST /postulaciones/entrevistas/{id}/rechazar con el motivo (3 a 1000 caracteres).
  Future<Entrevista> rechazar(String accessToken, String entrevistaId, String motivo) async {
    final respuesta = await enviar(
      Uri.parse('${ApiConfig.baseUrl}/postulaciones/entrevistas/$entrevistaId/rechazar'),
      accessToken: accessToken,
      cuerpo: {'motivo': motivo.trim()},
    );
    if (respuesta.statusCode != 200) {
      throw ApiException(mensajeDeError(respuesta, 'No se pudo enviar tu respuesta.'), codigo: respuesta.statusCode);
    }
    return Entrevista.fromJson(decodificar(respuesta) as Map<String, dynamic>);
  }
}
