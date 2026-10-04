/// Mensajería interna entre la empresa y el egresado de una postulación
/// (HU-19). Espejo de backend/app/features/comunicacion/schema.py.
library;

class Adjunto {
  final String id;
  final String nombre;
  final String? tipo;
  final int? tamano;

  const Adjunto({required this.id, required this.nombre, required this.tipo, required this.tamano});

  factory Adjunto.fromJson(Map<String, dynamic> json) => Adjunto(
    id: json['id'] as String,
    nombre: json['original_filename'] as String? ?? 'adjunto',
    tipo: json['mime_type'] as String?,
    tamano: json['file_size'] as int?,
  );
}

class Mensaje {
  final String id;
  final String contenido;
  final bool esMio;

  /// "empresa" o "candidato".
  final String remitenteRol;
  final String remitenteNombre;

  /// En hora local del teléfono.
  final DateTime fecha;
  final Adjunto? adjunto;

  const Mensaje({
    required this.id,
    required this.contenido,
    required this.esMio,
    required this.remitenteRol,
    required this.remitenteNombre,
    required this.fecha,
    required this.adjunto,
  });

  factory Mensaje.fromJson(Map<String, dynamic> json) {
    final adjunto = json['adjunto'];
    return Mensaje(
      id: json['id'] as String,
      contenido: json['content'] as String? ?? '',
      esMio: json['es_mio'] as bool? ?? false,
      remitenteRol: json['sender_rol'] as String? ?? 'empresa',
      remitenteNombre: json['sender_nombre'] as String? ?? '',
      fecha: DateTime.parse(json['created_at'] as String).toLocal(),
      adjunto: adjunto is Map<String, dynamic> ? Adjunto.fromJson(adjunto) : null,
    );
  }

  /// El backend guarda "Archivo adjunto: cv.pdf" cuando solo se manda un
  /// archivo; en ese caso la burbuja muestra únicamente el archivo.
  bool get soloAdjunto => adjunto != null && contenido == 'Archivo adjunto: ${adjunto!.nombre}';
}

/// Hilo completo de una postulación (GET /comunicacion/postulaciones/{id}/mensajes).
class HiloMensajes {
  final String postulacionId;
  final String vacanteTitulo;
  final String empresaNombre;
  final String candidatoNombre;
  final String? candidatoCarrera;
  final List<Mensaje> mensajes;

  const HiloMensajes({
    required this.postulacionId,
    required this.vacanteTitulo,
    required this.empresaNombre,
    required this.candidatoNombre,
    required this.candidatoCarrera,
    required this.mensajes,
  });

  factory HiloMensajes.fromJson(Map<String, dynamic> json) => HiloMensajes(
    postulacionId: json['application_id'] as String,
    vacanteTitulo: json['vacante_titulo'] as String? ?? 'Vacante',
    empresaNombre: json['empresa_nombre'] as String? ?? 'Empresa',
    candidatoNombre: json['candidato_nombre'] as String? ?? 'Candidato',
    candidatoCarrera: json['candidato_carrera'] as String?,
    mensajes: (json['mensajes'] as List<dynamic>? ?? [])
        .map((m) => Mensaje.fromJson(m as Map<String, dynamic>))
        .toList(),
  );
}

/// Fila de la bandeja de mensajes (GET /comunicacion/conversaciones).
class ResumenConversacion {
  final String postulacionId;
  final String vacanteTitulo;
  final String empresaNombre;
  final String candidatoNombre;
  final String ultimoMensaje;
  final bool ultimoEsMio;
  final DateTime ultimaFecha;
  final int noLeidos;

  const ResumenConversacion({
    required this.postulacionId,
    required this.vacanteTitulo,
    required this.empresaNombre,
    required this.candidatoNombre,
    required this.ultimoMensaje,
    required this.ultimoEsMio,
    required this.ultimaFecha,
    required this.noLeidos,
  });

  factory ResumenConversacion.fromJson(Map<String, dynamic> json) => ResumenConversacion(
    postulacionId: json['application_id'] as String,
    vacanteTitulo: json['vacante_titulo'] as String? ?? 'Vacante',
    empresaNombre: json['empresa_nombre'] as String? ?? 'Empresa',
    candidatoNombre: json['candidato_nombre'] as String? ?? 'Candidato',
    ultimoMensaje: json['ultimo_mensaje'] as String? ?? '',
    ultimoEsMio: json['ultimo_mensaje_es_mio'] as bool? ?? false,
    ultimaFecha: DateTime.parse(json['ultimo_mensaje_at'] as String).toLocal(),
    noLeidos: json['no_leidos'] as int? ?? 0,
  );
}
