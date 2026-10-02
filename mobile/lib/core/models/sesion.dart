/// Respuesta de POST /auth/login (ver backend/app/features/auth/schema.py::TokenResponse).
class Sesion {
  final String accessToken;
  final String refreshToken;
  final String rol;
  final List<String> roles;

  /// Universidad del usuario (el SaaS es multi-universidad); null para el superadmin.
  final String? institucionNombre;

  const Sesion({
    required this.accessToken,
    required this.refreshToken,
    required this.rol,
    required this.roles,
    this.institucionNombre,
  });

  factory Sesion.fromJson(Map<String, dynamic> json) {
    return Sesion(
      accessToken: json['access_token'] as String,
      refreshToken: json['refresh_token'] as String,
      rol: json['rol'] as String,
      roles: (json['roles'] as List<dynamic>? ?? []).map((e) => e.toString()).toList(),
      institucionNombre: json['institucion_nombre'] as String?,
    );
  }
}
