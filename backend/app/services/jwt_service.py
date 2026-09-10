import time
from typing import Any
import jwt

from app.services.config import settings


def create_access_token(payload: dict[str, Any]) -> str:
    now = int(time.time())
    exp = now + int(settings.JWT_EXPIRES_SECONDS)

    body = {
        **payload,
        "iat": now,
        "exp": exp,
    }

    return jwt.encode(body, settings.JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])

