import 'package:flutter/material.dart';

import '../../core/models/postulante_nuevo.dart';
import '../../core/services/empresa_service.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/abrir_afuera.dart';
import '../../core/utils/formatos.dart';
import '../../core/widgets/insignia.dart';
import '../../core/widgets/vistas_estado.dart';
import '../mensajes/chat_screen.dart';

/// Postulantes que nadie de la empresa revisó todavía, de todas sus vacantes.
class PostulantesTab extends StatefulWidget {
  final String accessToken;
  final List<Widget> acciones;

  const PostulantesTab({super.key, required this.accessToken, required this.acciones});

  @override
  State<PostulantesTab> createState() => _PostulantesTabState();
}

class _PostulantesTabState extends State<PostulantesTab> {
  late Future<PostulantesNuevos> _futuro = EmpresaService().postulantesNuevos(widget.accessToken);

  Future<void> _recargar() async {
    if (!mounted) return;
    final futuro = EmpresaService().postulantesNuevos(widget.accessToken);
    setState(() { _futuro = futuro; });
    await futuro.then((_) {}, onError: (_) {});
  }

  Future<void> _verFicha(PostulanteNuevo p) async {
    final escribir = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _FichaPostulante(p),
    );
    if (escribir != true || !mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ChatScreen(
          accessToken: widget.accessToken,
          postulacionId: p.postulacionId,
          esEmpresa: true,
          titulo: p.nombre,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Postulantes'), actions: widget.acciones),
      body: FutureBuilder<PostulantesNuevos>(
        future: _futuro,
        builder: (context, snapshot) {
          if (snapshot.hasData) return RefreshIndicator(onRefresh: _recargar, child: _contenido(snapshot.data!));
          if (snapshot.connectionState == ConnectionState.waiting) return const VistaCargando();
          return VistaMensaje.error(snapshot.error, onReintentar: _recargar);
        },
      ),
    );
  }

  Widget _contenido(PostulantesNuevos datos) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
      children: [
        _Resumen(datos),
        const SizedBox(height: 16),
        if (datos.postulantes.isEmpty)
          const Padding(
            padding: EdgeInsets.only(top: 32),
            child: VistaMensaje(
              icono: Icons.inbox_outlined,
              titulo: 'Estás al día',
              mensaje: 'Cuando alguien se postule a una de tus vacantes, va a aparecer acá.',
            ),
          )
        else ...[
          for (final p in datos.postulantes) ...[
            _TarjetaPostulante(postulante: p, onTap: () => _verFicha(p)),
            const SizedBox(height: 10),
          ],
          if (datos.total > datos.postulantes.length)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                'Se muestran los ${datos.postulantes.length} más recientes de ${datos.total}. '
                'El resto está en el panel web.',
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.textoSuave, fontSize: 13),
              ),
            ),
        ],
      ],
    );
  }
}

class _Resumen extends StatelessWidget {
  final PostulantesNuevos datos;
  const _Resumen(this.datos);

  @override
  Widget build(BuildContext context) {
    final total = datos.total;
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppColors.primario,
        borderRadius: BorderRadius.circular(AppTheme.radio),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  datos.empresaNombre,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: Color(0xFFC7D2FE), fontSize: 13, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 4),
                Text(
                  switch (total) {
                    0 => 'Sin postulantes por revisar',
                    1 => '1 postulante nuevo',
                    _ => '$total postulantes nuevos',
                  },
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(color: Colors.white),
                ),
                const SizedBox(height: 4),
                Text(
                  total == 0
                      ? 'Revisaste todas las postulaciones.'
                      : 'Todavía nadie los revisó. Escribiles desde acá o avanzalos en el panel web.',
                  style: const TextStyle(color: Color(0xFFC7D2FE), fontSize: 13, height: 1.35),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.12), shape: BoxShape.circle),
            child: const Icon(Icons.person_search_rounded, color: Colors.white, size: 28),
          ),
        ],
      ),
    );
  }
}

class _TarjetaPostulante extends StatelessWidget {
  final PostulanteNuevo postulante;
  final VoidCallback onTap;
  const _TarjetaPostulante({required this.postulante, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final p = postulante;
    final perfil = [?p.carrera, ?p.universidad];

    return Card(
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AvatarPersona(p.nombre),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            p.nombre,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15.5),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          capitalizar(haceCuanto(p.fecha)),
                          style: const TextStyle(color: AppColors.textoTenue, fontSize: 12),
                        ),
                      ],
                    ),
                    if (perfil.isNotEmpty)
                      Text(
                        perfil.join(' · '),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: AppColors.textoSuave, fontSize: 13),
                      ),
                    const SizedBox(height: 8),
                    DatoConIcono(Icons.work_outline_rounded, p.vacanteTitulo),
                    if (p.afinidad != null) ...[
                      const SizedBox(height: 8),
                      Insignia(
                        '${p.afinidad}% de afinidad',
                        colores: coloresDeAfinidad(p.afinidad!),
                        icono: Icons.auto_awesome_outlined,
                      ),
                    ],
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

/// Datos del postulante y formas de contactarlo. Devuelve true si eligió escribirle.
class _FichaPostulante extends StatelessWidget {
  final PostulanteNuevo p;
  const _FichaPostulante(this.p);

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                AvatarPersona(p.nombre, tamano: 56),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(p.nombre, style: Theme.of(context).textTheme.titleLarge),
                      if (p.titular != null)
                        Text(p.titular!, style: const TextStyle(color: AppColors.textoSuave)),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
            _Dato(Icons.work_outline_rounded, 'Se postuló a ${p.vacanteTitulo} ${haceCuanto(p.fecha)}'),
            if (p.carrera != null) _Dato(Icons.school_outlined, p.carrera!),
            if (p.universidad != null) _Dato(Icons.account_balance_outlined, p.universidad!),
            if (p.ciudad != null) _Dato(Icons.location_on_outlined, p.ciudad!),
            if (p.afinidad != null) ...[
              const SizedBox(height: 6),
              Align(
                alignment: Alignment.centerLeft,
                child: Insignia(
                  '${p.afinidad}% de afinidad con la vacante',
                  colores: coloresDeAfinidad(p.afinidad!),
                  icono: Icons.auto_awesome_outlined,
                ),
              ),
            ],
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: () => Navigator.of(context).pop(true),
              icon: const Icon(Icons.chat_bubble_outline_rounded),
              label: const Text('Enviar mensaje'),
            ),
            if (p.telefono != null || p.correo != null) ...[
              const SizedBox(height: 10),
              Row(
                children: [
                  if (p.telefono != null)
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () => llamar(context, p.telefono!),
                        icon: const Icon(Icons.call_outlined),
                        label: const Text('Llamar'),
                      ),
                    ),
                  if (p.telefono != null && p.correo != null) const SizedBox(width: 10),
                  if (p.correo != null)
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () => escribirCorreo(context, p.correo!),
                        icon: const Icon(Icons.mail_outline_rounded),
                        label: const Text('Correo'),
                      ),
                    ),
                ],
              ),
            ],
            const SizedBox(height: 14),
            const Text(
              'Para ver su CV completo, avanzarlo o descartarlo, usá el proceso de selección en el panel web.',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textoSuave, fontSize: 13),
            ),
          ],
        ),
      ),
    );
  }
}

class _Dato extends StatelessWidget {
  final IconData icono;
  final String texto;
  const _Dato(this.icono, this.texto);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icono, size: 18, color: AppColors.textoSuave),
          const SizedBox(width: 10),
          Expanded(child: Text(texto)),
        ],
      ),
    );
  }
}
