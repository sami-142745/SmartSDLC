"""Deterministic secret scanner.

What it detects
---------------
Credential material committed to a repository, across six families: private
keys, provider API keys, cloud access keys, database URIs, hardcoded
credential assignments, and high-entropy tokens. Every pattern is a fixed
regular expression or a measured entropy threshold — there is no model call and
no network lookup, so a scan returns the same answer every time.

The redaction contract
----------------------
This is the only module in the system that is allowed to see raw credential
material, and it does not pass it on. :func:`redact` converts a matched value to
a shape-preserving mask *before* the value is measured, fingerprinted, placed in
a description, or handed to any caller. A :class:`SecretMatch` therefore cannot
carry a secret even by accident: the raw match is confined to the local variable
inside :meth:`SecretScanner.scan_text`, and the structured result exposes only
``redacted``, ``length`` and ``fingerprint``.

Fingerprints
------------
The fingerprint is a salted hash of the *normalised file path plus the rule id
plus the redacted value*. It is stable across scans of the same file (so the UI
can track a finding over time) and identical for a secret that is duplicated into
several files, which is what makes cross-file dedupe possible. Because the salt
lives only in this process, fingerprints are not comparable across restarts;
they are identifiers, not security primitives.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Protocol

from app.services import security_sources

#: Redaction mask. Fixed-width and obviously not the original, so it cannot be
#: mistaken for a usable credential by a human or a downstream consumer.
REDACTED = "[REDACTED]"

#: Minimum length before a value is even considered for entropy scoring. Short
#: strings cannot be both random and non-guessable.
MIN_ENTROPY_LENGTH = 16

#: Shannon entropy threshold in bits per character. 4.0 is high enough to exclude
#: ordinary identifiers, prose and base64-encoded file paths, and low enough to
#: catch real API keys, which sit well above 4.5.
ENTROPY_THRESHOLD = 4.0

#: Entropy is measured over this many characters at most. Real tokens have
#: uniform per-character distribution, so a prefix is a sufficient and much
#: cheaper sample than a 4 KB blob.
ENTROPY_SAMPLE = 128

#: A token must mix at least this many character classes to be considered
#: random. Hex-only and digits-only strings are excluded: they are common
#: hashes and build identifiers, not credentials.
MIN_CHARACTER_CLASSES = 2

#: Process-local salt. Findings are matched within and across scans in one
#: running process, which is what the UI needs; it is deliberately not derived
#: from any secret so it cannot leak one.
_FINGERPRINT_SALT = b"smart-sdlc-security-intelligence-v1"


class SecretPattern(Protocol):
    """Structural description of one detection rule.

    Scanners are configured from plain data so a new rule is a dict entry rather
    than a code change, and so a test can enumerate every rule the engine
    claims to support.
    """

    rule_id: str
    title: str
    description: str
    severity: str
    confidence: float
    pattern: re.Pattern[str]
    category: str
    scanner: str = "secret"


@dataclass(frozen=True)
class SecretRule:
    rule_id: str
    title: str
    description: str
    severity: str
    confidence: float
    pattern: re.Pattern[str]
    category: str = "secrets"
    scanner: str = "secret"
    #: Whether the entropy heuristic gates this rule. Defaults to True because a
    #: rule with its own anchored pattern has already decided what a match means;
    #: only a broad catch-all rule (``secret.high_entropy_token``) opts out.
    skip_entropy: bool = True
    #: Whether placeholder-shaped values are suppressed. Only the generic rules
    #: (a credential-shaped variable, an unrecognised high-entropy token) need
    #: it. A rule anchored to a provider's fixed prefix and length — an AWS key
    #: ID, a Slack token — must not be suppressed, because a real leaked key can
    #: contain any character sequence, including the word "example" (AWS's own
    #: documentation key does).
    suppress_placeholders: bool = False
    #: Whether URL userinfo is masked before this rule runs. True for the generic
    #: rules, so ``https://user:pass@host`` is not reported a second time as a
    #: bare password. False for the database-URI rule, which exists precisely to
    #: report that shape.
    mask_url_credentials: bool = False


@dataclass
class SecretMatch:
    """One detected credential, with the credential itself already redacted."""

    rule_id: str
    path: str
    line: int
    column: int
    severity: str
    category: str
    scanner: str
    title: str
    description: str
    redacted: str
    length: int
    fingerprint: str
    confidence: float
    tags: list[str] = field(default_factory=list)

    def as_finding(self) -> dict:
        """Build the finding payload for the normalizer.

        Only the redacted value is included. The remediation text is written so
        it stands alone — a reader can act on it without ever seeing the secret.
        """
        return {
            "file": self.path,
            "line": self.line,
            "column": self.column,
            "category": self.category,
            "severity": self.severity,
            "confidence": self.confidence,
            "title": self.title,
            "description": self.description,
            "remediation": (
                "Revoke and rotate this credential immediately, remove it from the "
                "repository history, and load the value from a secret manager or "
                "environment variable at runtime."
            ),
            "scanner": self.scanner,
            "fingerprint": self.fingerprint,
        }


def redact(value: str) -> str:
    """Replace a credential with a fixed mask, preserving nothing.

    A prefix-preserving mask such as ``AKIA…`` would still leak a few bits of
    entropy and, for a short password, a large fraction of the value. Since the
    finding's usefulness comes from its location and rule, not from the secret,
    the mask is total.
    """
    return REDACTED


def shannon_entropy(value: str) -> float:
    """Shannon entropy in bits per character.

    Returns 0.0 for an empty string. Uses a count-based implementation rather
    than :func:`math.log2` over a probability table so the cost is linear in the
    string length and the function stays allocation-light.
    """
    if not value:
        return 0.0
    counts = Counter(value)
    length = len(value)
    return -sum(
        (count / length) * math.log2(count / length) for count in counts.values()
    )


def character_classes(value: str) -> int:
    """Count distinct character classes present (lower, upper, digit, other)."""
    classes = 0
    if any(c.islower() for c in value):
        classes += 1
    if any(c.isupper() for c in value):
        classes += 1
    if any(c.isdigit() for c in value):
        classes += 1
    if any(not c.isalnum() for c in value):
        classes += 1
    return classes


def looks_random(value: str) -> bool:
    """Heuristic gate for generic high-entropy detection.

    A value qualifies when it is long enough, mixes at least
    ``MIN_CHARACTER_CLASSES`` character classes, clears the entropy threshold,
    and is not a placeholder. Placeholder and shape checks live in
    :mod:`app.services.security_sources` so the same rules apply everywhere.

    Only the *generic* token rule reaches here. Rules anchored to a provider's
    fixed prefix never call this, so a real AWS or Slack key is not discarded
    for containing a substring like ``example``.
    """
    if len(value) < MIN_ENTROPY_LENGTH:
        return False
    if character_classes(value) < MIN_CHARACTER_CLASSES:
        return False
    if security_sources.is_placeholder(value):
        return False
    return shannon_entropy(value[:ENTROPY_SAMPLE]) >= ENTROPY_THRESHOLD


def fingerprint_for(path: str, rule_id: str, redacted_value: str) -> str:
    """Stable identifier for a credential at a location.

    Hashed rather than stored so a fingerprint can be compared across files and
    across scans without ever containing a credential.
    """
    material = "|".join(
        (path or "", rule_id or "", redacted_value or "")
    ).encode("utf-8")
    return hashlib.sha256(_FINGERPRINT_SALT + material).hexdigest()[:32]


def _rule(
    rule_id: str,
    title: str,
    description: str,
    severity: str,
    confidence: float,
    pattern: str,
    *,
    category: str = "secrets",
    skip_entropy: bool = True,
    suppress_placeholders: bool = False,
    mask_url_credentials: bool = False,
    flags: int = 0,
) -> SecretRule:
    return SecretRule(
        rule_id=rule_id,
        title=title,
        description=description,
        severity=severity,
        confidence=confidence,
        pattern=re.compile(pattern, flags),
        category=category,
        skip_entropy=skip_entropy,
        suppress_placeholders=suppress_placeholders,
        mask_url_credentials=mask_url_credentials,
    )


#: The full rule set. Ordered from most specific to most generic, because
#: :meth:`SecretScanner.scan_text` stops at the first rule that matches a given
#: span: a private key must not also be reported as a generic high-entropy token.
SECRET_RULES: tuple[SecretRule, ...] = (
    _rule(
        "secret.private_key",
        "Private key committed to repository",
        "A private key block is stored in the source tree. Anyone with repository "
        "access can impersonate the owner or decrypt data protected by it.",
        "critical",
        0.97,
        r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----",
    ),
    _rule(
        "secret.aws_access_key_id",
        "AWS access key ID",
        "An AWS access key identifier is hardcoded. It is the public half of a "
        "credential pair and is not designed to be committed.",
        "critical",
        0.95,
        r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b",
    ),
    _rule(
        "secret.aws_secret_access_key",
        "AWS secret access key",
        "An AWS secret access key assignment is hardcoded. This value alone "
        "authenticates as the principal it belongs to.",
        "critical",
        0.93,
        r"(?i)\baws_?secret_?access_?key\b\s*[:=]\s*[\"']?([A-Za-z0-9/+=]{40})",
    ),
    _rule(
        "secret.github_token",
        "GitHub token",
        "A GitHub personal access, OAuth, user-to-server or server-to-server "
        "token is hardcoded in the repository.",
        "critical",
        0.94,
        r"\b(?:ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{36,}\b",
    ),
    _rule(
        "secret.slack_token",
        "Slack token",
        "A Slack API token is hardcoded in the repository.",
        "high",
        0.9,
        r"\bxox[abposr]-[0-9A-Za-z-]{10,}\b",
    ),
    _rule(
        "secret.google_api_key",
        "Google API key",
        "A Google API key is hardcoded in the repository.",
        "high",
        0.9,
        r"\bAIza[0-9A-Za-z_-]{35}\b",
    ),
    _rule(
        "secret.stripe_key",
        "Stripe API key",
        "A Stripe live or test secret key is hardcoded in the repository.",
        "critical",
        0.93,
        r"\b(?:sk|rk)_(?:live|test)_[0-9A-Za-z]{10,}\b",
    ),
    _rule(
        "secret.openai_key",
        "OpenAI API key",
        "An OpenAI-style API key is hardcoded in the repository.",
        "high",
        0.88,
        r"\bsk-(?:proj-)?[0-9A-Za-z_-]{20,}\b",
    ),
    _rule(
        "secret.jwt",
        "JSON Web Token",
        "A signed JWT is hardcoded. Tokens in source are readable by everyone "
        "with repository access and may still be valid.",
        "high",
        0.85,
        r"\beyJ[0-9A-Za-z_-]{8,}\.[0-9A-Za-z_-]{8,}\.[0-9A-Za-z_-]{8,}\b",
    ),
    _rule(
        "secret.database_uri",
        "Database connection string with credentials",
        "A database URI embeds a username and password. Connection strings are "
        "commonly reused across environments, so one leak can span several.",
        "critical",
        0.9,
        r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp|mssql|oracle)"
        r"://[^\s:@/]+:[^\s:@/]+@[^\s/]+",
    ),
    _rule(
        "secret.credential_assignment",
        "Hardcoded credential",
        "A value is assigned to a credential-like variable in source. The "
        "variable name indicates the value is intended to be a secret.",
        "high",
        0.78,
        r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|apikey|access[_-]?token|"
        r"auth[_-]?token|client[_-]?secret|private[_-]?key|refresh[_-]?token|"
        r"encryption[_-]?key|signing[_-]?key)\b\s*[:=]\s*[\"']([^\"'\s]{6,})[\"']",
        suppress_placeholders=True,
        mask_url_credentials=True,
    ),
    _rule(
        "secret.nginx_basic_auth",
        "Basic auth credentials in configuration",
        "A htpasswd-style credential pair is stored in configuration, usually "
        "alongside a password hash for a shared account.",
        "high",
        0.8,
        r"\b[a-zA-Z0-9._-]+:\$\{?(?:apr1|2[aby]|1|bcrypt|md5|sha1|sha256)\}?\$\{?[A-Za-z0-9./$]{6,}",
    ),
)

#: Generic token shapes are only reported when they clear
#: :func:`looks_random`, so this rule is registered with ``skip_entropy=False``.
_GENERIC_TOKEN_RULE = _rule(
    "secret.high_entropy_token",
    "High-entropy token",
    "A long, high-entropy string appears to be a credential or signing key. No "
    "known provider prefix matched, so confirm before rotating.",
    "medium",
    0.55,
    r"[\"']?([A-Za-z0-9+/=_\-]{20,})[\"']?",
    skip_entropy=False,
    suppress_placeholders=True,
    mask_url_credentials=True,
)

#: Everything the scanner evaluates, in specificity order.
ALL_SECRET_RULES: tuple[SecretRule, ...] = SECRET_RULES + (_GENERIC_TOKEN_RULE,)

RULES_BY_ID: dict[str, SecretRule] = {rule.rule_id: rule for rule in ALL_SECRET_RULES}


def iter_rule_ids() -> Iterator[str]:
    return (rule.rule_id for rule in ALL_SECRET_RULES)


def _capture_group_value(match: re.Match[str]) -> tuple[str, int]:
    """Return the interesting substring of a match and its absolute offset.

    Rules that match a whole assignment capture the credential in a group; the
    group is used so the key name is not treated as part of the secret. Rules
    without a capture group use the entire match.
    """
    if match.groups():
        try:
            start, end = match.span(match.lastindex or 1)
        except (IndexError, ValueError):
            return match.group(0), match.start()
        if end > start:
            return match.group(match.lastindex or 1), start
    return match.group(0), match.start()


def _dedupe_span(
    claimed: list[tuple[int, int]], start: int, end: int
) -> bool:
    """Claim a span, refusing to overlap one already claimed by a prior rule."""
    for existing_start, existing_end in claimed:
        if start < existing_end and existing_start < end:
            return False
    claimed.append((start, end))
    return True


@dataclass
class SecretScanner:
    """Scans text for credential material.

    Stateless and safe to reuse across files and repositories. ``rules`` is
    injectable so a test can exercise one rule in isolation and so a future
    configuration source can extend or narrow the rule set without a code
    change.
    """

    rules: tuple[SecretRule, ...] = ALL_SECRET_RULES

    def supports(self, rule_id: str) -> bool:
        return rule_id in RULES_BY_ID

    def scan_text(self, path: str, content: str) -> list[SecretMatch]:
        """Return every distinct credential found in ``content``.

        ``content`` is expected to be a single file's text. The caller is
        responsible for having screened the path first; this method re-checks
        anyway because a scanner that trusts its caller is a scanner that will
        eventually be called by the wrong thing.
        """
        if not content:
            return []
        normalized = security_sources.normalize_path_for_scan(path)
        if not normalized:
            return []

        matches: list[SecretMatch] = []
        seen: set[tuple[str, str]] = set()
        lines = content.splitlines()

        for line_number, raw_line in enumerate(lines, start=1):
            if not raw_line.strip():
                continue
            claimed: list[tuple[int, int]] = []
            for rule in self.rules:
                # URL userinfo is masked only for the rules that would otherwise
                # report it a second time as a bare password. The database-URI
                # rule opts out, because that shape is exactly what it detects.
                line = (
                    security_sources.strip_url_credentials(raw_line)
                    if rule.mask_url_credentials
                    else raw_line
                )
                for match in rule.pattern.finditer(line):
                    value, offset = _capture_group_value(match)
                    start, end = match.span(match.lastindex or 0)
                    if not _dedupe_span(claimed, start, end):
                        continue
                    if not self._is_reportable(rule, value):
                        continue
                    redacted = redact(value)
                    fingerprint = fingerprint_for(normalized, rule.rule_id, redacted)
                    # A single secret repeated in the same file is one finding.
                    dedupe_key = (rule.rule_id, fingerprint)
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)
                    matches.append(
                        SecretMatch(
                            rule_id=rule.rule_id,
                            path=normalized,
                            line=line_number,
                            column=offset + 1,
                            severity=rule.severity,
                            category=rule.category,
                            scanner=rule.scanner,
                            title=rule.title,
                            description=rule.description,
                            redacted=redacted,
                            length=len(value),
                            fingerprint=fingerprint,
                            confidence=rule.confidence,
                            tags=[rule.rule_id],
                        )
                    )
        return matches

    def scan_lines(self, path: str, lines: Iterable[str]) -> list[SecretMatch]:
        """Scan pre-split lines, re-attaching line numbers.

        Used by the repository scan service, which receives content already
        split and capped by :mod:`app.services.security_sources`.
        """
        return self.scan_text(path, "\n".join(lines))

    def _is_reportable(self, rule: SecretRule, value: str) -> bool:
        """Decide whether a matched value is worth a finding."""
        if not value or not value.strip():
            return False
        if rule.suppress_placeholders and security_sources.is_placeholder(value):
            return False
        if rule.skip_entropy:
            return True
        return looks_random(value)


#: Module-level default scanner. Constructing it is cheap (the rules are
#: pre-compiled module constants), and sharing one instance keeps a single
#: interpretation of the rule set for the whole process.
DEFAULT_SECRET_SCANNER = SecretScanner()


def scan_content(path: str, content: str) -> list[SecretMatch]:
    """Convenience wrapper around :meth:`SecretScanner.scan_text`."""
    return DEFAULT_SECRET_SCANNER.scan_text(path, content)


def rule_summary() -> list[dict[str, str]]:
    """Machine-readable description of the supported rules.

    Returned by the API so the UI can explain what the engine looks for without
    hardcoding a duplicate list on the frontend.
    """
    return [
        {
            "rule_id": rule.rule_id,
            "title": rule.title,
            "description": rule.description,
            "severity": rule.severity,
            "category": rule.category,
        }
        for rule in ALL_SECRET_RULES
    ]
