import 'package:flutter/material.dart';

import '../../core/models/entrevista.dart';
import '../../core/models/postulacion.dart';
import '../../core/services/entrevista_service.dart';
import '../../core/services/mensaje_service.dart';
import '../../core/services/postulacion_service.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/formatos.dart';
import '../../core/widgets/insignia.dart';
import '../../core/widgets/vistas_estado.dart';
import 'postulacion_detalle_screen.dart';

/// Estados en los que la postulación ya terminó (incluye la contratación).
const _estadosFinalizados = {'rejected', 'withdrawn', 'hired'};

enum _Filtro { activas, todas, finalizadas }

class _Datos {
  final ResumenPostulaciones resumen;
  final Map<String, List<Entrevista>> entrevistas;

  /// Mensajes sin leer por postulación (HU-19).
  final Map<String, int> noLeidos;
  const _Datos(this.resumen, this.entrevistas, this.noLeidos);
}

/// Seguimiento de postulaciones (HU-15), con el aviso de entrevistas por
/// responder (HU-20). Mismo endpoint que el tablero de la web.
class MisPostulacionesScreen extends StatefulWidget {
  final String accessToken;

  const MisPostulacionesScreen({super.key, required this.accessToken});

  @override
  State<MisPostulacionesScreen> createState() => _MisPostulacionesScreenState();
}

class _MisPostulacionesScreenState extends State<MisPostulacionesScreen> {
  late Future<_Datos> _futuro = _cargar();
  _Filtro _filtro = _Filtro.activas;

  Future<_Datos> _cargar() async {
    final resumen = await PostulacionService().obtenerMisPostulaciones(widget.accessToken);
    final activas = resumen.postulaciones.where((p) => !_estadosFinalizados.contains(p.estado)).map((p) => p.id);
    final (entrevistas, noLeidos) = await (
      EntrevistaService().deVariasPostulaciones(widget.accessToken, activas),
      _noLeidosPorPostulacion(),
    ).wait;
    return _Datos(resumen, entrevistas, noLeidos);
  }

  /// El aviso de mensajes es un extra: si la consulta falla, la lista carga igual.
  Future<Map<String, int>> _noLeidosPorPostulacion() async {
    try {
      final conversaciones = await MensajeService().conversaciones(widget.accessToken);
      return {for (final c in conversaciones) if (c.noLeidos > 0) c.postulacionId: c.noLeidos};
    } catch (_) {
      return const {};
    }
  }

  Future<void> _recargar() async {
    if (!mounted) return;
    final futuro = _cargar();
    setState(() => _futuro = futuro);
    await futuro.then((_) {}, onError: (_) {});
  }

  Future<void> _abrir(PostulacionItem p) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => PostulacionDetalleScreen(accessToken: widget.accessToken, postulacionId: p.id),
      ),
    );
    if (mounted) _recargar();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Mis postulaciones')),
      body: FutureBuilder<_Datos>(
        future: _futuro,
        builder: (context, snapshot) {
          if (snapshot.hasData) return RefreshIndicator(onRefresh: _recargar, child: _contenido(snapshot.data!));
          if (snapshot.connectionState == ConnectionState.waiting) return const VistaCargando();
          return VistaMensaje.error(snapshot.error, onReintentar: _recargar);
        },
      ),
    );
  }

  Widget _contenido(_Datos datos) {
    final todas = datos.resumen.postulaciones;
    final finalizadas = todas.where((p) => _estadosFinalizados.contains(p.estado)).toList();
    final activas = todas.where((p) => !_estadosFinalizados.contains(p.estado)).toList();
    final visibles = switch (_filtro) {
      _Filtro.activas => activas,
      _Filtro.todas => todas,
      _Filtro.finalizadas => finalizadas,
    };

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
      children: [
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              _ChipFiltro('Activas', activas.length, seleccionado: _filtro == _Filtro.activas,
                  onTap: () => setState(() => _filtro = _Filtro.activas)),
              const SizedBox(width: 8),
              _ChipFiltro('Todas', todas.length, seleccionado: _filtro == _Filtro.todas,
                  onTap: () => setState(() => _filtro = _Filtro.todas)),
              const SizedBox(width: 8),
              _ChipFiltro('Finalizadas', finalizadas.length, seleccionado: _filtro == _Filtro.finalizadas,
                  onTap: () => setState(() => _filtro = _Filtro.finalizadas)),
            ],
          ),
        ),
        const SizedBox(height: 14),
        if (visibles.isEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 48),
            child: VistaMensaje(
              icono: Icons.assignment_outlined,
              titulo: todas.isEmpty ? 'Todavía no te postulaste' : 'No hay postulaciones en esta lista',
              mensaje: todas.isEmpty
                  ? 'Explorá las vacantes y postulate a las que te interesen; vas a poder seguir cada proceso desde acá.'
                  : null,
            ),
          )
        else
          for (final p in visibles) ...[
            _TarjetaPostulacion(
              postulacion: p,
              entrevistas: datos.entrevistas[p.id] ?? const [],
              mensajesNoLeidos: datos.noLeidos[p.id] ?? 0,
              onTap: () => _abrir(p),
            ),
            const SizedBox(height: 12),
          ],
      ],
    );
  }
}

