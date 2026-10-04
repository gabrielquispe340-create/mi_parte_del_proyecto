import 'package:flutter/material.dart';

import '../../core/models/entrevista.dart';
import '../../core/services/empresa_service.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/abrir_afuera.dart';
import '../../core/utils/formatos.dart';
import '../../core/widgets/insignia.dart';
import '../../core/widgets/vistas_estado.dart';
import '../mensajes/chat_screen.dart';

/// Días que muestra la agenda, contando hoy.
const _diasDeAgenda = 7;

/// Agenda de entrevistas de la empresa: las de hoy primero y después las de
/// la semana. Proponer, reprogramar o cancelar se hace desde la web.
class AgendaTab extends StatefulWidget {
  final String accessToken;
  final List<Widget> acciones;

  const AgendaTab({super.key, required this.accessToken, required this.acciones});

  @override
  State<AgendaTab> createState() => _AgendaTabState();
}

class _AgendaTabState extends State<AgendaTab> {
  late Future<List<Entrevista>> _futuro = _cargar();

  Future<List<Entrevista>> _cargar() async {
    final ahora = DateTime.now();
    final hoy = DateTime(ahora.year, ahora.month, ahora.day);
    final entrevistas = await EmpresaService().agenda(
      widget.accessToken,
      hoy,
      DateTime(hoy.year, hoy.month, hoy.day + _diasDeAgenda),
    );
    // Las canceladas ya no son parte de la agenda.
    return entrevistas.where((e) => e.estado != 'cancelled').toList();
  }

  Future<void> _recargar() async {
    if (!mounted) return;
    final futuro = _cargar();
    setState(() { _futuro = futuro; });
    await futuro.then((_) {}, onError: (_) {});
  }

  void _escribir(Entrevista e) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ChatScreen(
          accessToken: widget.accessToken,
          postulacionId: e.postulacionId,
          esEmpresa: true,
          titulo: e.candidatoNombre,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Entrevistas'), actions: widget.acciones),
      body: FutureBuilder<List<Entrevista>>(
        future: _futuro,
        builder: (context, snapshot) {
          if (snapshot.hasData) return RefreshIndicator(onRefresh: _recargar, child: _contenido(snapshot.data!));
          if (snapshot.connectionState == ConnectionState.waiting) return const VistaCargando();
          return VistaMensaje.error(snapshot.error, onReintentar: _recargar);
        },
      ),
    );
  }

  Widget _contenido(List<Entrevista> entrevistas) {
    final ahora = DateTime.now();
    final deHoy = entrevistas.where((e) => mismoDia(e.inicio, ahora)).toList();
    final proximas = entrevistas.where((e) => !mismoDia(e.inicio, ahora)).toList();

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
      children: [
        _CabeceraHoy(fecha: ahora, cantidad: deHoy.length),
        const SizedBox(height: 14),
        if (deHoy.isEmpty)
          const Card(
            child: Padding(
              padding: EdgeInsets.all(18),
              child: Row(
                children: [
                  Icon(Icons.free_breakfast_outlined, color: AppColors.textoSuave),
                  SizedBox(width: 12),
                  Expanded(
                    child: Text('No tenés entrevistas hoy.', style: TextStyle(color: AppColors.textoSuave)),
                  ),
                ],
              ),
            ),
          )
        else
          for (final e in deHoy) ...[
            _TarjetaEntrevista(entrevista: e, onEscribir: () => _escribir(e)),
            const SizedBox(height: 10),
          ],
        const SizedBox(height: 14),
        const TituloSeccion('Próximos días'),
        const SizedBox(height: 4),
        if (proximas.isEmpty)
          const Text(
            'No hay entrevistas agendadas para esta semana.',
            style: TextStyle(color: AppColors.textoSuave),
          )
        else
          for (final (i, e) in proximas.indexed) ...[
            if (i == 0 || !mismoDia(proximas[i - 1].inicio, e.inicio))
              Padding(
                padding: const EdgeInsets.only(top: 8, bottom: 8),
                child: Text(
                  capitalizar(fechaLarga(e.inicio)),
                  style: const TextStyle(color: AppColors.textoSuave, fontWeight: FontWeight.w600, fontSize: 13),
                ),
              ),
            _TarjetaEntrevista(entrevista: e, onEscribir: () => _escribir(e)),
            const SizedBox(height: 10),
          ],
        const SizedBox(height: 12),
        const Text(
          'Para proponer, reprogramar o cancelar entrevistas usá el panel web.',
          textAlign: TextAlign.center,
          style: TextStyle(color: AppColors.textoSuave, fontSize: 13),
        ),
      ],
    );
  }
}

