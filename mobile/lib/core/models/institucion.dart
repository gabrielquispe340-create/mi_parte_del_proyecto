/// Universidad cliente de la plataforma (ver backend/app/features/catalogo/schema.py::InstitucionResponse).
class Institucion {
  final String id;
  final String nombre;
  final String? sigla;
  final String? ciudad;

  const Institucion({required this.id, required this.nombre, this.sigla, this.ciudad});

  String get etiqueta => sigla != null ? '$nombre ($sigla)' : nombre;

  factory Institucion.fromJson(Map<String, dynamic> json) {
    return Institucion(
      id: json['id'] as String,
      nombre: json['nombre'] as String,
      sigla: json['sigla'] as String?,
      ciudad: json['ciudad'] as String?,
    );
  }
}
