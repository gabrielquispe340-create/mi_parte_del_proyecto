"""Acceso a Stripe Checkout para cobrar el plan anual de una universidad.

Se cobra en bolivianos (BOB) con un pago único por año. La confirmación no depende del
webhook: al volver de Stripe el frontend pide verificar la sesión, así funciona también
en local. Si STRIPE_WEBHOOK_SECRET está configurado, el webhook acredita el pago aunque
el usuario cierre la pestaña antes de volver.
"""

import logging
from decimal import Decimal

import stripe

from app.common.exceptions import AppException, BusinessException
from app.core.config import get_settings

logger = logging.getLogger(__name__)

MONEDA = "bob"


def centavos(monto_bs: Decimal) -> int:
    return int((monto_bs * 100).to_integral_value())


def _cliente() -> stripe.StripeClient:
    clave = get_settings().stripe_secret_key
    if not clave:
        raise BusinessException("El cobro con tarjeta no está configurado en el servidor.")
    return stripe.StripeClient(clave)


def crear_checkout(
    *,
    monto_bs: Decimal,
    producto: str,
    descripcion: str,
    correo: str,
    referencia: str,
    metadata: dict[str, str],
) -> stripe.checkout.Session:
    base = get_settings().frontend_url.rstrip("/")
    if not base:
        raise BusinessException("Falta configurar FRONTEND_URL para volver de Stripe.")
    try:
        return _cliente().v1.checkout.sessions.create(
            params={
                "mode": "payment",
                "locale": "es-419",
                "customer_email": correo,
                "client_reference_id": referencia,
                "line_items": [
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": MONEDA,
                            "unit_amount": centavos(monto_bs),
                            "product_data": {"name": producto, "description": descripcion},
                        },
                    }
                ],
                "metadata": metadata,
                "payment_intent_data": {"metadata": metadata, "description": producto},
                "success_url": f"{base}/admin/universidades?pago={{CHECKOUT_SESSION_ID}}",
                "cancel_url": f"{base}/admin/universidades?pago=cancelado",
            }
        )
    except stripe.StripeError as exc:
        logger.exception("Stripe rechazó la creación del checkout")
        raise BusinessException("No se pudo iniciar el pago con Stripe. Probá de nuevo en un momento.") from exc


def obtener_sesion(session_id: str) -> stripe.checkout.Session:
    try:
        return _cliente().v1.checkout.sessions.retrieve(session_id)
    except stripe.InvalidRequestError as exc:
        raise BusinessException("Stripe no reconoce ese pago.") from exc
    except stripe.StripeError as exc:
        logger.exception("No se pudo consultar la sesión de Stripe %s", session_id)
        raise BusinessException("No se pudo consultar el pago en Stripe. Probá de nuevo en un momento.") from exc


def leer_evento(payload: bytes, firma: str | None) -> stripe.Event:
    secreto = get_settings().stripe_webhook_secret
    if not secreto:
        raise BusinessException("El webhook de Stripe no está configurado.")
    try:
        return _cliente().construct_event(payload, firma or "", secreto)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise AppException("Firma de Stripe inválida.") from exc
