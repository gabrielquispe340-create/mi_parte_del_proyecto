/// Estadísticas públicas de la plataforma (HU-34), GET /vacantes/estadisticas-publicas.
/// El backend las recalcula una vez por día; [corte] es el momento del cálculo.
class EstadisticasPublicas {
  final int vacantesActivas;
  final int empresasVerificadas;
  final DateTime corte;

  const EstadisticasPublicas({
    required this.vacantesActivas,
    required this.empresasVerificadas,
    required this.corte,
  });

  factory EstadisticasPublicas.fromJson(Map<String, dynamic> json) {
    return EstadisticasPublicas(
      vacantesActivas: json['total_vacantes_activas'] as int? ?? 0,
      empresasVerificadas: json['total_empresas_registradas'] as int? ?? 0,
      corte: DateTime.parse(json['fecha_actualizacion'] as String).toLocal(),
    );
  }
}