class _CabeceraHoy extends StatelessWidget {
  final DateTime fecha;
  final int cantidad;
  const _CabeceraHoy({required this.fecha, required this.cantidad});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(color: AppColors.primario, borderRadius: BorderRadius.circular(AppTheme.radio)),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Hoy, ${fechaLarga(fecha)}',
                  style: const TextStyle(color: Color(0xFFC7D2FE), fontSize: 13, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 4),
                Text(
                  switch (cantidad) {
                    0 => 'Día libre de entrevistas',
                    1 => '1 entrevista',
                    _ => '$cantidad entrevistas',
                  },
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(color: Colors.white),
                ),
              ],
            ),
          ),
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.12), shape: BoxShape.circle),
            child: const Icon(Icons.event_rounded, color: Colors.white, size: 28),
          ),
        ],
      ),
    );
  }
}

class _TarjetaEntrevista extends StatelessWidget {
  final Entrevista entrevista;
  final VoidCallback onEscribir;
  const _TarjetaEntrevista({required this.entrevista, required this.onEscribir});

  @override
  Widget build(BuildContext context) {
    final e = entrevista;
    final estado = _estadoDe(e);
    final porVenir = (e.pendiente || e.confirmada) && !e.yaPaso;
    final lugar = e.esVirtual ? null : e.lugar;

    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 14, 14, 6),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 54,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(hora(e.inicio), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 17)),
                      if (e.fin != null)
                        Text(hora(e.fin!), style: const TextStyle(color: AppColors.textoTenue, fontSize: 13)),
                    ],
                  ),
                ),
                Container(width: 1, height: 58, color: AppColors.borde, margin: const EdgeInsets.only(right: 12)),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        e.candidatoNombre ?? 'Candidato',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15.5),
                      ),
                      if (e.vacanteTitulo != null)
                        Text(
                          e.vacanteTitulo!,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(color: AppColors.textoSuave, fontSize: 13),
                        ),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 10,
                        runSpacing: 6,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          Insignia(estado.texto, colores: estado.colores),
                          DatoConIcono(
                            e.esVirtual ? Icons.videocam_outlined : Icons.location_on_outlined,
                            e.esVirtual ? 'Videollamada' : 'Presencial',
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if (lugar != null) ...[
              const SizedBox(height: 10),
              Text(lugar, style: const TextStyle(color: AppColors.textoSuave, fontSize: 13)),
            ],
            const SizedBox(height: 4),
            Wrap(
              spacing: 4,
              children: [
                if (e.esVirtual && e.enlace != null && porVenir)
                  TextButton.icon(
                    onPressed: () => abrirVideollamada(context, e.enlace!),
                    icon: const Icon(Icons.videocam_outlined, size: 20),
                    label: const Text('Unirse'),
                  ),
                if (lugar != null && porVenir)
                  TextButton.icon(
                    onPressed: () => abrirMapa(context, lugar),
                    icon: const Icon(Icons.map_outlined, size: 20),
                    label: const Text('Cómo llegar'),
                  ),
                TextButton.icon(
                  onPressed: onEscribir,
                  icon: const Icon(Icons.chat_bubble_outline_rounded, size: 20),
                  label: const Text('Mensaje'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  /// El estado visto desde la empresa (la tarjeta del egresado habla en segunda persona).
  static ({String texto, ColoresInsignia colores}) _estadoDe(Entrevista e) {
    const gris = (color: AppColors.textoSuave, fondo: Color(0xFFF1F5F9));
    const realizada = (color: AppColors.primario, fondo: AppColors.primarioSuave);
    final ahora = DateTime.now();
    final enCurso = e.confirmada && !e.inicio.isAfter(ahora) && (e.fin ?? e.inicio.add(const Duration(hours: 1))).isAfter(ahora);
    return switch (e.estado) {
      'confirmed' when enCurso => (texto: 'En curso', colores: (color: AppColors.exito, fondo: AppColors.exitoSuave)),
      'confirmed' when e.yaPaso => (texto: 'Realizada', colores: realizada),
      'confirmed' => (texto: 'Confirmada', colores: (color: AppColors.exito, fondo: AppColors.exitoSuave)),
      'pending_confirmation' when e.yaPaso => (texto: 'Venció sin respuesta', colores: gris),
      'pending_confirmation' => (
        texto: 'Esperando confirmación',
        colores: (color: AppColors.alerta, fondo: AppColors.alertaSuave),
      ),
      'rejected' => (
        texto: 'No puede asistir',
        colores: (color: AppColors.peligro, fondo: AppColors.peligroSuave),
      ),
      'completed' => (texto: 'Realizada', colores: realizada),
      _ => (texto: 'Entrevista', colores: gris),
    };
  }
}
