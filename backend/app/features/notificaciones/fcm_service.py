"""Servicio de Notificaciones Push con Firebase Cloud Messaging (FCM) — HU-21.

Gestiona el registro de tokens de dispositivos (Web, Android, iOS) y el envío
de mensajes Push utilizando Firebase Admin SDK o HTTP v1 con fallback seguro.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.notificacion import UserDeviceToken

logger = logging.getLogger(__name__)

# Variable global del estado de inicialización de Firebase
_firebase_initialized = False


def inicializar_firebase() -> bool:
    """Inicializa Firebase Admin SDK si se configuran credenciales válidas."""
    global _firebase_initialized
    if _firebase_initialized:
        return True

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        cred_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

        # Rutas de autodescubrimiento si no se especificó variable de entorno
        rutas_posibles = [
            cred_path,
            "serviceAccountKey.json",
            "/app/serviceAccountKey.json",
            os.path.join(os.getcwd(), "serviceAccountKey.json"),
            os.path.join(os.getcwd(), "backend", "serviceAccountKey.json"),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "serviceAccountKey.json")),
        ]

        ruta_encontrada = next((p for p in rutas_posibles if p and os.path.exists(p)), None)

        if ruta_encontrada:
            cred = credentials.Certificate(ruta_encontrada)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("Firebase Admin inicializado exitosamente desde: %s", ruta_encontrada)
            return True
        elif cred_json:
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("Firebase Admin inicializado desde variable de entorno JSON")
            return True
        else:
            # Sin credenciales no hay push; las notificaciones dentro de la app siguen funcionando.
            logger.debug("Firebase Admin sin credenciales: no se envían notificaciones push.")
            return False
    except Exception as e:
        logger.warning("No se pudo inicializar Firebase Admin SDK: %s", e)
        return False


def registrar_token_dispositivo(
    db: Session,
    user_id: uuid.UUID,
    fcm_token: str,
    device_type: str = "web",
    device_name: str | None = None,
) -> UserDeviceToken:
    """Registra o actualiza el FCM token de un dispositivo para el usuario."""
    registro = db.query(UserDeviceToken).filter(UserDeviceToken.fcm_token == fcm_token).first()

    if registro:
        registro.user_id = user_id
        registro.device_type = device_type
        registro.device_name = device_name
        registro.is_active = True
        registro.updated_at = datetime.now(timezone.utc)
    else:
        registro = UserDeviceToken(
            user_id=user_id,
            fcm_token=fcm_token,
            device_type=device_type,
            device_name=device_name,
            is_active=True,
        )
        db.add(registro)

    db.commit()
    db.refresh(registro)
    return registro


def desactivar_token_dispositivo(db: Session, fcm_token: str, user_id: uuid.UUID) -> bool:
    """Desactiva un FCM token del usuario al cerrar sesión o desinstalar."""
    registro = (
        db.query(UserDeviceToken)
        .filter(UserDeviceToken.fcm_token == fcm_token, UserDeviceToken.user_id == user_id)
        .first()
    )
    if registro:
        registro.is_active = False
        registro.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True
    return False


def obtener_tokens_activos(db: Session, user_id: uuid.UUID) -> list[str]:
    """Obtiene todos los FCM tokens activos de un usuario."""
    tokens = (
        db.query(UserDeviceToken.fcm_token)
        .filter(UserDeviceToken.user_id == user_id, UserDeviceToken.is_active.is_(True))
        .all()
    )
    return [t[0] for t in tokens]


def enviar_push_fcm(
    db: Session,
    user_id: uuid.UUID,
    title: str,
    body: str | None,
    link: str | None = None,
    datos_extra: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Envía un mensaje Push vía Firebase Cloud Messaging a todos los dispositivos del usuario.

    No hace commit: los tokens que Firebase rechaza quedan desactivados en la
    transacción de quien llama.
    """
    if not inicializar_firebase():
        return {"enviados": 0, "fallidos": 0, "mensaje": "Firebase no está configurado en el servidor."}

    tokens = obtener_tokens_activos(db, user_id)
    if not tokens:
        return {"enviados": 0, "fallidos": 0, "mensaje": "Usuario no tiene dispositivos FCM registrados"}

    data_payload = {
        "title": title,
        "body": body or "",
        "link": link or "/notificaciones",
        "click_action": link or "/notificaciones",
    }
    if datos_extra:
        data_payload.update(datos_extra)

    from firebase_admin import messaging

    mensaje_multicast = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body or ""),
        data=data_payload,
        tokens=tokens,
        webpush=messaging.WebpushConfig(
            notification=messaging.WebpushNotification(title=title, body=body or "", icon="/favicon.ico"),
            fcm_options=messaging.WebpushFCMOptions(link=link or "/notificaciones"),
        ),
    )
    respuesta = messaging.send_each_for_multicast(mensaje_multicast)

    # Tokens inválidos o de apps desinstaladas: no se les vuelve a enviar.
    invalidos = [tokens[i] for i, r in enumerate(respuesta.responses) if not r.success]
    if invalidos:
        db.query(UserDeviceToken).filter(UserDeviceToken.fcm_token.in_(invalidos)).update(
            {"is_active": False, "updated_at": datetime.now(timezone.utc)}, synchronize_session=False
        )

    return {
        "enviados": respuesta.success_count,
        "fallidos": respuesta.failure_count,
        "tokens_destino": len(tokens),
        "titulo": title,
    }


def enviar_push_seguro(
    db: Session, user_id: uuid.UUID, title: str, body: str | None, link: str | None = None
) -> None:
    """Push que acompaña a una notificación: si falla, el flujo que notifica sigue igual.

    Sin credenciales de Firebase no consulta nada. Las consultas van en un
    savepoint para no abortar la transacción de quien llama si, por ejemplo,
    falta la tabla user_device_token.
    """
    if not inicializar_firebase():
        return
    try:
        with db.begin_nested():
            enviar_push_fcm(db, user_id, title, body, link)
    except Exception:
        logger.warning("No se pudo enviar el push FCM al usuario %s", user_id, exc_info=True)
