import hashlib
import hmac
import secrets
from typing import Dict


def hash_password(password: str, salt: str | None = None) -> str:
    used_salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), used_salt.encode("utf-8"), 100_000)
    return f"{used_salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, expected_hex = stored_hash.split("$", 1)
    except ValueError:
        return False
    candidate = hash_password(password, salt).split("$", 1)[1]
    return hmac.compare_digest(candidate, expected_hex)


class SessionStore:
    """Armazena tokens de sessão em memória (suficiente para v1 local)."""

    def __init__(self) -> None:
        self._tokens: Dict[str, str] = {}

    def create_session(self, username: str) -> str:
        token = secrets.token_urlsafe(24)
        self._tokens[token] = username
        return token

    def get_user(self, token: str | None) -> str | None:
        if not token:
            return None
        return self._tokens.get(token)

    def revoke(self, token: str | None) -> None:
        if token and token in self._tokens:
            del self._tokens[token]