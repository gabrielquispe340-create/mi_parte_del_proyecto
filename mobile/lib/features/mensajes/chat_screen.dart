import 'dart:async';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:open_filex/open_filex.dart';

import '../../core/models/mensaje.dart';
import '../../core/services/mensaje_service.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/formatos.dart';
import '../../core/widgets/vistas_estado.dart';

/// Cada cuánto se buscan mensajes nuevos mientras el chat está abierto (no hay push).
const _intervaloActualizacion = Duration(seconds: 8);

/// Conversación entre la empresa y el egresado de una postulación (HU-19).
/// La usan las dos apps: [esEmpresa] decide a quién se nombra en la cabecera.
class ChatScreen extends StatefulWidget {
  final String accessToken;
  final String postulacionId;
  final bool esEmpresa;

  /// Nombre de la otra parte, para la cabecera mientras carga el hilo.
  final String? titulo;

  const ChatScreen({
    super.key,
    required this.accessToken,
    required this.postulacionId,
    required this.esEmpresa,
    this.titulo,
  });

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> with WidgetsBindingObserver {
  final _servicio = MensajeService();
  final _texto = TextEditingController();
  final _descargando = <String>{};

  HiloMensajes? _hilo;
  Object? _error;
  ArchivoParaEnviar? _archivo;
  bool _enviando = false;
  bool _actualizando = false;
  Timer? _temporizador;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _texto.addListener(() => setState(() {}));
    _actualizar();
    _iniciarTemporizador();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _temporizador?.cancel();
    _texto.dispose();
    super.dispose();
  }

  /// Con la app en segundo plano no se consulta al servidor.
  @override
  void didChangeAppLifecycleState(AppLifecycleState estado) {
    if (estado == AppLifecycleState.resumed) {
      _actualizar();
      _iniciarTemporizador();
    } else {
      _temporizador?.cancel();
    }
  }

  void _iniciarTemporizador() {
    _temporizador?.cancel();
    _temporizador = Timer.periodic(_intervaloActualizacion, (_) => _actualizar());
  }

  Future<void> _actualizar() async {
    if (_actualizando) return;
    _actualizando = true;
    try {
      final hilo = await _servicio.hilo(widget.accessToken, widget.postulacionId);
      if (mounted) {
        setState(() {
          _hilo = hilo;
          _error = null;
        });
      }
    } catch (e) {
      // Si ya hay mensajes en pantalla, un corte momentáneo no los tapa.
      if (mounted && _hilo == null) setState(() => _error = e);
    } finally {
      _actualizando = false;
    }
  }

  Future<void> _reintentar() async {
    setState(() => _error = null);
    await _actualizar();
  }