class _ChipFiltro extends StatelessWidget {
  final String texto;
  final int cantidad;
  final bool seleccionado;
  final VoidCallback onTap;
  const _ChipFiltro(this.texto, this.cantidad, {required this.seleccionado, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ChoiceChip(
      label: Text('$texto · $cantidad'),
      selected: seleccionado,
      onSelected: (_) => onTap(),
      showCheckmark: false,
      selectedColor: AppColors.primarioSuave,
      side: BorderSide(color: seleccionado ? AppColors.primarioBorde : AppColors.borde),
      labelStyle: TextStyle(
        fontFamily: 'Inter',
        fontSize: 13,
        fontWeight: seleccionado ? FontWeight.w600 : FontWeight.w500,
        color: seleccionado ? AppColors.primario : AppColors.textoSuave,
      ),
    );
  }
}

class _TarjetaPostulacion extends StatelessWidget {
  final PostulacionItem postulacion;
  final List<Entrevista> entrevistas;
  final int mensajesNoLeidos;
  final VoidCallback onTap;
  const _TarjetaPostulacion({
    required this.postulacion,
    required this.entrevistas,
    required this.mensajesNoLeidos,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final p = postulacion;
    final porResponder = entrevistas.where((e) => e.requiereRespuesta).firstOrNull;
    final confirmada = entrevistas.where((e) => e.confirmada && !e.yaPaso).firstOrNull;
    final ubicacion = [p.empresaNombre, if (p.empresaCiudad != null && p.empresaCiudad!.isNotEmpty) p.empresaCiudad!];

    return Card(
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  AvatarEmpresa(p.empresaNombre, tamano: 40),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          p.jobTitulo,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15.5, height: 1.3),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          ubicacion.join(' · '),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(color: AppColors.textoSuave, fontSize: 13),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: Align(
                      alignment: Alignment.centerLeft,
                      child: Insignia(p.estadoLabel, colores: coloresDeEstado(p.estadoColor)),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    capitalizar(haceCuanto(p.fechaPostulacion)),
                    style: const TextStyle(color: AppColors.textoSuave, fontSize: 12),
                  ),
                ],
              ),
              if (p.etapaActualNombre != null && p.etapaActualNombre!.isNotEmpty) ...[
                const SizedBox(height: 8),
                DatoConIcono(Icons.flag_outlined, 'Etapa: ${p.etapaActualNombre}'),
              ],
              if (porResponder != null)
                _Aviso(
                  icono: Icons.notifications_active_outlined,
                  texto: 'Te propusieron una entrevista: ${cuandoSera(porResponder.inicio).toLowerCase()} a las ${hora(porResponder.inicio)}',
                  colores: (color: AppColors.alerta, fondo: AppColors.alertaSuave),
                )
              else if (confirmada != null)
                _Aviso(
                  icono: Icons.event_available_outlined,
                  texto: 'Entrevista ${cuandoSera(confirmada.inicio).toLowerCase()} a las ${hora(confirmada.inicio)}',
                  colores: (color: AppColors.exito, fondo: AppColors.exitoSuave),
                ),
              if (mensajesNoLeidos > 0)
                _Aviso(
                  icono: Icons.mark_chat_unread_outlined,
                  texto: mensajesNoLeidos == 1
                      ? '1 mensaje nuevo de ${p.empresaNombre}'
                      : '$mensajesNoLeidos mensajes nuevos de ${p.empresaNombre}',
                  colores: (color: AppColors.primario, fondo: AppColors.primarioSuave),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Aviso extends StatelessWidget {
  final IconData icono;
  final String texto;
  final ColoresInsignia colores;
  const _Aviso({required this.icono, required this.texto, required this.colores});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(color: colores.fondo, borderRadius: BorderRadius.circular(10)),
      child: Row(
        children: [
          Icon(icono, size: 18, color: colores.color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(texto, style: TextStyle(color: colores.color, fontWeight: FontWeight.w600, fontSize: 13)),
          ),
          Icon(Icons.chevron_right_rounded, size: 20, color: colores.color),
        ],
      ),
    );
  }
}
