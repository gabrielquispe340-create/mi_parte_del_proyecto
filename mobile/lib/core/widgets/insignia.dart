import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../utils/formatos.dart';

/// Par de colores (texto, fondo) de una insignia.
typedef ColoresInsignia = ({Color color, Color fondo});

/// El backend etiqueta cada estado de postulación con un nombre de color
/// ("blue", "emerald"...); acá se traduce a la paleta de la app.
ColoresInsignia coloresDeEstado(String nombre) => switch (nombre) {
  'blue' || 'indigo' => (color: AppColors.primario, fondo: AppColors.primarioSuave),
  'cyan' => (color: AppColors.info, fondo: AppColors.infoSuave),
  'yellow' => (color: AppColors.alerta, fondo: AppColors.alertaSuave),
  'purple' => (color: AppColors.violeta, fondo: AppColors.violetaSuave),
  'emerald' || 'green' => (color: AppColors.exito, fondo: AppColors.exitoSuave),
  'red' => (color: AppColors.peligro, fondo: AppColors.peligroSuave),
  _ => (color: AppColors.textoSuave, fondo: const Color(0xFFF1F5F9)),
};

/// Afinidad: verde desde 75%, azul desde 50%, gris por debajo.
ColoresInsignia coloresDeAfinidad(int porcentaje) => porcentaje >= 75
    ? (color: AppColors.exito, fondo: AppColors.exitoSuave)
    : porcentaje >= 50
    ? (color: AppColors.primario, fondo: AppColors.primarioSuave)
    : (color: AppColors.textoSuave, fondo: const Color(0xFFF1F5F9));

/// Etiqueta compacta en forma de píldora.
class Insignia extends StatelessWidget {
  final String texto;
  final ColoresInsignia colores;
  final IconData? icono;

  const Insignia(this.texto, {super.key, required this.colores, this.icono});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: colores.fondo, borderRadius: BorderRadius.circular(999)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icono != null) ...[Icon(icono, size: 14, color: colores.color), const SizedBox(width: 4)],
          Flexible(
            child: Text(
              texto,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: colores.color, fontSize: 12, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}

/// Dato con ícono, para filas de metadatos ("Santa Cruz", "Remoto"...).
/// Ícono para la modalidad de trabajo de una vacante (`work_modality`).
IconData iconoDeModalidad(String codigo) => switch (codigo) {
  'remote' => Icons.home_work_outlined,
  'hybrid' => Icons.sync_alt_rounded,
  _ => Icons.apartment_rounded,
};

class DatoConIcono extends StatelessWidget {
  final IconData icono;
  final String texto;
  const DatoConIcono(this.icono, this.texto, {super.key});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icono, size: 15, color: AppColors.textoTenue),
        const SizedBox(width: 4),
        Flexible(
          child: Text(
            texto,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: AppColors.textoSuave, fontSize: 13),
          ),
        ),
      ],
    );
  }
}

/// Avatar cuadrado con la inicial de la empresa.
class AvatarEmpresa extends StatelessWidget {
  final String nombre;
  final double tamano;
  const AvatarEmpresa(this.nombre, {super.key, this.tamano = 44});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: tamano,
      height: tamano,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: AppColors.primarioSuave,
        borderRadius: BorderRadius.circular(tamano * 0.28),
        border: Border.all(color: AppColors.primarioBorde),
      ),
      child: Text(
        nombre.isEmpty ? '?' : nombre[0].toUpperCase(),
        style: TextStyle(color: AppColors.primario, fontWeight: FontWeight.w700, fontSize: tamano * 0.4),
      ),
    );
  }
}

/// Avatar redondo con las iniciales de una persona (los postulantes, en la app de empresas).
class AvatarPersona extends StatelessWidget {
  final String nombre;
  final double tamano;
  const AvatarPersona(this.nombre, {super.key, this.tamano = 44});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: tamano,
      height: tamano,
      alignment: Alignment.center,
      decoration: const BoxDecoration(color: AppColors.violetaSuave, shape: BoxShape.circle),
      child: Text(
        iniciales(nombre),
        style: TextStyle(color: AppColors.violeta, fontWeight: FontWeight.w700, fontSize: tamano * 0.36),
      ),
    );
  }
}

/// Burbuja con la cantidad de mensajes sin leer.
class ContadorNoLeidos extends StatelessWidget {
  final int cantidad;
  const ContadorNoLeidos(this.cantidad, {super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 22),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(color: AppColors.primario, borderRadius: BorderRadius.circular(999)),
      child: Text(
        cantidad > 99 ? '99+' : '$cantidad',
        textAlign: TextAlign.center,
        style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700),
      ),
    );
  }
}

/// Título de sección con una acción opcional a la derecha.
class TituloSeccion extends StatelessWidget {
  final String texto;
  final String? accion;
  final VoidCallback? onAccion;
  const TituloSeccion(this.texto, {super.key, this.accion, this.onAccion});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(child: Text(texto, style: Theme.of(context).textTheme.titleMedium)),
        if (accion != null && onAccion != null)
          TextButton(
            onPressed: onAccion,
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              minimumSize: const Size(0, 36),
              textStyle: const TextStyle(fontFamily: 'Inter', fontWeight: FontWeight.w600, fontSize: 14),
            ),
            child: Text(accion!),
          ),
      ],
    );
  }
}
