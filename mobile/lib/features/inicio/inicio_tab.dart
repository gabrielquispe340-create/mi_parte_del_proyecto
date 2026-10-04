import 'package:flutter/material.dart';

import '../../core/models/entrevista.dart';
import '../../core/models/mensaje.dart';
import '../../core/models/perfil_egresado.dart';
import '../../core/models/postulacion.dart';
import '../../core/models/sesion.dart';
import '../../core/services/entrevista_service.dart';
import '../../core/services/mensaje_service.dart';
import '../../core/services/perfil_service.dart';
import '../../core/services/postulacion_service.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/formatos.dart';
import '../../core/widgets/insignia.dart';
import '../../core/widgets/vistas_estado.dart';
import '../mensajes/bandeja_mensajes_screen.dart';
import '../mensajes/chat_screen.dart';
import '../notificaciones/notificaciones_screen.dart';
import '../perfil/mi_cv_screen.dart';
import '../postulaciones/postulacion_detalle_screen.dart';
import '../recomendaciones/recomendaciones_screen.dart';

/// Estados en los que una postulación ya terminó y no puede tener entrevistas pendientes.
const _estadosCerrados = {'rejected', 'withdrawn', 'hired'};

class _DatosInicio {
  final PerfilEgresado perfil;
  final ResumenPostulaciones resumen;
  final Map<String, List<Entrevista>> entrevistas;

  /// Conversaciones con mensajes sin leer (HU-19), la más reciente primero.
  final List<ResumenConversacion> sinLeer;
  const _DatosInicio(this.perfil, this.resumen, this.entrevistas, this.sinLeer);

  int get mensajesNoLeidos => sinLeer.fold(0, (total, c) => total + c.noLeidos);

  Iterable<Entrevista> get _todas => entrevistas.values.expand((lista) => lista);

  List<Entrevista> get porResponder =>
      _todas.where((e) => e.requiereRespuesta).toList()..sort((a, b) => a.inicio.compareTo(b.inicio));

  Entrevista? get proximaConfirmada {
    final confirmadas = _todas.where((e) => e.confirmada && !e.yaPaso).toList()
      ..sort((a, b) => a.inicio.compareTo(b.inicio));
    return confirmadas.isEmpty ? null : confirmadas.first;
  }

  /// Entrevistas por venir (propuestas o confirmadas): lo mismo que avisa la lista de postulaciones.
  int get proximas => _todas.where((e) => (e.pendiente || e.confirmada) && !e.yaPaso).length;

  PostulacionItem? postulacionDe(Entrevista e) =>
      resumen.postulaciones.where((p) => p.id == e.postulacionId).firstOrNull;
}

/// Pestaña de inicio del egresado: lo que requiere atención primero
/// (propuestas de entrevista), el resumen de postulaciones y el perfil.
class InicioTab extends StatefulWidget {
  final Sesion sesion;
  final ValueChanged<int> onIrA;

  const InicioTab({super.key, required this.sesion, required this.onIrA});

  @override
  State<InicioTab> createState() => _InicioTabState();
}

class _InicioTabState extends State<InicioTab> {
  late Future<_DatosInicio> _futuro = _cargar();

  Future<_DatosInicio> _cargar() async {
    final token = widget.sesion.accessToken;
    final resultados = await Future.wait<Object>([
      PerfilService().obtenerMiPerfil(token),
      PostulacionService().obtenerMisPostulaciones(token),
    ]);
    final resumen = resultados[1] as ResumenPostulaciones;
    final activas = resumen.postulaciones.where((p) => !_estadosCerrados.contains(p.estado)).map((p) => p.id);
    final (entrevistas, sinLeer) = await (
      EntrevistaService().deVariasPostulaciones(token, activas),
      _conversacionesSinLeer(token),
    ).wait;
    return _DatosInicio(resultados[0] as PerfilEgresado, resumen, entrevistas, sinLeer);
  }

  /// El aviso de mensajes es un extra: si la consulta falla, el inicio carga igual.
  Future<List<ResumenConversacion>> _conversacionesSinLeer(String token) async {
    try {
      final conversaciones = await MensajeService().conversaciones(token);
      return conversaciones.where((c) => c.noLeidos > 0).toList();
    } catch (_) {
      return const [];
    }
  }

  Future<void> _recargar() async {
    if (!mounted) return;
    final futuro = _cargar();
    setState(() { _futuro = futuro; });
    await futuro.then((_) {}, onError: (_) {});
  }

