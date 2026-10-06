import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../core/widgets/boton_ayuda.dart';
import 'ayuda_contenido.dart';

/// Centro de ayuda de la app: todos los temas, con buscador.
class AyudaScreen extends StatefulWidget {
  final bool esEmpresa;
  const AyudaScreen({super.key, this.esEmpresa = false});

  @override
  State<AyudaScreen> createState() => _AyudaScreenState();
}

class _AyudaScreenState extends State<AyudaScreen> {
  String _consulta = '';

  @override
  Widget build(BuildContext context) {
    final temas = buscarTemasAyuda(_consulta, esEmpresa: widget.esEmpresa);
    return Scaffold(
      appBar: AppBar(title: const Text('Ayuda')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
        children: [
          TextField(
            onChanged: (texto) => setState(() => _consulta = texto),
            textInputAction: TextInputAction.search,
            decoration: const InputDecoration(
              prefixIcon: Icon(Icons.search_rounded),
              hintText: 'Buscá un tema: postularme, entrevista…',
            ),
          ),
          const SizedBox(height: 12),
          if (temas.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 32),
              child: Text(
                'No encontramos temas con esas palabras. Probá con otras.',
                textAlign: TextAlign.center,
                style: TextStyle(color: AppColors.textoSuave),
              ),
            ),
          for (final tema in temas)
            Card(
              margin: const EdgeInsets.only(bottom: 10),
              child: ExpansionTile(
                shape: const Border(),
                title: Text(tema.titulo, style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Text(tema.resumen, maxLines: 2, overflow: TextOverflow.ellipsis),
                childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                expandedAlignment: Alignment.centerLeft,
                children: [ContenidoTemaAyuda(tema, conTitulo: false)],
              ),
            ),
        ],
      ),
    );
  }
}
