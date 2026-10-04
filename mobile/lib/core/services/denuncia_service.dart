import 'api_config.dart';
import 'api_http.dart';

/// Motivos de denuncia (HU-22); el valor coincide con moderation_report.category.
const motivosDenuncia = <({String valor, String etiqueta, String ayuda})>[
  (valor: 'fraud', etiqueta: 'Fraude o estafa', ayuda: 'Piden dinero, datos bancarios o un pago para postular.'),
  (valor: 'fake_information', etiqueta: 'Información falsa', ayuda: 'La empresa, el sueldo o el puesto no son reales.'),
  (valor: 'discrimination', etiqueta: 'Discriminación', ayuda: 'Excluye por género, edad, origen u otra condición.'),
  (valor: 'inappropriate', etiqueta: 'Contenido inapropiado', ayuda: 'Lenguaje ofensivo o contenido que no es una oferta.'),
  (valor: 'spam', etiqueta: 'Spam o publicidad', ayuda: 'Promociona cursos, productos o es una oferta repetida.'),
  (valor: 'other', etiqueta: 'Otro motivo', ayuda: 'Contanos qué pasó.'),
];

/// Caracteres de detalle para que la denuncia cuente para ocultar la oferta (igual que el backend).
const minimoFundamento = 20;

/// Denuncia de ofertas sospechosas (backend/app/features/moderacion).
class DenunciaService {
  /// POST /moderacion/vacantes/{id}/denuncias. Devuelve el mensaje para mostrar.
  /// Si el usuario ya la había denunciado, lanza [ApiException] con código 409.
  Future<String> denunciar(String accessToken, String vacanteId, String categoria, String? descripcion) async {
    final respuesta = await enviar(
      Uri.parse('${ApiConfig.baseUrl}/moderacion/vacantes/$vacanteId/denuncias'),
      accessToken: accessToken,
      cuerpo: {'categoria': categoria, 'descripcion': descripcion},
    );
    if (respuesta.statusCode != 201) {
      throw ApiException(
        mensajeDeError(respuesta, 'No se pudo enviar la denuncia. Intentá de nuevo.'),
        codigo: respuesta.statusCode,
      );
    }
    final cuerpo = decodificar(respuesta) as Map<String, dynamic>;
    return cuerpo['mensaje'] as String? ?? 'Gracias por avisar. La universidad va a revisar esta oferta.';
  }
}