  Future<void> _abrir(Widget pantalla) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => pantalla));
    if (mounted) _recargar();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: FutureBuilder<_DatosInicio>(
          future: _futuro,
          builder: (context, snapshot) {
            // Al recargar se siguen mostrando los datos anteriores hasta que lleguen los nuevos.
            if (snapshot.hasData) return RefreshIndicator(onRefresh: _recargar, child: _contenido(snapshot.data!));
            if (snapshot.connectionState == ConnectionState.waiting) return const VistaCargando();
            return VistaMensaje.error(snapshot.error, onReintentar: _recargar);
          },
        ),
      ),
    );
  }

  Widget _contenido(_DatosInicio datos) {
    final token = widget.sesion.accessToken;
    final porResponder = datos.porResponder;
    final proxima = datos.proximaConfirmada;
    final recientes = datos.resumen.postulaciones.take(3).toList();

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
      children: [
        _Saludo(
          perfil: datos.perfil,
          universidad: widget.sesion.institucionNombre,
          mensajesNoLeidos: datos.mensajesNoLeidos,
          onMensajes: () => _abrir(BandejaMensajesScreen(accessToken: token, esEmpresa: false)),
          onNotificaciones: () => _abrir(NotificacionesScreen(accessToken: token)),
          onPerfil: () => widget.onIrA(3),
        ),
        const SizedBox(height: 22),
        if (datos.sinLeer.isNotEmpty) ...[
          _AvisoMensajes(
            conversaciones: datos.sinLeer,
            total: datos.mensajesNoLeidos,
            // Si es una sola conversación se abre directo; si son varias, la bandeja.
            onTap: () => _abrir(
              datos.sinLeer.length == 1
                  ? ChatScreen(
                      accessToken: token,
                      postulacionId: datos.sinLeer.first.postulacionId,
                      esEmpresa: false,
                      titulo: datos.sinLeer.first.empresaNombre,
                    )
                  : BandejaMensajesScreen(accessToken: token, esEmpresa: false),
            ),
          ),
          const SizedBox(height: 16),
        ],
        if (porResponder.isNotEmpty) ...[
          _AvisoEntrevista(
            entrevista: porResponder.first,
            cantidad: porResponder.length,
            postulacion: datos.postulacionDe(porResponder.first),
            onTap: () =>
                _abrir(PostulacionDetalleScreen(accessToken: token, postulacionId: porResponder.first.postulacionId)),
          ),
          const SizedBox(height: 16),
        ] else if (proxima != null) ...[
          _ProximaEntrevista(
            entrevista: proxima,
            postulacion: datos.postulacionDe(proxima),
            onTap: () => _abrir(PostulacionDetalleScreen(accessToken: token, postulacionId: proxima.postulacionId)),
          ),
          const SizedBox(height: 16),
        ],
        Row(
          children: [
            Expanded(
              child: _Metrica(valor: datos.resumen.activas, etiqueta: 'Activas', onTap: () => widget.onIrA(2)),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _Metrica(valor: datos.resumen.enRevision, etiqueta: 'En revisión', onTap: () => widget.onIrA(2)),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _Metrica(valor: datos.proximas, etiqueta: 'Entrevistas', onTap: () => widget.onIrA(2)),
            ),
          ],
        ),
        const SizedBox(height: 16),
        _TarjetaRecomendadas(onTap: () => _abrir(RecomendacionesScreen(accessToken: token))),
        const SizedBox(height: 16),
        _TarjetaPerfil(
          perfil: datos.perfil,
          onCompletar: () => _abrir(MiCvScreen(accessToken: token)),
        ),
        const SizedBox(height: 24),
        TituloSeccion('Tus últimas postulaciones', accion: 'Ver todas', onAccion: () => widget.onIrA(2)),
        const SizedBox(height: 8),
        if (recientes.isEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  const Text('Todavía no te postulaste a ninguna vacante.', textAlign: TextAlign.center),
                  const SizedBox(height: 12),
                  FilledButton(onPressed: () => widget.onIrA(1), child: const Text('Explorar vacantes')),
                ],
              ),
            ),
          )
        else
          Card(
            child: Column(
              children: [
                for (final (i, p) in recientes.indexed) ...[
                  if (i > 0) const Divider(indent: 16, endIndent: 16),
                  ListTile(
                    contentPadding: const EdgeInsets.fromLTRB(16, 8, 10, 8),
                    leading: AvatarEmpresa(p.empresaNombre, tamano: 40),
                    title: Text(p.jobTitulo, maxLines: 2, overflow: TextOverflow.ellipsis),
                    subtitle: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('${p.empresaNombre} · ${haceCuanto(p.fechaPostulacion)}'),
                        const SizedBox(height: 6),
                        Insignia(p.estadoLabel, colores: coloresDeEstado(p.estadoColor)),
                      ],
                    ),
                    trailing: const Icon(Icons.chevron_right_rounded, color: AppColors.textoTenue),
                    onTap: () => _abrir(PostulacionDetalleScreen(accessToken: token, postulacionId: p.id)),
                  ),
                ],
              ],
            ),
          ),
      ],
    );
  }
}

