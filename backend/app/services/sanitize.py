from __future__ import annotations

import re

REDACTED = "[REDACTED]"

_PRIVATE_KEY_BLOCK_RE = re.compile(
    r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----.*?"
    r"-----END (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----",
    re.DOTALL,
)

_TOKEN_RE = re.compile(
    r"\b(?:AKIA[0-9A-Z]{16}|gho_[0-9A-Za-z]{36}|ghp_[0-9A-Za-z]{36}|"
    r"ghu_[0-9A-Za-z]{36}|ghs_[0-9A-Za-z]{36}|xox[baprs]-[0-9A-Za-z-]{10,}|"
    r"sk-[0-9A-Za-z-]{20,}|AIza[0-9A-Za-z_-]{35}|ya29\.[0-9A-Za-z_-]+|"
    r"glpat-[0-9A-Za-z_-]{20,}|eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,})\b",
    re.IGNORECASE,
)

_CREDENTIAL_ASSIGNMENT_RE = re.compile(
    r"(\b(?:password|passwd|secret|token|api[_-]?key|apikey|client[_-]?secret|"
    r"access[_-]?key|private[_-]?key|refresh[_-]?token|bearer[_-]?token|"
    r"auth[_-]?token)\b\s*[:=]\s*)([\"'][^\"']{6,}[\"'])",
    re.IGNORECASE,
)


def redact_secrets(text: str) -> str:
    """Remove credentials from untrusted repository content before it is
    sent to the model. Never raises; pure string transformation."""
    if not text:
        return text
    out = _PRIVATE_KEY_BLOCK_RE.sub(REDACTED, text)
    out = _TOKEN_RE.sub(REDACTED, out)
    out = _CREDENTIAL_ASSIGNMENT_RE.sub(lambda m: m.group(1) + REDACTED, out)
    return out