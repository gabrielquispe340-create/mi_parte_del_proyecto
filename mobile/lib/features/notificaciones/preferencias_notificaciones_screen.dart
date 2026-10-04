import 'package:flutter/material.dart';

import '../../core/models/notificacion.dart';
import '../../core/services/notificacion_service.dart';

class PreferenciasNotificacionesScreen extends StatefulWidget {
  final String accessToken;

  const PreferenciasNotificacionesScreen({super.key, required this.accessToken});

  @override
  State<PreferenciasNotificacionesScreen> createState() => _PreferenciasNotificacionesScreenState();
}

class _PreferenciasNotificacionesScreenState extends State<PreferenciasNotificacionesScreen> {
  final _servicio = NotificacionService();
  bool _cargando = true;
  bool _guardando = false;
  late PreferenciasNotificacion _prefs;

  @override
  void initState() {
    super.initState();
    _cargar();
  }

  Future<void> _cargar() async {
    setState(() => _cargando = true);
    final p = await _servicio.obtenerPreferencias(widget.accessToken);
    if (!mounted) return;
    setState(() {
      _prefs = p;
      _cargando = false;
    });
  }

  Future<void> _guardar() async {
    setState(() => _guardando = true);
    final p = await _servicio.actualizarPreferencias(widget.accessToken, _prefs);
    if (!mounted) return;
    setState(() {
      _prefs = p;
      _guardando = false;
    });
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Preferencias de notificación guardadas'),
        backgroundColor: Colors.green,
      ),
    );
  }

  Future<void> _probarPushFCM() async {
    final ok = await _servicio.probarPushFCM(
      widget.accessToken,
      title: '🔔 Push Firebase FCM Móvil',
      body: '¡Excelente! La notificación Push móvil a través de Firebase está activa y funcionando.',
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(ok ? 'Push de prueba emitido exitosamente' : 'Push emitido al servidor'),
        backgroundColor: Colors.indigo,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Preferencias de Alertas'),
        actions: [
          if (!_cargando)
            IconButton(
              icon: _guardando
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.check),
              tooltip: 'Guardar cambios',
              onPressed: _guardando ? null : _guardar,
            ),
        ],
      ),
      body: _cargando
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _buildSeccionHeader('Canales de Envío'),
                Card(
                  elevation: 1,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  child: Column(
                    children: [
                      SwitchListTile(
                        secondary: const Icon(Icons.notifications_active, color: Colors.indigo),
                        title: const Text('Notificaciones Push Móvil (FCM)'),
                        subtitle: const Text('Alertas instantáneas emergentes en este dispositivo móvil'),
                        value: _prefs.pushEnabled,
                        onChanged: (val) => setState(() => _prefs = _prefs.copyWith(pushEnabled: val)),
                      ),
                      if (_prefs.pushEnabled)
                        Padding(
                          padding: const EdgeInsets.only(left: 16, right: 16, bottom: 12),
                          child: Align(
                            alignment: Alignment.centerLeft,
                            child: OutlinedButton.icon(
                              icon: const Icon(Icons.send_outlined, size: 16),
                              label: const Text('Probar Push Firebase Ahora', style: TextStyle(fontSize: 12)),
                              style: OutlinedButton.styleFrom(
                                visualDensity: VisualDensity.compact,
                                foregroundColor: Colors.indigo,
                              ),
                              onPressed: _probarPushFCM,
                            ),
                          ),
                        ),
                      const Divider(height: 1),
                      SwitchListTile(
                        secondary: const Icon(Icons.mark_chat_unread_outlined, color: Colors.blue),
                        title: const Text('Alertas en la App (In-App)'),
                        subtitle: const Text('Icono de campana y avisos dentro de EGRESA'),
                        value: _prefs.inAppEnabled,
                        onChanged: (val) => setState(() => _prefs = _prefs.copyWith(inAppEnabled: val)),
                      ),
                      const Divider(height: 1),
                      SwitchListTile(
                        secondary: const Icon(Icons.email_outlined, color: Colors.orange),
                        title: const Text('Correo Electrónico'),
                        subtitle: const Text('Resumen por email de eventos críticos'),
                        value: _prefs.emailEnabled,
                        onChanged: (val) => setState(() => _prefs = _prefs.copyWith(emailEnabled: val)),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                _buildSeccionHeader('Tipos de Eventos'),
                Card(
                  elevation: 1,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  child: Column(
                    children: [
                      SwitchListTile(
                        secondary: const Icon(Icons.trending_up, color: Colors.teal),
                        title: const Text('Avances de Postulaciones'),
                        subtitle: const Text('Cambios de etapa, preselección o estado de postulaciones'),
                        value: _prefs.notifyStageChanges,
                        onChanged: (val) => setState(() => _prefs = _prefs.copyWith(notifyStageChanges: val)),
                      ),
                      const Divider(height: 1),
                      SwitchListTile(
                        secondary: const Icon(Icons.auto_awesome, color: Colors.amber),
                        title: const Text('Vacantes Afines'),
                        subtitle: const Text('Nuevas ofertas laborales recomendadas para tu perfil'),
                        value: _prefs.notifyJobMatches,
                        onChanged: (val) => setState(() => _prefs = _prefs.copyWith(notifyJobMatches: val)),
                      ),
                      const Divider(height: 1),
                      SwitchListTile(
                        secondary: const Icon(Icons.event_available, color: Colors.purple),
                        title: const Text('Entrevistas y Citas'),
                        subtitle: const Text('Agendamiento y confirmaciones de entrevistas de trabajo'),
                        value: _prefs.notifyInterviewEvents,
                        onChanged: (val) => setState(() => _prefs = _prefs.copyWith(notifyInterviewEvents: val)),
                      ),
                      const Divider(height: 1),
                      SwitchListTile(
                        secondary: const Icon(Icons.chat_bubble_outline, color: Colors.cyan),
                        title: const Text('Mensajes de Empresas'),
                        subtitle: const Text('Avisos ante comunicaciones directas de reclutadores'),
                        value: _prefs.notifyMessages,
                        onChanged: (val) => setState(() => _prefs = _prefs.copyWith(notifyMessages: val)),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 32),
                ElevatedButton.icon(
                  icon: const Icon(Icons.save),
                  label: Text(_guardando ? 'Guardando...' : 'Guardar Preferencias'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.indigo,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  onPressed: _guardando ? null : _guardar,
                ),
              ],
            ),
    );
  }

  Widget _buildSeccionHeader(String titulo) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 8),
      child: Text(
        titulo,
        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Colors.grey),
      ),
    );
  }
}