class _Saludo extends StatelessWidget {
  final PerfilEgresado perfil;
  final String? universidad;
  final int mensajesNoLeidos;
  final VoidCallback onMensajes;
  final VoidCallback onNotificaciones;
  final VoidCallback onPerfil;
  const _Saludo({
    required this.perfil,
    required this.universidad,
    required this.mensajesNoLeidos,
    required this.onMensajes,
    required this.onNotificaciones,
    required this.onPerfil,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                perfil.nombres.trim().isEmpty ? 'Hola' : 'Hola, ${perfil.nombres.trim().split(' ').first}',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              if (universidad != null) ...[
                const SizedBox(height: 4),
                DatoConIcono(Icons.school_outlined, universidad!),
              ],
            ],
          ),
        ),
        const SizedBox(width: 4),
        IconButton(
          onPressed: onNotificaciones,
          tooltip: 'Notificaciones y alertas',
          icon: const Icon(Icons.notifications_outlined, color: AppColors.primario, size: 26),
        ),
        IconButton(
          onPressed: onMensajes,
          tooltip: 'Mensajes',
          icon: Badge(
            isLabelVisible: mensajesNoLeidos > 0,
            label: Text(mensajesNoLeidos > 99 ? '99+' : '$mensajesNoLeidos'),
            child: const Icon(Icons.forum_outlined, color: AppColors.primario, size: 26),
          ),
        ),
        const SizedBox(width: 4),
        IconButton(
          onPressed: onPerfil,
          tooltip: 'Ir a mi perfil',
          padding: EdgeInsets.zero,
          icon: CircleAvatar(
            radius: 24,
            backgroundColor: AppColors.primario,
            child: Text(
              iniciales(perfil.nombreCompleto),
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
            ),
          ),
        ),
      ],
    );
  }
}

class _AvisoMensajes extends StatelessWidget {
  final List<ResumenConversacion> conversaciones;
  final int total;
  final VoidCallback onTap;
  const _AvisoMensajes({required this.conversaciones, required this.total, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final ultima = conversaciones.first;
    final empresas = conversaciones.map((c) => c.empresaNombre).toSet();
    return Card(
      color: AppColors.primarioSuave,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppTheme.radio),
        side: const BorderSide(color: AppColors.primarioBorde),
      ),
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: const BoxDecoration(color: Colors.white, shape: BoxShape.circle),
                child: const Icon(Icons.mark_chat_unread_outlined, color: AppColors.primario),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      total == 1 ? 'Tenés un mensaje nuevo' : 'Tenés $total mensajes nuevos',
                      style: const TextStyle(fontWeight: FontWeight.w700, color: AppColors.texto),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      empresas.length == 1
                          ? '${ultima.empresaNombre}: ${ultima.ultimoMensaje.replaceAll('\n', ' ')}'
                          : 'De ${empresas.length} empresas',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: AppColors.textoSuave, fontSize: 13),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right_rounded, color: AppColors.primario),
            ],
          ),
        ),
      ),
    );
  }
}

class _AvisoEntrevista extends StatelessWidget {
  final Entrevista entrevista;
  final int cantidad;
  final PostulacionItem? postulacion;
  final VoidCallback onTap;
  const _AvisoEntrevista({
    required this.entrevista,
    required this.cantidad,
    required this.postulacion,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final empresa = entrevista.empresaNombre ?? postulacion?.empresaNombre ?? 'Una empresa';
    final vacante = entrevista.vacanteTitulo ?? postulacion?.jobTitulo;
    return Card(
      color: AppColors.alertaSuave,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppTheme.radio),
        side: BorderSide(color: AppColors.alerta.withValues(alpha: 0.35)),
      ),
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: const BoxDecoration(color: Colors.white, shape: BoxShape.circle),
                child: const Icon(Icons.notifications_active_outlined, color: AppColors.alerta),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      cantidad == 1 ? 'Tenés una propuesta de entrevista' : 'Tenés $cantidad propuestas de entrevista',
                      style: const TextStyle(fontWeight: FontWeight.w700, color: AppColors.texto),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      [empresa, ?vacante].join(' · '),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: AppColors.textoSuave, fontSize: 13),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${cuandoSera(entrevista.inicio)} · ${hora(entrevista.inicio)}',
                      style: const TextStyle(color: AppColors.alerta, fontSize: 13, fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right_rounded, color: AppColors.alerta),
            ],
          ),
        ),
      ),
    );
  }
}

