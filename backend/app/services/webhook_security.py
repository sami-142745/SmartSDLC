import hashlib
import hmac


def verify_webhook_signature(payload: bytes, signature: str | None, secret: str) -> bool:
    if not signature or not secret:
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def payload_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()