  void _avisar(String mensaje) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(mensaje)));
  }

  Future<void> _elegirArchivo() async {
    try {
      final elegido = await FilePicker.pickFile();
      if (elegido == null) return;
      final tamano = await elegido.length();
      if (tamano != null && tamano > tamanoMaximoAdjunto) {
        _avisar('El archivo pesa ${tamanoLegible(tamano)}. El máximo es 5 MB.');
        return;
      }
      final bytes = await elegido.readAsBytes();
      if (bytes.isEmpty) {
        _avisar('El archivo está vacío.');
      } else if (bytes.length > tamanoMaximoAdjunto) {
        _avisar('El archivo pesa ${tamanoLegible(bytes.length)}. El máximo es 5 MB.');
      } else if (mounted) {
        setState(() => _archivo = ArchivoParaEnviar(elegido.name, bytes));
      }
    } catch (_) {
      _avisar('No se pudo leer el archivo. Probá con otro.');
    }
  }

  Future<void> _enviar() async {
    final texto = _texto.text.trim();
    if ((texto.isEmpty && _archivo == null) || _enviando) return;
    setState(() => _enviando = true);
    try {
      await _servicio.enviar(widget.accessToken, widget.postulacionId, texto: texto, archivo: _archivo);
      _texto.clear();
      if (mounted) setState(() => _archivo = null);
      await _actualizar();
    } catch (e) {
      _avisar('$e');
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  Future<void> _abrirAdjunto(Adjunto adjunto) async {
    if (_descargando.contains(adjunto.id)) return;
    setState(() => _descargando.add(adjunto.id));
    try {
      final archivo = await _servicio.descargarAdjunto(widget.accessToken, adjunto);
      final tipo = adjunto.tipo == null || adjunto.tipo == 'application/octet-stream' ? null : adjunto.tipo;
      final resultado = await OpenFilex.open(archivo.path, type: tipo);
      if (resultado.type == ResultType.noAppToOpen) {
        _avisar('No tenés una app para abrir este tipo de archivo.');
      } else if (resultado.type != ResultType.done) {
        _avisar('No se pudo abrir el archivo.');
      }
    } catch (e) {
      _avisar('$e');
    } finally {
      if (mounted) setState(() => _descargando.remove(adjunto.id));
    }
  }

  @override
  Widget build(BuildContext context) {
    final hilo = _hilo;
    final titulo = hilo == null ? widget.titulo : (widget.esEmpresa ? hilo.candidatoNombre : hilo.empresaNombre);
    final subtitulo = hilo == null
        ? null
        : [hilo.vacanteTitulo, if (widget.esEmpresa && hilo.candidatoCarrera != null) hilo.candidatoCarrera!].join(' · ');

    return Scaffold(
      appBar: AppBar(
        titleSpacing: 0,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(titulo ?? 'Mensajes', maxLines: 1, overflow: TextOverflow.ellipsis),
            if (subtitulo != null)
              Text(
                subtitulo,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w400, color: AppColors.textoSuave),
              ),
          ],
        ),
      ),
      body: Column(
        children: [
          Expanded(child: _cuerpo(hilo)),
          if (hilo != null) _barraDeEnvio(),
        ],
      ),
    );
  }

  Widget _cuerpo(HiloMensajes? hilo) {
    if (hilo == null) {
      return _error == null ? const VistaCargando() : VistaMensaje.error(_error, onReintentar: _reintentar);
    }
    if (hilo.mensajes.isEmpty) {
      return VistaMensaje(
        icono: Icons.forum_outlined,
        titulo: 'Todavía no hay mensajes',
        mensaje: widget.esEmpresa
            ? 'Escribile a ${hilo.candidatoNombre} para coordinar la entrevista o pedirle documentos.'
            : 'Podés escribirle a ${hilo.empresaNombre} sobre tu postulación a ${hilo.vacanteTitulo}.',
      );
    }

    // La lista va invertida para que arranque abajo, en el mensaje más nuevo.
    final elementos = <Widget>[];
    DateTime? diaAnterior;
    for (final m in hilo.mensajes) {
      if (diaAnterior == null || !mismoDia(diaAnterior, m.fecha)) {
        elementos.add(_SeparadorDia(diaDeConversacion(m.fecha)));
        diaAnterior = m.fecha;
      }
      elementos.add(
        _Burbuja(mensaje: m, descargando: m.adjunto != null && _descargando.contains(m.adjunto!.id), onAdjunto: _abrirAdjunto),
      );
    }
    final invertidos = elementos.reversed.toList();
    return ListView.builder(
      reverse: true,
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
      itemCount: invertidos.length,
      itemBuilder: (_, i) => invertidos[i],
    );
  }

  Widget _barraDeEnvio() {
    final puedeEnviar = (_texto.text.trim().isNotEmpty || _archivo != null) && !_enviando;
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: AppColors.superficie,
        border: Border(top: BorderSide(color: AppColors.borde)),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(8, 8, 8, 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (_archivo != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(4, 0, 4, 8),
                child: _ArchivoElegido(
                  archivo: _archivo!,
                  onQuitar: _enviando ? null : () => setState(() => _archivo = null),
                ),
              ),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                IconButton(
                  tooltip: 'Adjuntar archivo (hasta 5 MB)',
                  onPressed: _enviando ? null : _elegirArchivo,
                  icon: const Icon(Icons.attach_file_rounded),
                ),
                Expanded(
                  child: TextField(
                    controller: _texto,
                    minLines: 1,
                    maxLines: 5,
                    textCapitalization: TextCapitalization.sentences,
                    decoration: const InputDecoration(
                      hintText: 'Escribí un mensaje',
                      contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                IconButton.filled(
                  tooltip: 'Enviar',
                  onPressed: puedeEnviar ? _enviar : null,
                  icon: _enviando
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white),
                        )
                      : const Icon(Icons.send_rounded),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _SeparadorDia extends StatelessWidget {
  final String texto;
  const _SeparadorDia(this.texto);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Center(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          decoration: BoxDecoration(color: AppColors.borde, borderRadius: BorderRadius.circular(999)),
          child: Text(
            texto,
            style: const TextStyle(color: AppColors.textoSuave, fontSize: 12, fontWeight: FontWeight.w600),
          ),
        ),
      ),
    );
  }
}

class _Burbuja extends StatelessWidget {
  final Mensaje mensaje;
  final bool descargando;
  final ValueChanged<Adjunto> onAdjunto;
  const _Burbuja({required this.mensaje, required this.descargando, required this.onAdjunto});

  @override
  Widget build(BuildContext context) {
    final mio = mensaje.esMio;
    final colorTexto = mio ? Colors.white : AppColors.texto;
    const radio = Radius.circular(16);

    return Align(
      alignment: mio ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.8),
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 3),
          padding: const EdgeInsets.fromLTRB(12, 9, 12, 7),
          decoration: BoxDecoration(
            color: mio ? AppColors.primario : AppColors.superficie,
            border: mio ? null : Border.all(color: AppColors.borde),
            borderRadius: BorderRadius.only(
              topLeft: radio,
              topRight: radio,
              bottomLeft: mio ? radio : const Radius.circular(4),
              bottomRight: mio ? const Radius.circular(4) : radio,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            mainAxisSize: MainAxisSize.min,
            children: [
              if (mensaje.adjunto != null)
                _TarjetaAdjunto(
                  adjunto: mensaje.adjunto!,
                  mio: mio,
                  descargando: descargando,
                  onTap: () => onAdjunto(mensaje.adjunto!),
                ),
              if (!mensaje.soloAdjunto) ...[
                if (mensaje.adjunto != null) const SizedBox(height: 6),
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text(mensaje.contenido, style: TextStyle(color: colorTexto, fontSize: 15, height: 1.35)),
                ),
              ],
              const SizedBox(height: 3),
              Text(
                hora(mensaje.fecha),
                style: TextStyle(color: mio ? const Color(0xFFC7D2FE) : AppColors.textoTenue, fontSize: 11),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TarjetaAdjunto extends StatelessWidget {
  final Adjunto adjunto;
  final bool mio;
  final bool descargando;
  final VoidCallback onTap;
  const _TarjetaAdjunto({required this.adjunto, required this.mio, required this.descargando, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final color = mio ? Colors.white : AppColors.primario;
    return Material(
      color: mio ? Colors.white.withValues(alpha: 0.14) : AppColors.primarioSuave,
      borderRadius: BorderRadius.circular(10),
      child: InkWell(
        onTap: descargando ? null : onTap,
        borderRadius: BorderRadius.circular(10),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(10, 8, 12, 8),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              SizedBox(
                width: 24,
                height: 24,
                child: descargando
                    ? Padding(
                        padding: const EdgeInsets.all(3),
                        child: CircularProgressIndicator(strokeWidth: 2.2, color: color),
                      )
                    : Icon(_iconoDe(adjunto), color: color, size: 24),
              ),
              const SizedBox(width: 10),
              Flexible(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      adjunto.nombre,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(color: mio ? Colors.white : AppColors.texto, fontWeight: FontWeight.w600, fontSize: 14),
                    ),
                    Text(
                      [if (adjunto.tamano != null) tamanoLegible(adjunto.tamano!), 'Tocá para abrir'].join(' · '),
                      style: TextStyle(color: mio ? const Color(0xFFC7D2FE) : AppColors.textoSuave, fontSize: 12),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static IconData _iconoDe(Adjunto adjunto) {
    final tipo = adjunto.tipo ?? '';
    final nombre = adjunto.nombre.toLowerCase();
    if (tipo.startsWith('image/')) return Icons.image_outlined;
    if (tipo == 'application/pdf' || nombre.endsWith('.pdf')) return Icons.picture_as_pdf_outlined;
    return Icons.insert_drive_file_outlined;
  }
}

class _ArchivoElegido extends StatelessWidget {
  final ArchivoParaEnviar archivo;
  final VoidCallback? onQuitar;
  const _ArchivoElegido({required this.archivo, required this.onQuitar});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 6, 4, 6),
      decoration: BoxDecoration(color: AppColors.primarioSuave, borderRadius: BorderRadius.circular(10)),
      child: Row(
        children: [
          const Icon(Icons.attach_file_rounded, size: 18, color: AppColors.primario),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '${archivo.nombre} · ${tamanoLegible(archivo.bytes.length)}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: AppColors.primario, fontWeight: FontWeight.w600, fontSize: 13),
            ),
          ),
          IconButton(
            tooltip: 'Quitar archivo',
            visualDensity: VisualDensity.compact,
            onPressed: onQuitar,
            icon: const Icon(Icons.close_rounded, size: 18, color: AppColors.primario),
          ),
        ],
      ),
    );
  }
}