class _ProximaEntrevista extends StatelessWidget {
  final Entrevista entrevista;
  final PostulacionItem? postulacion;
  final VoidCallback onTap;
  const _ProximaEntrevista({required this.entrevista, required this.postulacion, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final empresa = entrevista.empresaNombre ?? postulacion?.empresaNombre ?? '';
    return Card(
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: const BoxDecoration(color: AppColors.exitoSuave, shape: BoxShape.circle),
                child: const Icon(Icons.event_available_outlined, color: AppColors.exito),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Próxima entrevista', style: TextStyle(color: AppColors.textoSuave, fontSize: 13)),
                    const SizedBox(height: 2),
                    Text(
                      '${cuandoSera(entrevista.inicio)} · ${hora(entrevista.inicio)}',
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    if (empresa.isNotEmpty)
                      Text(empresa, style: const TextStyle(color: AppColors.textoSuave, fontSize: 13)),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right_rounded, color: AppColors.textoTenue),
            ],
          ),
        ),
      ),
    );
  }
}

class _Metrica extends StatelessWidget {
  final int valor;
  final String etiqueta;
  final VoidCallback onTap;
  const _Metrica({required this.valor, required this.etiqueta, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('$valor', style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700, height: 1.1)),
              const SizedBox(height: 4),
              Text(
                etiqueta,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: AppColors.textoSuave, fontSize: 12.5, fontWeight: FontWeight.w500),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TarjetaRecomendadas extends StatelessWidget {
  final VoidCallback onTap;
  const _TarjetaRecomendadas({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      color: AppColors.primario,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppTheme.radio)),
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.auto_awesome_outlined, color: Colors.white),
              ),
              const SizedBox(width: 14),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Vacantes recomendadas para vos',
                      style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 15),
                    ),
                    SizedBox(height: 3),
                    Text(
                      'Según tu carrera, habilidades, experiencia e idiomas.',
                      style: TextStyle(color: Color(0xFFC7D2FE), fontSize: 13),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.arrow_forward_rounded, color: Colors.white),
            ],
          ),
        ),
      ),
    );
  }
}

class _TarjetaPerfil extends StatelessWidget {
  final PerfilEgresado perfil;
  final VoidCallback onCompletar;
  const _TarjetaPerfil({required this.perfil, required this.onCompletar});

  @override
  Widget build(BuildContext context) {
    final porcentaje = perfil.porcentajeCompletitud.clamp(0, 100);
    final completo = porcentaje >= 100;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text('Tu perfil', style: Theme.of(context).textTheme.titleMedium)),
                InsigniaValidacion(perfil.estadoValidacion),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(99),
                    child: LinearProgressIndicator(value: porcentaje / 100, minHeight: 8),
                  ),
                ),
                const SizedBox(width: 12),
                Text('$porcentaje%', style: const TextStyle(fontWeight: FontWeight.w700)),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              completo
                  ? 'Tu perfil está completo. Las empresas ven toda tu información.'
                  : 'Completá tu CV para que tus recomendaciones y tu afinidad sean más precisas.',
              style: const TextStyle(color: AppColors.textoSuave, fontSize: 13),
            ),
            if (!completo) ...[
              const SizedBox(height: 4),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: onCompletar,
                  style: TextButton.styleFrom(padding: EdgeInsets.zero),
                  icon: const Icon(Icons.edit_note_rounded),
                  label: const Text('Completar mi CV'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Estado de validación del egresado por su universidad.
class InsigniaValidacion extends StatelessWidget {
  final String estado;
  const InsigniaValidacion(this.estado, {super.key});

  @override
  Widget build(BuildContext context) {
    return switch (estado) {
      'APROBADO' => Insignia('Validado', colores: coloresDeEstado('green'), icono: Icons.verified_outlined),
      'RECHAZADO' => Insignia('Rechazado', colores: coloresDeEstado('red'), icono: Icons.block_outlined),
      _ => Insignia('Validación pendiente', colores: coloresDeEstado('yellow'), icono: Icons.hourglass_top_rounded),
    };
  }
}
