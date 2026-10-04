import 'dart:io';
import 'dart:typed_data';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:path_provider/path_provider.dart';

import '../models/mensaje.dart';
import 'api_config.dart';
import 'api_http.dart';

/// Tope del backend para los adjuntos (HU-19).
const tamanoMaximoAdjunto = 5 * 1024 * 1024;

/// Archivo elegido en el teléfono, listo para subir.
class ArchivoParaEnviar {
  final String nombre;
  final Uint8List bytes;
  const ArchivoParaEnviar(this.nombre, this.bytes);
}

/// Mensajería de una postulación (HU-19): las mismas rutas que usa la web
/// (backend/app/features/comunicacion/router.py), para egresados y empresas.
class MensajeService {
  /// GET /comunicacion/postulaciones/{id}/mensajes. El backend marca el hilo como leído.
  Future<HiloMensajes> hilo(String accessToken, String postulacionId) async {
    final respuesta = await obtener(
      Uri.parse('${ApiConfig.baseUrl}/comunicacion/postulaciones/$postulacionId/mensajes'),
      accessToken: accessToken,
    );
    if (respuesta.statusCode != 200) {
      throw ApiException(mensajeDeError(respuesta, 'No se pudieron cargar los mensajes.'), codigo: respuesta.statusCode);
    }
    return HiloMensajes.fromJson(decodificar(respuesta) as Map<String, dynamic>);
  }

  /// GET /comunicacion/conversaciones: hilos del usuario, del más reciente al más viejo.
  Future<List<ResumenConversacion>> conversaciones(String accessToken) async {
    final respuesta = await obtener(
      Uri.parse('${ApiConfig.baseUrl}/comunicacion/conversaciones'),
      accessToken: accessToken,
    );
    if (respuesta.statusCode != 200) {
      throw ApiException(mensajeDeError(respuesta, 'No se pudieron cargar tus mensajes.'), codigo: respuesta.statusCode);
    }
    return (decodificar(respuesta) as List<dynamic>)
        .map((c) => ResumenConversacion.fromJson(c as Map<String, dynamic>))
        .toList();
  }

  /// POST multipart /comunicacion/postulaciones/{id}/mensajes con texto, archivo o ambos.
  Future<Mensaje> enviar(String accessToken, String postulacionId, {String texto = '', ArchivoParaEnviar? archivo}) async {
    final pedido = http.MultipartRequest(
      'POST',
      Uri.parse('${ApiConfig.baseUrl}/comunicacion/postulaciones/$postulacionId/mensajes'),
    )..headers.addAll(encabezados(accessToken));
    if (texto.trim().isNotEmpty) pedido.fields['contenido'] = texto.trim();
    if (archivo != null) {
      pedido.files.add(
        http.MultipartFile.fromBytes('archivo', archivo.bytes, filename: archivo.nombre, contentType: _tipoDe(archivo.nombre)),
      );
    }

    late final http.Response respuesta;
    try {
      // Un adjunto de 5 MB puede tardar con datos móviles: más margen que el resto.
      respuesta = await http.Response.fromStream(await pedido.send().timeout(const Duration(seconds: 60)));
    } catch (_) {
      throw const ApiException(mensajeSinConexion);
    }
    if (respuesta.statusCode != 201) {
      throw ApiException(mensajeDeError(respuesta, 'No se pudo enviar el mensaje.'), codigo: respuesta.statusCode);
    }
    return Mensaje.fromJson(decodificar(respuesta) as Map<String, dynamic>);
  }

  /// GET /comunicacion/adjuntos/{id}: lo guarda en la caché de la app y devuelve el archivo.
  /// La descarga pide la sesión, por eso no alcanza con abrir un enlace en el navegador.
  Future<File> descargarAdjunto(String accessToken, Adjunto adjunto) async {
    final respuesta = await obtener(
      Uri.parse('${ApiConfig.baseUrl}/comunicacion/adjuntos/${adjunto.id}'),
      accessToken: accessToken,
    );
    if (respuesta.statusCode != 200) {
      throw ApiException(mensajeDeError(respuesta, 'No se pudo descargar el archivo.'), codigo: respuesta.statusCode);
    }
    // Una carpeta por adjunto: dos archivos con el mismo nombre no se pisan.
    final carpeta = Directory('${(await getTemporaryDirectory()).path}/adjuntos/${adjunto.id}');
    await carpeta.create(recursive: true);
    final nombre = adjunto.nombre.replaceAll(RegExp(r'[\\/:*?"<>|]'), '_');
    return File('${carpeta.path}/$nombre').writeAsBytes(respuesta.bodyBytes, flush: true);
  }

  /// Sin esto el backend guarda todo como application/octet-stream y la web
  /// no sabe con qué abrirlo.
  static MediaType _tipoDe(String nombre) {
    final extension = nombre.contains('.') ? nombre.split('.').last.toLowerCase() : '';
    return MediaType.parse(switch (extension) {
      'pdf' => 'application/pdf',
      'png' => 'image/png',
      'jpg' || 'jpeg' => 'image/jpeg',
      'webp' => 'image/webp',
      'txt' => 'text/plain',
      'doc' => 'application/msword',
      'docx' => 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'xls' => 'application/vnd.ms-excel',
      'xlsx' => 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'ppt' => 'application/vnd.ms-powerpoint',
      'pptx' => 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      'zip' => 'application/zip',
      _ => 'application/octet-stream',
    });
  }
}
