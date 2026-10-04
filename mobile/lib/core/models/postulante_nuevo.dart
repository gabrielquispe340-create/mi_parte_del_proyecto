/// Postulante que la empresa todavía no revisó. Espejo de PostulanteNuevoItem
/// (backend/app/features/seleccion/schema.py), para la app de empresas.
class PostulanteNuevo {
  final String postulacionId;
  final String nombre;
  final String? titular;
  final String? carrera;
  final String? correo;
  final String? telefono;
  final String? ciudad;
  final String? universidad;

  /// Afinidad con la vacante (HU-23); null si el motor de IA está apagado.
  final int? afinidad;
  final String vacanteTitulo;

  /// En hora local del teléfono.
  final DateTime fecha;

  const PostulanteNuevo({
    required this.postulacionId,
    required this.nombre,
    required this.titular,
    required this.carrera,
    required this.correo,
    required this.telefono,
    required this.ciudad,
    required this.universidad,
    required this.afinidad,
    required this.vacanteTitulo,
    required this.fecha,
  });

  factory PostulanteNuevo.fromJson(Map<String, dynamic> json) => PostulanteNuevo(
    postulacionId: json['postulacion_id'] as String,
    nombre: json['candidato_nombre'] as String? ?? 'Candidato',
    titular: _texto(json['candidato_titular']),
    carrera: _texto(json['candidato_carrera']),
    correo: _texto(json['candidato_email']),
    telefono: _texto(json['candidato_telefono']),
    ciudad: _texto(json['candidato_ciudad']),
    universidad: _texto(json['candidato_universidad']),
    afinidad: json['candidato_afinidad'] as int?,
    vacanteTitulo: json['vacante_titulo'] as String? ?? 'Vacante',
    fecha: DateTime.parse(json['fecha_postulacion'] as String).toLocal(),
  );

  static String? _texto(Object? valor) {
    final texto = valor as String?;
    return texto == null || texto.trim().isEmpty ? null : texto.trim();
  }
}

/// GET /seleccion/postulantes-nuevos: los más recientes primero.
class PostulantesNuevos {
  final String empresaNombre;

  /// Total sin revisar; la lista puede traer menos (el backend la limita).
  final int total;
  final List<PostulanteNuevo> postulantes;

  const PostulantesNuevos({required this.empresaNombre, required this.total, required this.postulantes});

  factory PostulantesNuevos.fromJson(Map<String, dynamic> json) => PostulantesNuevos(
    empresaNombre: json['empresa_nombre'] as String? ?? 'Tu empresa',
    total: json['total'] as int? ?? 0,
    postulantes: (json['postulantes'] as List<dynamic>? ?? [])
        .map((p) => PostulanteNuevo.fromJson(p as Map<String, dynamic>))
        .toList(),
  );
}
