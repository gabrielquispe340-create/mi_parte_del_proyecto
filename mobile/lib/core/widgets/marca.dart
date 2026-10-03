import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Logo de EGRESA: el rombo de la web y el nombre.
class MarcaEgresa extends StatelessWidget {
  /// true sobre fondos oscuros (texto y rombo en blanco).
  final bool sobreOscuro;
  final double tamano;

  const MarcaEgresa({super.key, this.sobreOscuro = false, this.tamano = 26});

  @override
  Widget build(BuildContext context) {
    final color = sobreOscuro ? Colors.white : AppColors.primario;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Transform.rotate(
          angle: math.pi / 4,
          child: Container(
            width: tamano * 0.62,
            height: tamano * 0.62,
            decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(tamano * 0.1)),
          ),
        ),
        SizedBox(width: tamano * 0.45),
        Text(
          'EGRESA',
          style: TextStyle(
            color: color,
            fontSize: tamano,
            fontWeight: FontWeight.w700,
            letterSpacing: tamano * 0.04,
            height: 1,
          ),
        ),
      ],
    );
  }
}
