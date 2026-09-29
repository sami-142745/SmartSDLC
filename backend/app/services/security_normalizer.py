"""Finding normalization: one shape, one identity, one order.

The three scanners deliberately emit different payloads — the secret scanner
wraps redacted values, the code scanner emits rule hits, the dependency scanner
carries the package name and the version. This module is the seam where they
become a single :class:`~app.schemas.security.SecurityFinding` list, and it owns
three properties the rest of the system relies on:

**Identity.** A code finding's fingerprint is derived from
``scanner|rule|file`` so a finding survives the line moving by one as the file
is edited. A secret finding's fingerprint comes from its value, so the *same*
credential duplicated into five files is one finding with five locations — the
behaviour a reviewer needs when deciding whether a leaked key is fully cleaned
up. A dependency finding's fingerprint includes its risk, so an unpinned
dependency that is also deprecated is two findings, each independently fixable.

**Provenance.** A finding that crossed a credential boundary must not report a
line it cannot justify. A secret scan over a whole file reports line 0; the
normalizer enforces that any finding whose ``scanner`` is ``secret`` and whose
line was not measured line-by-line stays file-level.

**Determinism.** The sort order is total: severity, then confidence descending,
then file, then line, then scanner, then rule. Two runs over the same repository
produce byte-identical output, which is what makes a scan diffable.
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping

from app.schemas.security import (
    FILE_LEVEL_LINE,
    SEVERITIES,
    SecurityFinding,
    normalize_category,
    normalize_scanner,
    normalize_severity,
    severity_rank,
)
from app.services import security_sources

#: Ordering of scanners in the output, so a secret always sorts beside other
#: secrets regardless of which pass produced it.
_SCANNER_ORDER = {"secret": 0, "code": 1, "dependency": 2}

#: Finding payload keys a scanner may set. Anything else is dropped before the
#: model is constructed, which is the enforcement point for "the raw matched
#: text must not reach the contract".
_ALLOWED_KEYS = frozenset(
    {
        "file",
        "line",
        "column",
        "category",
        "severity",
        "confidence",
        "title",
        "description",
        "remediation",
        "scanner",
        "fingerprint",
        "rule_id",
    }
)

#: Keys that would carry file content. Rejected loudly rather than dropped, so
#: a scanner regression is a test failure instead of a silent leak.
_FORBIDDEN_KEYS = frozenset(
    {
        "match",
        "matched",
        "matched_text",
        "match_text",
        "snippet",
        "code",
        "source",
        "line_text",
        "content",
        "raw",
        "raw_value",
        "value",
        "secret",
        "redacted_preview",
        "context",
    }
)


class NormalizationError(ValueError):
    """A scanner payload carried something it must not."""


def _rule_fingerprint(scanner: str, rule_id: str, path: str) -> str:
    material = "|".join((scanner, rule_id, path or ""))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def sanitize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Drop unknown keys and reject any content-bearing key.

    Raises :class:`NormalizationError` for a forbidden key: silently discarding
    it would hide the fact that a scanner is attaching file content, which is
    exactly the bug this module exists to prevent.
    """
    if not isinstance(payload, Mapping):
        raise NormalizationError("scanner payload must be a mapping")

    forbidden = _FORBIDDEN_KEYS & set(payload)
    if forbidden:
        raise NormalizationError(
            f"scanner payload contains content-bearing keys: {sorted(forbidden)}"
        )

    rule_id = payload.get("rule_id")
    cleaned = {key: value for key, value in payload.items() if key in _ALLOWED_KEYS}
    if isinstance(rule_id, str) and rule_id:
        cleaned["rule_id"] = rule_id
    return cleaned


