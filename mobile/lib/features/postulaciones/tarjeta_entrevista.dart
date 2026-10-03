import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/models/entrevista.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/formatos.dart';
import '../../core/widgets/insignia.dart';

/// Entrevista de una postulación (HU-20): cuándo, dónde y, si la empresa
/// todavía espera respuesta, los botones para confirmarla o rechazarla.
class TarjetaEntrevista extends StatefulWidget {
  final Entrevista entrevista;
  final Future<void> Function(Entrevista entrevista) onConfirmar;
  final Future<void> Function(Entrevista entrevista, String motivo) onRechazar;

  const TarjetaEntrevista({super.key, required this.entrevista, required this.onConfirmar, required this.onRechazar});

  @override
  State<TarjetaEntrevista> createState() => _TarjetaEntrevistaState();
}

class _TarjetaEntrevistaState extends State<TarjetaEntrevista> {
  bool _procesando = false;

  Entrevista get _e => widget.entrevista;

  Future<void> _confirmar() async {
    final cuando = '${fechaLarga(_e.inicio)} a las ${hora(_e.inicio)}';
    final ok = await showDialog<bool>(
      context: context,
      builder: (contexto) => AlertDialog(
        title: const Text('Confirmar asistencia'),
        content: Text('Vas a confirmar que asistís a la entrevista del $cuando. La empresa recibirá tu confirmación.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(contexto).pop(false), child: const Text('Volver')),
          FilledButton(onPressed: () => Navigator.of(contexto).pop(true), child: const Text('Confirmar')),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    await _ejecutar(() => widget.onConfirmar(_e));
  }

  Future<void> _rechazar() async {
    final motivo = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (_) => const _HojaRechazo(),
    );
    if (motivo == null || !mounted) return;
    await _ejecutar(() => widget.onRechazar(_e, motivo));
  }

  /// Los callbacks deberían manejar sus errores; si alguno se escapa, se avisa
  /// acá en vez de dejar un error sin capturar desde el botón.
  Future<void> _ejecutar(Future<void> Function() accion) async {
    setState(() => _procesando = true);
    try {
      await accion();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _procesando = false);
    }
  }

  /// El enlace lo escribe la empresa: solo se abren direcciones http(s), y si
  /// viene sin esquema ("meet.google.com/abc") se asume https.
  static Uri? _enlaceSeguro(String texto) {
    final limpio = texto.trim();
    final uri = Uri.tryParse(limpio.contains('://') ? limpio : 'https://$limpio');
    if (uri == null || !(uri.scheme == 'https' || uri.scheme == 'http') || uri.host.isEmpty) return null;
    return uri;
  }

  /// Abre [uri] en otra app; si no se puede, copia [texto] y avisa con [siFalla].
  Future<void> _abrirAfuera(Uri? uri, String texto, String siFalla) async {
    var abierto = false;
    if (uri != null) {
      try {
        abierto = await launchUrl(uri, mode: LaunchMode.externalApplication);
      } catch (_) {
        abierto = false;
      }
    }
    if (abierto || !mounted) return;
    await Clipboard.setData(ClipboardData(text: texto));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(siFalla)));
  }

  Future<void> _abrirEnlace() async {
    final enlace = _e.enlace;
    if (enlace == null) return;
    await _abrirAfuera(
      _enlaceSeguro(enlace),
      enlace,
      'No se pudo abrir el enlace. Lo copiamos para que lo pegues en tu navegador.',
    );
  }

  Future<void> _abrirMapa(String lugar) => _abrirAfuera(
    Uri.https('www.google.com', '/maps/search/', {'api': '1', 'query': lugar}),
    lugar,
    'No se pudo abrir el mapa. Copiamos la dirección.',
  );

  @override
  Widget build(BuildContext context) {
    final estilo = _estiloDe(_e);
    final porVenir = (_e.pendiente || _e.confirmada) && !_e.yaPaso;
    final mostrarEnlace = _e.esVirtual && _e.enlace != null && porVenir;
    final lugar = _e.esVirtual ? null : _e.lugar?.trim();
    final tieneLugar = lugar != null && lugar.isNotEmpty;

    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppTheme.radio),
        side: BorderSide(color: _e.requiereRespuesta ? estilo.colores.color.withValues(alpha: 0.45) : AppColors.borde),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            color: estilo.colores.fondo,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: Row(
              children: [
                Icon(estilo.icono, size: 20, color: estilo.colores.color),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    estilo.titulo,
                    style: TextStyle(color: estilo.colores.color, fontWeight: FontWeight.w600, fontSize: 14),
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    _BloqueCalendario(_e.inicio),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            capitalizar(fechaLarga(_e.inicio)),
                            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
                          ),
                          const SizedBox(height: 2),
                          Text(rangoHorario(_e.inicio, _e.fin), style: const TextStyle(color: AppColors.textoSuave)),
                          const SizedBox(height: 6),
                          DatoConIcono(
                            _e.esVirtual ? Icons.videocam_outlined : Icons.location_on_outlined,
                            _e.esVirtual ? 'Videollamada' : 'Presencial',
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                if (tieneLugar) ...[const SizedBox(height: 14), _Nota(titulo: 'Dirección', texto: lugar)],
                if (_e.indicaciones != null) ...[
                  const SizedBox(height: 14),
                  _Nota(titulo: 'Indicaciones de la empresa', texto: _e.indicaciones!),
                ],
                if (_e.estado == 'rejected' && _e.motivoRechazo != null) ...[
                  const SizedBox(height: 14),
                  _Nota(titulo: 'Tu respuesta', texto: _e.motivoRechazo!),
                ],
                if (_e.requiereRevision) ...[
                  const SizedBox(height: 12),
                  const Text(
                    'La empresa va a revisar la agenda antes de proponerte una nueva fecha.',
                    style: TextStyle(color: AppColors.textoSuave, fontSize: 13),
                  ),
                ],
                if (mostrarEnlace) ...[
                  const SizedBox(height: 14),
                  OutlinedButton.icon(
                    onPressed: _abrirEnlace,
                    icon: const Icon(Icons.videocam_outlined),
                    label: const Text('Unirse a la videollamada'),
                  ),
                ],
                if (tieneLugar && porVenir) ...[
                  const SizedBox(height: 14),
                  OutlinedButton.icon(
                    onPressed: () => _abrirMapa(lugar),
                    icon: const Icon(Icons.map_outlined),
                    label: const Text('Cómo llegar'),
                  ),
                ],
                if (_e.requiereRespuesta) ...[
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: _procesando ? null : _confirmar,
                    child: _procesando
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white),
                          )
                        : const Text('Confirmar asistencia'),
                  ),
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: _procesando ? null : _rechazar,
                    style: TextButton.styleFrom(foregroundColor: AppColors.peligro, minimumSize: const Size(64, 48)),
                    child: const Text('No puedo asistir'),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

