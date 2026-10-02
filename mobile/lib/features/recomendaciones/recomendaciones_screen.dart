import 'package:flutter/material.dart';

import '../../core/models/recomendacion.dart';
import '../../core/services/recomendacion_service.dart';
import '../perfil/mi_cv_screen.dart';
import '../vacantes/postulacion_screen.dart';
import '../vacantes/vacante_detalle_screen.dart';
import '../vacantes/vacantes_screen.dart';

/// HU-23 — Vacantes recomendadas (versión móvil). Consume GET /ia/recomendaciones,
/// el mismo motor de afinidad que la web: carrera, habilidades, experiencia e
/// idiomas, con el detalle de por qué cada vacante tiene ese porcentaje.
class RecomendacionesScreen extends StatefulWidget {
  final String accessToken;

  const RecomendacionesScreen({super.key, required this.accessToken});

  @override
  State<RecomendacionesScreen> createState() => _RecomendacionesScreenState();
}

class _RecomendacionesScreenState extends State<RecomendacionesScreen> {
  final _servicio = RecomendacionService();

  late Future<Recomendaciones> _futuro;
  int _minimo = 0;
  final Set<String> _abiertas = {};

  static const _filtros = {0: 'Todas', 50: '50% o más', 75: '75% o más'};

  @override
  void initState() {
    super.initState();
    _futuro = _servicio.obtener(widget.accessToken);
  }

  void _recargar() {
    setState(() {
      _abiertas.clear();
      _futuro = _servicio.obtener(widget.accessToken);
    });
  }