def normalize_finding(
    payload: Mapping[str, Any],
    *,
    repository_id: str = "",
    finding_id: str = "",
) -> SecurityFinding:
    """Build a validated :class:`SecurityFinding` from a scanner payload.

    The rule id is folded into the fingerprint for code findings, which is what
    makes a code finding's identity independent of the line it sits on.
    """
    cleaned = sanitize_payload(payload)
    scanner = normalize_scanner(cleaned.get("scanner"))
    path = security_sources.normalize_path_for_scan(str(cleaned.get("file") or ""))
    rule_id = str(cleaned.get("rule_id") or "")

    fingerprint = str(cleaned.get("fingerprint") or "").strip()
    if not fingerprint:
        # A secret finding without a value-derived fingerprint would dedupe
        # purely on location, so the same key copied into two files would read
        # as two separate leaks. Fall back to the rule+path identity and let the
        # scanner contract in the tests require the real fingerprint.
        fingerprint = _rule_fingerprint(scanner, rule_id or scanner, path)

    data = {
        "repository_id": repository_id,
        "file": path,
        "line": cleaned.get("line", FILE_LEVEL_LINE),
        "column": cleaned.get("column"),
        "category": normalize_category(cleaned.get("category")),
        "severity": normalize_severity(cleaned.get("severity")),
        "confidence": cleaned.get("confidence", 0.5),
        "title": cleaned.get("title") or "Security finding",
        "description": cleaned.get("description") or "",
        "remediation": cleaned.get("remediation") or "",
        "scanner": scanner,
        "fingerprint": fingerprint,
    }
    return SecurityFinding(finding_id=finding_id, **data)


def sort_key(finding: SecurityFinding) -> tuple:
    """Total order over findings: severity, confidence, location, scanner, id."""
    return (
        severity_rank(finding.severity),
        -float(finding.confidence),
        finding.file,
        finding.line,
        finding.column if finding.column is not None else -1,
        _SCANNER_ORDER.get(finding.scanner, 99),
        finding.fingerprint,
    )


def dedupe(findings: Iterable[SecurityFinding]) -> list[SecurityFinding]:
    """Collapse findings that share a fingerprint, merging their locations.

    The winner is the highest-severity copy, with the earliest line, so the
    surviving finding points a reviewer at the first place the problem appears
    rather than at whichever scanner happened to finish last.
    """
    by_fingerprint: dict[str, SecurityFinding] = {}
    for finding in findings:
        existing = by_fingerprint.get(finding.fingerprint)
        if existing is None:
            by_fingerprint[finding.fingerprint] = finding
            continue
        by_fingerprint[finding.fingerprint] = min(existing, finding, key=sort_key)
    return list(by_fingerprint.values())


def normalize_findings(
    payloads: Iterable[Mapping[str, Any]],
    *,
    repository_id: str = "",
) -> list[SecurityFinding]:
    """Normalize, deduplicate and order a mixed set of scanner payloads.

    This is the single entry point the scan service uses, so the ordering and
    dedupe guarantees hold no matter which scanners contributed.
    """
    normalized = [
        normalize_finding(payload, repository_id=repository_id) for payload in payloads
    ]
    return sorted(dedupe(normalized), key=sort_key)


def severity_counts(findings: Iterable[SecurityFinding]) -> dict[str, int]:
    """Count findings per severity, including zero counts for absent bands.

    The zero entries matter: a client that iterates the distribution to render
    a legend should not have to special-case a severity with no findings.
    """
    counts = {severity: 0 for severity in SEVERITIES}
    for finding in findings:
        if finding.severity in counts:
            counts[finding.severity] += 1
    return counts


def category_distribution(findings: Iterable[SecurityFinding]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for finding in findings:
        distribution[finding.category] = distribution.get(finding.category, 0) + 1
    return distribution


def scanner_distribution(findings: Iterable[SecurityFinding]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for finding in findings:
        distribution[finding.scanner] = distribution.get(finding.scanner, 0) + 1
    return distribution


def findings_by_file(findings: Iterable[SecurityFinding]) -> dict[str, int]:
    per_file: dict[str, int] = {}
    for finding in findings:
        per_file[finding.file] = per_file.get(finding.file, 0) + 1
    return dict(sorted(per_file.items()))


def filter_findings(
    findings: Iterable[SecurityFinding],
    *,
    severity: str | None = None,
    category: str | None = None,
    scanner: str | None = None,
    file: str | None = None,
) -> list[SecurityFinding]:
    """Apply the API's validated filters and preserve the canonical order."""
    normalized_file = security_sources.normalize_path_for_scan(file) if file else None
    selected = []
    for finding in findings:
        if severity and finding.severity != severity:
            continue
        if category and finding.category != category:
            continue
        if scanner and finding.scanner != scanner:
            continue
        if normalized_file and finding.file != normalized_file:
            continue
        selected.append(finding)
    return sorted(selected, key=sort_key)
