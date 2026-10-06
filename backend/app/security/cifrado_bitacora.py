"""Cifrado de la bitácora (requisito general 3: bitácora confidencial).

Cada entrada se cifra con la clave pública de la bitácora: X25519 con una clave efímera por
entrada, HKDF-SHA256 y AES-256-GCM. El servidor solo conoce la clave pública, así que puede
escribir entradas pero no leerlas. Para leerlas hay que ingresar la clave de desarrollador,
de la que se deriva la clave privada con scrypt. Ni el administrador de la base de datos ni
quien vea las variables del servidor puede leer la bitácora sin esa clave.
"""

import base64
import hmac
import json
import os
import secrets
from functools import lru_cache
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

VERSION = "v1"
_SAL = b"egresa/bitacora/clave-desarrollador/v1"
_INFO = b"egresa/bitacora/entrada/v1"
_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I: se dicta sin confusiones


class ClaveIncorrecta(Exception):
    """La clave de desarrollador no corresponde a la clave pública configurada."""


def generar_clave_desarrollador() -> str:
    """Clave nueva al azar (150 bits) con formato legible: EGRESA-XXXXX-XXXXX-…"""
    grupos = ("".join(secrets.choice(_ALFABETO) for _ in range(5)) for _ in range(6))
    return "EGRESA-" + "-".join(grupos)


def derivar_clave_privada(clave_desarrollador: str) -> X25519PrivateKey:
    # scrypt hace lento probar claves al azar (unos 100 ms y 32 MB por intento).
    semilla = Scrypt(salt=_SAL, length=32, n=2**15, r=8, p=1).derive(clave_desarrollador.strip().encode("utf-8"))
    return X25519PrivateKey.from_private_bytes(semilla)


def _bytes_publicos(clave: X25519PublicKey) -> bytes:
    return clave.public_bytes(Encoding.Raw, PublicFormat.Raw)


def clave_publica_de(clave_desarrollador: str) -> str:
    """La clave pública (base64) que va en BITACORA_CLAVE_PUBLICA."""
    return base64.b64encode(_bytes_publicos(derivar_clave_privada(clave_desarrollador).public_key())).decode()


@lru_cache(maxsize=4)
def _cargar_publica(texto: str) -> X25519PublicKey:
    crudo = base64.b64decode(texto.strip(), validate=True)
    if len(crudo) != 32:
        raise ValueError("BITACORA_CLAVE_PUBLICA no es una clave válida (deben ser 32 bytes en base64).")
    return X25519PublicKey.from_public_bytes(crudo)


def _clave_simetrica(compartido: bytes, efimera: bytes, publica: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_INFO + efimera + publica).derive(compartido)


def cifrar(datos: dict[str, Any], clave_publica: str) -> str:
    destino = _cargar_publica(clave_publica)
    efimera = X25519PrivateKey.generate()
    efimera_publica = _bytes_publicos(efimera.public_key())
    clave = _clave_simetrica(efimera.exchange(destino), efimera_publica, _bytes_publicos(destino))
    nonce = os.urandom(12)
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    cifrado = AESGCM(clave).encrypt(nonce, texto, VERSION.encode())
    return f"{VERSION}.{base64.b64encode(efimera_publica + nonce + cifrado).decode()}"


class Lector:
    """Descifra entradas con la clave privada derivada de la clave de desarrollador.

    Se crea por consulta y no se guarda: el servidor no conserva la clave privada.
    """

    def __init__(self, clave_desarrollador: str, clave_publica: str) -> None:
        privada = derivar_clave_privada(clave_desarrollador)
        esperada = _bytes_publicos(_cargar_publica(clave_publica))
        self._publica = _bytes_publicos(privada.public_key())
        if not hmac.compare_digest(self._publica, esperada):
            raise ClaveIncorrecta()
        self._privada = privada

    def descifrar(self, token: str) -> dict[str, Any]:
        version, _, cuerpo = token.partition(".")
        if version != VERSION:
            raise ValueError(f"Versión de cifrado desconocida: {version}")
        crudo = base64.b64decode(cuerpo)
        efimera_publica, nonce, cifrado = crudo[:32], crudo[32:44], crudo[44:]
        compartido = self._privada.exchange(X25519PublicKey.from_public_bytes(efimera_publica))
        clave = _clave_simetrica(compartido, efimera_publica, self._publica)
        return json.loads(AESGCM(clave).decrypt(nonce, cifrado, VERSION.encode()))
