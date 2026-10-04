import 'package:flutter/material.dart';

import '../../core/models/mensaje.dart';
import '../../core/services/mensaje_service.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/formatos.dart';
import '../../core/widgets/insignia.dart';
import '../../core/widgets/vistas_estado.dart';
import 'chat_screen.dart';

/// Bandeja de mensajes (HU-19): una fila por postulación con conversación,
/// la más reciente arriba. La empresa ve al candidato; el egresado, a la empresa.
class BandejaMensajesScreen extends StatefulWidget {
  final String accessToken;
  final bool esEmpresa;

  /// Acciones de la barra superior (la app de empresas pone el menú de la cuenta).
  final List<Widget>? acciones;

  /// Avisa el total de no leídos cada vez que carga, para el contador del menú.
  final ValueChanged<int>? onNoLeidos;

  const BandejaMensajesScreen({
    super.key,
    required this.accessToken,
    required this.esEmpresa,
    this.acciones,
    this.onNoLeidos,
  });

  @override
  State<BandejaMensajesScreen> createState() => _BandejaMensajesScreenState();
}

class _BandejaMensajesScreenState extends State<BandejaMensajesScreen> {
  late Future<List<ResumenConversacion>> _futuro = _cargar();

  Future<List<ResumenConversacion>> _cargar() async {
    final conversaciones = await MensajeService().conversaciones(widget.accessToken);
    widget.onNoLeidos?.call(conversaciones.fold(0, (total, c) => total + c.noLeidos));
    return conversaciones;
  }

  Future<void> _recargar() async {
    if (!mounted) return;
    final futuro = _cargar();
    setState(() { _futuro = futuro; });
    await futuro.then((_) {}, onError: (_) {});
  }

  Future<void> _abrir(ResumenConversacion c) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ChatScreen(
          accessToken: widget.accessToken,
          postulacionId: c.postulacionId,
          esEmpresa: widget.esEmpresa,
          titulo: widget.esEmpresa ? c.candidatoNombre : c.empresaNombre,
        ),
      ),
    );
    if (mounted) _recargar();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Mensajes'), actions: widget.acciones),
      body: FutureBuilder<List<ResumenConversacion>>(
        future: _futuro,
        builder: (context, snapshot) {
          if (snapshot.hasData) return RefreshIndicator(onRefresh: _recargar, child: _contenido(snapshot.data!));
          if (snapshot.connectionState == ConnectionState.waiting) return const VistaCargando();
          return VistaMensaje.error(snapshot.error, onReintentar: _recargar);
        },
      ),
    );
  }

  Widget _contenido(List<ResumenConversacion> conversaciones) {
    if (conversaciones.isEmpty) {
      // Dentro de un ListView para que igual se pueda deslizar para actualizar.
      return ListView(
        children: [
          const SizedBox(height: 80),
          VistaMensaje(
            icono: Icons.forum_outlined,
            titulo: 'Todavía no tenés mensajes',
            mensaje: widget.esEmpresa
                ? 'Escribile a un postulante desde la pestaña Postulantes o desde una entrevista de tu agenda.'
                : 'Cuando una empresa te escriba por una de tus postulaciones, vas a verlo acá. '
                      'También podés escribirle vos desde el detalle de la postulación.',
          ),
        ],
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
      itemCount: conversaciones.length,
      separatorBuilder: (_, _) => const SizedBox(height: 10),
      itemBuilder: (_, i) => _FilaConversacion(
        conversacion: conversaciones[i],
        esEmpresa: widget.esEmpresa,
        onTap: () => _abrir(conversaciones[i]),
      ),
    );
  }
}

class _FilaConversacion extends StatelessWidget {
  final ResumenConversacion conversacion;
  final bool esEmpresa;
  final VoidCallback onTap;
  const _FilaConversacion({required this.conversacion, required this.esEmpresa, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final c = conversacion;
    final nombre = esEmpresa ? c.candidatoNombre : c.empresaNombre;
    final sinLeer = c.noLeidos > 0;
    final vista = c.ultimoMensaje.replaceAll('\n', ' ');

    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppTheme.radio),
        side: BorderSide(color: sinLeer ? AppColors.primarioBorde : AppColors.borde),
      ),
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              esEmpresa ? AvatarPersona(nombre, tamano: 44) : AvatarEmpresa(nombre, tamano: 44),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            nombre,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          momentoCorto(c.ultimaFecha),
                          style: TextStyle(
                            fontSize: 12,
                            color: sinLeer ? AppColors.primario : AppColors.textoTenue,
                            fontWeight: sinLeer ? FontWeight.w600 : FontWeight.w400,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 1),
                    Text(
                      c.vacanteTitulo,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: AppColors.textoSuave, fontSize: 13),
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            c.ultimoEsMio ? 'Vos: $vista' : vista,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: 14,
                              color: sinLeer ? AppColors.texto : AppColors.textoSuave,
                              fontWeight: sinLeer ? FontWeight.w600 : FontWeight.w400,
                            ),
                          ),
                        ),
                        if (sinLeer) ...[const SizedBox(width: 8), ContadorNoLeidos(c.noLeidos)],
                      ],
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
}