typedef _Estilo = ({String titulo, IconData icono, ColoresInsignia colores});

_Estilo _estiloDe(Entrevista e) {
  const gris = (color: AppColors.textoSuave, fondo: Color(0xFFF1F5F9));
  return switch (e.estado) {
    'pending_confirmation' when e.yaPaso => (
      titulo: 'La propuesta venció sin respuesta',
      icono: Icons.event_busy_outlined,
      colores: gris,
    ),
    'pending_confirmation' => (
      titulo: 'Te propusieron una entrevista',
      icono: Icons.notifications_active_outlined,
      colores: (color: AppColors.alerta, fondo: AppColors.alertaSuave),
    ),
    'confirmed' when e.yaPaso => (
      titulo: 'Entrevista realizada',
      icono: Icons.task_alt_rounded,
      colores: (color: AppColors.primario, fondo: AppColors.primarioSuave),
    ),
    'confirmed' => (
      titulo: 'Entrevista confirmada',
      icono: Icons.event_available_outlined,
      colores: (color: AppColors.exito, fondo: AppColors.exitoSuave),
    ),
    'rejected' => (
      titulo: 'Rechazaste esta propuesta',
      icono: Icons.event_busy_outlined,
      colores: (color: AppColors.peligro, fondo: AppColors.peligroSuave),
    ),
    'cancelled' => (titulo: 'La empresa canceló la entrevista', icono: Icons.event_busy_outlined, colores: gris),
    'completed' => (
      titulo: 'Entrevista realizada',
      icono: Icons.task_alt_rounded,
      colores: (color: AppColors.primario, fondo: AppColors.primarioSuave),
    ),
    _ => (titulo: 'Entrevista', icono: Icons.event_outlined, colores: gris),
  };
}

/// Hoja inferior para rechazar: el motivo es obligatorio y lo ve la empresa.
class _HojaRechazo extends StatefulWidget {
  const _HojaRechazo();

  @override
  State<_HojaRechazo> createState() => _HojaRechazoState();
}

class _HojaRechazoState extends State<_HojaRechazo> {
  final _clave = GlobalKey<FormState>();
  final _motivo = TextEditingController();

  @override
  void dispose() {
    _motivo.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
      child: Form(
        key: _clave,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('No puedo asistir', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 6),
            const Text(
              'Contale a la empresa el motivo o proponé otro horario. Con tu respuesta puede ofrecerte una nueva fecha.',
              style: TextStyle(color: AppColors.textoSuave),
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _motivo,
              autofocus: true,
              minLines: 3,
              maxLines: 5,
              maxLength: 1000,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(
                hintText: 'Ej.: Tengo un examen ese día. Puedo el viernes por la tarde.',
              ),
              validator: (valor) =>
                  (valor == null || valor.trim().length < 3) ? 'Escribí un motivo (al menos 3 caracteres).' : null,
            ),
            const SizedBox(height: 8),
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: AppColors.peligro),
              onPressed: () {
                if (_clave.currentState!.validate()) Navigator.of(context).pop(_motivo.text.trim());
              },
              child: const Text('Enviar respuesta'),
            ),
          ],
        ),
      ),
    );
  }
}

class _BloqueCalendario extends StatelessWidget {
  final DateTime fecha;
  const _BloqueCalendario(this.fecha);

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 58,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.borde),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          Container(
            width: double.infinity,
            color: AppColors.primario,
            padding: const EdgeInsets.symmetric(vertical: 3),
            child: Text(
              mesAbreviado(fecha),
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 11,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.8,
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Text('${fecha.day}', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, height: 1.1)),
          ),
        ],
      ),
    );
  }
}

class _Nota extends StatelessWidget {
  final String titulo;
  final String texto;
  const _Nota({required this.titulo, required this.texto});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: AppColors.fondo, borderRadius: BorderRadius.circular(10)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            titulo,
            style: const TextStyle(color: AppColors.textoSuave, fontSize: 12, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 4),
          Text(texto),
        ],
      ),
    );
  }
}
