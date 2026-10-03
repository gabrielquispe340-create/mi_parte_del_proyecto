/// Formatos de fecha en español, sin depender del paquete intl. Todas las
/// funciones esperan fechas ya convertidas a la hora local del teléfono.
library;

const _meses = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
];
const _mesesCortos = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const _dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];

String _dosDigitos(int n) => n.toString().padLeft(2, '0');

/// "3 oct. 2026"
String fechaCorta(DateTime f) => '${f.day} ${_mesesCortos[f.month - 1]}. ${f.year}';

/// "jueves 5 de octubre"
String fechaLarga(DateTime f) => '${_dias[f.weekday - 1]} ${f.day} de ${_meses[f.month - 1]}';

/// "14:00"
String hora(DateTime f) => '${_dosDigitos(f.hour)}:${_dosDigitos(f.minute)}';

/// "OCT", para el bloque de calendario de las entrevistas.
String mesAbreviado(DateTime f) => _mesesCortos[f.month - 1].toUpperCase();

/// "14:00 – 15:00", o solo el inicio si no hay hora de fin.
String rangoHorario(DateTime inicio, DateTime? fin) => fin == null ? hora(inicio) : '${hora(inicio)} – ${hora(fin)}';

/// "hoy", "ayer", "hace 3 días", "hace 2 semanas" o la fecha corta si pasó más de un mes.
String haceCuanto(DateTime f, {DateTime? ahora}) {
  final hoy = _soloFecha(ahora ?? DateTime.now());
  final dias = hoy.difference(_soloFecha(f)).inDays;
  if (dias <= 0) return 'hoy';
  if (dias == 1) return 'ayer';
  if (dias < 7) return 'hace $dias días';
  if (dias < 30) {
    final semanas = dias ~/ 7;
    return semanas == 1 ? 'hace 1 semana' : 'hace $semanas semanas';
  }
  return 'el ${fechaCorta(f)}';
}

/// "Hoy", "Mañana", "En 3 días" o la fecha larga, para eventos futuros.
String cuandoSera(DateTime f, {DateTime? ahora}) {
  final dias = _soloFecha(f).difference(_soloFecha(ahora ?? DateTime.now())).inDays;
  if (dias == 0) return 'Hoy';
  if (dias == 1) return 'Mañana';
  if (dias > 1 && dias < 7) return 'En $dias días';
  return capitalizar(fechaLarga(f));
}

String capitalizar(String texto) => texto.isEmpty ? texto : texto[0].toUpperCase() + texto.substring(1);

/// Iniciales para los avatares: "Antonio Bravo" -> "AB".
String iniciales(String nombre) {
  final partes = nombre.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
  if (partes.isEmpty) return '?';
  if (partes.length == 1) return partes.first[0].toUpperCase();
  return (partes.first[0] + partes[1][0]).toUpperCase();
}

DateTime _soloFecha(DateTime f) => DateTime(f.year, f.month, f.day);
