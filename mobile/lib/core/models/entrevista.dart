/// Entrevista propuesta por la empresa para una postulación (HU-20).
/// Espejo de EntrevistaOut (backend/app/features/entrevistas/schema.py).
class Entrevista {
  final String id;
  final String postulacionId;

  /// En hora local del teléfono (el backend la envía en UTC).
  final DateTime inicio;
  final DateTime? fin;

  /// "onsite" o "virtual".
  final String modalidad;
  final String? lugar;
  final String? enlace;

  /// Indicaciones que dejó la empresa.
  final String? indicaciones;

  /// pending_confirmation, confirmed, rejected, cancelled o completed.
  final String estado;

  /// Motivo que dio el egresado al rechazarla.
  final String? motivoRechazo;
  final int rechazos;
  final bool requiereRevision;
  final String? empresaNombre;
  final String? vacanteTitulo;
  final DateTime creada;

  const Entrevista({
    required this.id,
    required this.postulacionId,
    required this.inicio,
    required this.fin,
    required this.modalidad,
    required this.lugar,
    required this.enlace,
    required this.indicaciones,
    required this.estado,
    required this.motivoRechazo,
    required this.rechazos,
    required this.requiereRevision,
    required this.empresaNombre,
    required this.vacanteTitulo,
    required this.creada,
  });

  /// null si el JSON no tiene la forma esperada (por ejemplo, sin fecha de inicio).
  static Entrevista? tryFromJson(Object? json) {
    if (json is! Map<String, dynamic>) return null;
    try {
      return Entrevista.fromJson(json);
    } on Object {
      return null;
    }
  }

  factory Entrevista.fromJson(Map<String, dynamic> json) {
    DateTime? fecha(String clave) {
      final valor = json[clave] as String?;
      return valor == null ? null : DateTime.parse(valor).toLocal();
    }

    final inicio = fecha('scheduled_start');
    if (inicio == null) throw const FormatException('La entrevista no tiene fecha de inicio.');

    return Entrevista(
      id: json['id'] as String,
      postulacionId: json['application_id'] as String,
      inicio: inicio,
      fin: fecha('scheduled_end'),
      modalidad: json['modality'] as String? ?? 'virtual',
      lugar: _texto(json['location']),
      enlace: _texto(json['meeting_url']),
      indicaciones: _texto(json['notes']),
      estado: json['status'] as String? ?? 'pending_confirmation',
      motivoRechazo: _texto(json['candidate_feedback']),
      rechazos: json['rejection_count'] as int? ?? 0,
      requiereRevision: json['requires_manual_review'] as bool? ?? false,
      empresaNombre: _texto(json['empresa_nombre']),
      vacanteTitulo: _texto(json['vacante_titulo']),
      creada: fecha('created_at') ?? DateTime.now(),
    );
  }

  bool get esVirtual => modalidad == 'virtual';
  bool get pendiente => estado == 'pending_confirmation';
  bool get confirmada => estado == 'confirmed';
  bool get yaPaso => (fin ?? inicio).isBefore(DateTime.now());

  /// Pendiente de respuesta y todavía a tiempo de responder.
  bool get requiereRespuesta => pendiente && !yaPaso;

  static String? _texto(Object? valor) {
    final texto = valor as String?;
    return texto == null || texto.trim().isEmpty ? null : texto.trim();
  }
}
