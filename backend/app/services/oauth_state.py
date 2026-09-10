import hashlib
import hmac
import secrets
import time

from app.services.config import settings


def create_state(secret: str, ttl_seconds: int | None = None, now: int | None = None) -> str:
    ttl = ttl_seconds if ttl_seconds is not None else settings.OAUTH_STATE_TTL_SECONDS
    now = now if now is not None else int(time.time())
    nonce = secrets.token_urlsafe(32)
    expires = now + ttl
    payload = f"{nonce}.{expires}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_state(state: str | None, secret: str, now: int | None = None) -> bool:
    if not state:
        return False
    parts = state.split(".")
    if len(parts) != 3:
        return False
    nonce, expires_str, signature = parts
    if not nonce or not expires_str:
        return False
    try:
        expires = int(expires_str)
    except ValueError:
        return False
    now = now if now is not None else int(time.time())
    if now > expires:
        return False
    expected = hmac.new(secret.encode(), f"{nonce}.{expires_str}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)