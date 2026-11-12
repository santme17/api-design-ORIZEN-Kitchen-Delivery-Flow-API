# app/core/security.py
"""Hash de contraseñas con la librería estándar (PBKDF2-SHA256).

No necesita paquetes extra. El formato guardado es:
    pbkdf2_sha256$<iteraciones>$<salt_hex>$<hash_hex>
La parte de JWT se agrega aquí mismo cuando se implemente la autenticación.
"""
import hashlib
import hmac
import secrets

_ALGORITMO = "pbkdf2_sha256"
_ITERACIONES = 390_000


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
