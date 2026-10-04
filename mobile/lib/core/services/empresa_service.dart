import '../models/entrevista.dart';
import '../models/postulante_nuevo.dart';
import 'api_config.dart';
import 'api_http.dart';

/// App de empresas: postulantes sin revisar y agenda de entrevistas
/// (backend/app/features/seleccion y entrevistas, lado empresa).
class EmpresaService {
  /// GET /seleccion/postulantes-nuevos
  Future<PostulantesNuevos> postulantesNuevos(String accessToken) async {
    final respuesta = await obtener(
      Uri.parse('${ApiConfig.baseUrl}/seleccion/postulantes-nuevos'),
      accessToken: accessToken,
    );
    if (respuesta.statusCode != 200) {
      throw ApiException(mensajeDeError(respuesta, 'No se pudieron cargar los postulantes.'), codigo: respuesta.statusCode);
    }
    return PostulantesNuevos.fromJson(decodificar(respuesta) as Map<String, dynamic>);
  }

  /// GET /seleccion/entrevistas: las que empiezan entre [desde] y [hasta]
  /// (hora local del teléfono), ordenadas por hora.
  Future<List<Entrevista>> agenda(String accessToken, DateTime desde, DateTime hasta) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/seleccion/entrevistas').replace(
      queryParameters: {'desde': desde.toUtc().toIso8601String(), 'hasta': hasta.toUtc().toIso8601String()},
    );
    final respuesta = await obtener(uri, accessToken: accessToken);
    if (respuesta.statusCode != 200) {
      throw ApiException(mensajeDeError(respuesta, 'No se pudo cargar la agenda.'), codigo: respuesta.statusCode);
    }
    final entrevistas = <Entrevista>[];
    for (final item in decodificar(respuesta) as List<dynamic>) {
      // Una fila con datos inesperados se omite en vez de romper la agenda.
      final entrevista = Entrevista.tryFromJson(item);
      if (entrevista != null) entrevistas.add(entrevista);
    }
    return entrevistas;
  }
}
