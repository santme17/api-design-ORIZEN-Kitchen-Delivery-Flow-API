# app/core/security.py
"""Seguridad: hash de contraseñas (PBKDF2-SHA256) y tokens JWT.

Formato del hash guardado:
    pbkdf2_sha256$<iteraciones>$<salt_hex>$<hash_hex>
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt  # paquete PyJWT

from app.core.config import settings

_ALGORITMO = "pbkdf2_sha256"
_ITERACIONES = 390_000


# ==========================================
# Contraseñas
# ==========================================


def hash_password(password: str) -> str:
    """Devuelve el hash con salt aleatorio. Nunca se guarda la contraseña en claro."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERACIONES)
    return f"{_ALGORITMO}${_ITERACIONES}${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Compara la contraseña con el hash guardado (comparación en tiempo constante)."""
    try:
        algoritmo, iteraciones, salt_hex, digest_hex = password_hash.split("$")
    except ValueError:
        return False
    if algoritmo != _ALGORITMO:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iteraciones)
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


# ==========================================
# JWT (tokens de acceso)
# ==========================================


def create_access_token(usuario_id: int, rol: str) -> str:
    """Firma un token con el id del usuario (sub), su rol y la fecha de vencimiento."""
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario_id),
        "rol": rol,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Verifica firma y vencimiento. Lanza jwt.InvalidTokenError si el token no sirve."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
