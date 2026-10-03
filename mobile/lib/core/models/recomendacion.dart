import 'vacante.dart';

/// Respuesta de GET /ia/recomendaciones (ver backend/app/features/ia/schema.py).
class Recomendaciones {
  final DateTime calculadoEn;
  final int total;

  /// Secciones vacías del perfil que bajan la afinidad.
  final List<String> perfilFaltantes;
  final List<VacanteRecomendada> items;

  const Recomendaciones({
    required this.calculadoEn,
    required this.total,
    required this.perfilFaltantes,
    required this.items,
  });

  factory Recomendaciones.fromJson(Map<String, dynamic> json) {
    return Recomendaciones(
      calculadoEn: DateTime.parse(json['calculado_en'] as String).toLocal(),
      total: json['total'] as int? ?? 0,
      perfilFaltantes: (json['perfil_faltantes'] as List<dynamic>? ?? []).map((e) => e.toString()).toList(),
      items: (json['items'] as List<dynamic>? ?? [])
          .map((e) => VacanteRecomendada.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

class VacanteRecomendada {
  final Vacante vacante;
  final int afinidad;

  /// Vacío cuando la vacante no detalla requisitos comparables (afinidad neutral).
  final List<CriterioAfinidad> criterios;
  final bool yaPostulado;

  const VacanteRecomendada({
    required this.vacante,
    required this.afinidad,
    required this.criterios,
    required this.yaPostulado,
  });

  factory VacanteRecomendada.fromJson(Map<String, dynamic> json) {
    return VacanteRecomendada(
      vacante: Vacante.fromJson(json['vacante'] as Map<String, dynamic>),
      afinidad: json['afinidad'] as int? ?? 0,
      criterios: (json['criterios'] as List<dynamic>? ?? [])
          .map((e) => CriterioAfinidad.fromJson(e as Map<String, dynamic>))
          .toList(),
      yaPostulado: json['ya_postulado'] as bool? ?? false,
    );
  }
}

/// Un criterio de la HU-23 (carrera, habilidades, experiencia o idiomas) y cuánto lo cumple el egresado.
class CriterioAfinidad {
  final String clave;
  final String nombre;
  final int peso;
  final int cumplimiento;

  /// cumple | parcial | no_cumple
  final String estado;
  final String detalle;
  final List<String> coincidencias;
  final List<String> faltantes;

  const CriterioAfinidad({
    required this.clave,
    required this.nombre,
    required this.peso,
    required this.cumplimiento,
    required this.estado,
    required this.detalle,
    required this.coincidencias,
    required this.faltantes,
  });

  factory CriterioAfinidad.fromJson(Map<String, dynamic> json) {
    return CriterioAfinidad(
      clave: json['clave'] as String? ?? '',
      nombre: json['nombre'] as String? ?? '',
      peso: json['peso'] as int? ?? 0,
      cumplimiento: json['cumplimiento'] as int? ?? 0,
      estado: json['estado'] as String? ?? 'no_cumple',
      detalle: json['detalle'] as String? ?? '',
      coincidencias: (json['coincidencias'] as List<dynamic>? ?? []).map((e) => e.toString()).toList(),
      faltantes: (json['faltantes'] as List<dynamic>? ?? []).map((e) => e.toString()).toList(),
    );
  }
}
