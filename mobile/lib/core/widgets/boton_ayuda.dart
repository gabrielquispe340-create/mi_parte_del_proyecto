import 'package:flutter/material.dart';

import '../../features/ayuda/ayuda_contenido.dart';
import '../../features/ayuda/ayuda_screen.dart';
import '../theme/app_theme.dart';

/// Botón «?» de la barra superior: abre la ayuda de la pantalla actual (requisito 4).
class BotonAyuda extends StatelessWidget {
  final String tema;
  final bool esEmpresa;
  final Color? color;

  const BotonAyuda(this.tema, {super.key, this.esEmpresa = false, this.color});

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: 'Ayuda',
      icon: Icon(Icons.help_outline_rounded, color: color),
      onPressed: () => mostrarAyuda(context, temaAyuda(tema), esEmpresa: esEmpresa),
    );
  }
}

Future<void> mostrarAyuda(BuildContext context, TemaAyuda tema, {required bool esEmpresa}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (hoja) => DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.6,
      maxChildSize: 0.92,
      builder: (_, scroll) => ListView(
        controller: scroll,
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'AYUDA EN LÍNEA',
                  style: TextStyle(color: AppColors.primario, fontSize: 12, fontWeight: FontWeight.w800, letterSpacing: 1),
                ),
              ),
              TextButton.icon(
                icon: const Icon(Icons.menu_book_outlined, size: 18),
                label: const Text('Ver toda la ayuda'),
                onPressed: () {
                  Navigator.of(hoja).pop();
                  Navigator.of(context).push(MaterialPageRoute(builder: (_) => AyudaScreen(esEmpresa: esEmpresa)));
                },
              ),
            ],
          ),
          const SizedBox(height: 2),
          ContenidoTemaAyuda(tema),
        ],
      ),
    ),
  );
}

/// Título, resumen, pasos y preguntas frecuentes de un tema.
class ContenidoTemaAyuda extends StatelessWidget {
  final TemaAyuda tema;
  final bool conTitulo;
  const ContenidoTemaAyuda(this.tema, {super.key, this.conTitulo = true});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (conTitulo) ...[
          Text(tema.titulo, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 6),
        ],
        Text(tema.resumen, style: const TextStyle(color: AppColors.textoSuave, height: 1.4)),
        if (tema.pasos.isNotEmpty) ...[
          const SizedBox(height: 14),
          for (var i = 0; i < tema.pasos.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CircleAvatar(
                    radius: 11,
                    backgroundColor: AppColors.primario,
                    child: Text('${i + 1}', style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700)),
                  ),
                  const SizedBox(width: 10),
                  Expanded(child: Text(tema.pasos[i], style: const TextStyle(height: 1.35))),
                ],
              ),
            ),
        ],
        if (tema.preguntas.isNotEmpty) ...[
          const SizedBox(height: 8),
          const Text('Preguntas frecuentes', style: TextStyle(fontWeight: FontWeight.w700)),
          for (final p in tema.preguntas)
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              childrenPadding: const EdgeInsets.only(bottom: 10),
              expandedAlignment: Alignment.centerLeft,
              title: Text(p.pregunta, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
              children: [Text(p.respuesta, style: const TextStyle(color: AppColors.textoSuave, height: 1.4))],
            ),
        ],
      ],
    );
  }
}