  Future<void> _postularme(VacanteRecomendada r) async {
    final postulado = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => PostulacionScreen(accessToken: widget.accessToken, vacante: r.vacante)),
    );
    // Las vacantes a las que ya se postuló salen de las recomendaciones.
    if (postulado == true && mounted) _recargar();
  }

  Future<void> _completarCv() async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => MiCvScreen(accessToken: widget.accessToken)),
    );
    if (mounted) _recargar();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Vacantes recomendadas'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), tooltip: 'Recalcular', onPressed: _recargar),
        ],
      ),
      body: FutureBuilder<Recomendaciones>(
        future: _futuro,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CircularProgressIndicator(),
                  SizedBox(height: 16),
                  Text('Calculando tu afinidad con las vacantes vigentes…'),
                ],
              ),
            );
          }
          if (snapshot.hasError) {
            return _estadoError(snapshot.error);
          }
          return RefreshIndicator(
            onRefresh: () async => _recargar(),
            child: _listado(snapshot.data!),
          );
        },
      ),
    );
  }

  Widget _estadoError(Object? error) {
    final noDisponible = error is RecomendacionException && error.noDisponible;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              noDisponible ? Icons.smart_toy_outlined : Icons.error_outline,
              color: noDisponible ? Colors.orange.shade400 : Colors.red.shade400,
              size: 48,
            ),
            const SizedBox(height: 12),
            if (noDisponible)
              Text(
                'Recomendaciones no disponibles',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
              ),
            const SizedBox(height: 8),
            Text('$error', textAlign: TextAlign.center),
            const SizedBox(height: 16),
            Wrap(
              spacing: 12,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: [
                if (noDisponible)
                  FilledButton(
                    onPressed: () => Navigator.of(context).pushReplacement(
                      MaterialPageRoute(builder: (_) => VacantesScreen(accessToken: widget.accessToken)),
                    ),
                    child: const Text('Buscar vacantes'),
                  ),
                OutlinedButton(onPressed: _recargar, child: const Text('Reintentar')),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _listado(Recomendaciones datos) {
    final filtradas = datos.items.where((r) => r.afinidad >= _minimo).toList();
    final hora = '${datos.calculadoEn.hour.toString().padLeft(2, '0')}:'
        '${datos.calculadoEn.minute.toString().padLeft(2, '0')}';

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.deepPurple.shade50,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: Colors.deepPurple.shade100),
          ),
          child: Text(
            '🔒 La afinidad compara tu carrera, habilidades, experiencia e idiomas con cada vacante vigente. '
            'Nunca usa tu edad, género, foto ni otros datos personales.',
            style: TextStyle(color: Colors.deepPurple.shade800, fontSize: 13),
          ),
        ),
        if (datos.perfilFaltantes.isNotEmpty) ...[
          const SizedBox(height: 12),
          _mejorarPerfil(datos.perfilFaltantes),
        ],
        const SizedBox(height: 16),
        Text(
          '${filtradas.length} ${filtradas.length == 1 ? 'vacante' : 'vacantes'} · calculado a las $hora con tu perfil actual',
          style: TextStyle(color: Colors.grey[700], fontSize: 13),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: _filtros.entries
              .map((f) => ChoiceChip(
                    label: Text(f.value),
                    selected: _minimo == f.key,
                    onSelected: (_) => setState(() => _minimo = f.key),
                  ))
              .toList(),
        ),
        const SizedBox(height: 12),
        if (filtradas.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 32),
            child: Text(
              datos.total == 0
                  ? 'No hay vacantes vigentes para recomendarte ahora (no se incluyen las que ya te postulaste).'
                  : 'Ninguna vacante llega a esa afinidad. Probá con "Todas".',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey[600]),
            ),
          ),
        for (final r in filtradas) ...[
          _tarjeta(r),
          const SizedBox(height: 12),
        ],
      ],
    );
  }

  Widget _mejorarPerfil(List<String> faltantes) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.amber.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.amber.shade200),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Mejorá tus recomendaciones', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          for (final f in faltantes) Text('• $f', style: const TextStyle(fontSize: 13)),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton.tonal(onPressed: _completarCv, child: const Text('Completar mi CV')),
          ),
        ],
      ),
    );
  }

  Widget _tarjeta(VacanteRecomendada r) {
    final abierta = _abiertas.contains(r.vacante.id);
    final datosVacante = [r.vacante.city, r.vacante.modalidadLegible, r.vacante.nivelLegible]
        .where((x) => x.isNotEmpty)
        .join(' · ');

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            InkWell(
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => VacanteDetalleScreen(accessToken: widget.accessToken, vacante: r.vacante),
                ),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _insigniaAfinidad(r.afinidad),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(r.vacante.title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                        const SizedBox(height: 2),
                        Text(r.vacante.companyName, style: TextStyle(color: Colors.grey[800], fontWeight: FontWeight.w600)),
                        if (datosVacante.isNotEmpty)
                          Text(datosVacante, style: TextStyle(color: Colors.grey[600], fontSize: 13)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: r.criterios.isEmpty
                  ? [_chipEstado('La vacante no detalla requisitos comparables', null)]
                  : r.criterios.map((c) => _chipEstado('${_icono(c.estado)} ${c.nombre}', c.estado)).toList(),
            ),
            if (abierta) ...[
              const SizedBox(height: 12),
              const Divider(height: 1),
              const SizedBox(height: 12),
              if (r.criterios.isEmpty)
                Text(
                  'La vacante no especifica carrera, habilidades, experiencia ni idiomas, así que la afinidad es neutral (50%).',
                  style: TextStyle(color: Colors.grey[700], fontSize: 13),
                ),
              for (final c in r.criterios) _detalleCriterio(c),
            ],
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => setState(() => abierta ? _abiertas.remove(r.vacante.id) : _abiertas.add(r.vacante.id)),
                    child: Text(abierta ? 'Ocultar detalle' : '¿Por qué ${r.afinidad}%?'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton(
                    onPressed: r.yaPostulado ? null : () => _postularme(r),
                    child: Text(r.yaPostulado ? 'Ya postulado' : 'Postularme'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _insigniaAfinidad(int afinidad) {
    final (fondo, texto) = afinidad >= 75
        ? (Colors.green.shade50, Colors.green.shade800)
        : afinidad >= 50
            ? (Colors.amber.shade50, Colors.orange.shade800)
            : (Colors.blueGrey.shade50, Colors.blueGrey.shade700);
    return Container(
      width: 72,
      padding: const EdgeInsets.symmetric(vertical: 10),
      decoration: BoxDecoration(color: fondo, borderRadius: BorderRadius.circular(10)),
      child: Column(
        children: [
          Text('$afinidad%', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: texto)),
          Text('afinidad', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: texto)),
        ],
      ),
    );
  }

  Widget _detalleCriterio(CriterioAfinidad c) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text('${_icono(c.estado)} ${c.nombre}', style: const TextStyle(fontWeight: FontWeight.w600)),
              ),
              Text('${c.cumplimiento}% · pesa ${c.peso}%', style: TextStyle(color: Colors.grey[600], fontSize: 12)),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: c.cumplimiento / 100,
              minHeight: 6,
              backgroundColor: Colors.grey.shade200,
              color: _colores(c.estado).$2,
            ),
          ),
          const SizedBox(height: 6),
          Text(c.detalle, style: TextStyle(color: Colors.grey[700], fontSize: 13)),
          if (c.coincidencias.isNotEmpty || c.faltantes.isNotEmpty) ...[
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final x in c.coincidencias) _chipEstado('✓ $x', 'cumple'),
                for (final x in c.faltantes) _chipEstado('✗ $x', 'no_cumple'),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _chipEstado(String texto, String? estado) {
    final (fondo, color) = _colores(estado);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(color: fondo, borderRadius: BorderRadius.circular(999)),
      child: Text(texto, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
    );
  }

  (Color, Color) _colores(String? estado) {
    switch (estado) {
      case 'cumple':
        return (Colors.green.shade50, Colors.green.shade700);
      case 'parcial':
        return (Colors.amber.shade50, Colors.orange.shade800);
      case 'no_cumple':
        return (Colors.red.shade50, Colors.red.shade700);
      default:
        return (Colors.grey.shade100, Colors.grey.shade700);
    }
  }

  String _icono(String estado) {
    switch (estado) {
      case 'cumple':
        return '✓';
      case 'parcial':
        return '◐';
      default:
        return '✗';
    }
  }
}
