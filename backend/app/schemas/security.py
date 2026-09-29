"""Domain contract for the Sprint 4 Security Intelligence Engine.

One finding shape for every scanner
-----------------------------------
Secret detection, source-code rules and dependency analysis all emit
:class:`SecurityFinding`. Scanners are deliberately dumb: they report what they
matched, and :mod:`app.services.security_normalizer` is responsible for turning
whatever they emit into something valid, deduplicated and fingerprinted. That
split is what lets a new scanner be added without touching the scoring, the
persistence or the API.

The contract is intentionally *not* the Sprint 3 review finding. A security
finding is anchored to a repository rather than a pull request, carries a
scanner attribution and a stable fingerprint, and is never allowed to contain
the matched text — see :attr:`SecurityFinding.forbid_extra`.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Severity vocabulary, ordered most to least severe. The order is meaningful:
#: :func:`severity_rank` and the risk calculator both rely on it.
SecuritySeverity = Literal["critical", "high", "medium", "low", "info"]

SEVERITIES: tuple[str, ...] = ("critical", "high", "medium", "low", "info")

#: Which detector produced a finding. Kept as an explicit vocabulary so the API
#: can group by detector and so an unknown scanner is a validation error rather
#: than a silently unlabelled finding.
ScannerType = Literal["secret", "code", "dependency"]

SCANNERS: tuple[str, ...] = ("secret", "code", "dependency")

#: Security taxonomy. Wider than the Sprint 3 review categories because these
#: describe *kinds of weakness*, not kinds of change.
SecurityCategory = Literal[
    "secrets",
    "injection",
    "code_execution",
    "crypto",
    "path_traversal",
    "deserialization",
    "authentication",
    "dependencies",
    "misconfiguration",
]

CATEGORIES: tuple[str, ...] = (
    "secrets",
    "injection",
    "code_execution",
    "crypto",
    "path_traversal",
    "deserialization",
    "authentication",
    "dependencies",
    "misconfiguration",
)

#: Lifecycle of a scan. ``pending`` and ``running`` exist so the API can report
#: work in progress and the UI can render a progress state, even though the
#: current implementation scans synchronously (see the service module).
ScanStatus = Literal["pending", "running", "complete", "failed"]

SCAN_STATUSES: tuple[str, ...] = ("pending", "running", "complete", "failed")

_SEVERITY_ALIASES = {
    "crit": "critical",
    "sev0": "critical",
    "severe": "critical",
    "blocker": "critical",
    "major": "high",
    "moderate": "medium",
    "med": "medium",
    "minor": "low",
    "warning": "medium",
    "warn": "medium",
    "informational": "info",
    "information": "info",
    "note": "info",
    "none": "info",
}

_CATEGORY_ALIASES = {
    "secret": "secrets",
    "credentials": "secrets",
    "credential": "secrets",
    "hardcoded_secret": "secrets",
    "sql_injection": "injection",
    "sqli": "injection",
    "command_injection": "injection",
    "xss": "injection",
    "rce": "code_execution",
    "code_injection": "code_execution",
    "dynamic_execution": "code_execution",
    "weak_crypto": "crypto",
    "cryptography": "crypto",
    "weak_cryptography": "crypto",
    "traversal": "path_traversal",
    "path": "path_traversal",
    "insecure_deserialization": "deserialization",
    "unsafe_deserialization": "deserialization",
    "auth": "authentication",
    "authn": "authentication",
    "jwt": "authentication",
    "dependency": "dependencies",
    "supply_chain": "dependencies",
    "vulnerable_dependency": "dependencies",
    "config": "misconfiguration",
    "configuration": "misconfiguration",
    "insecure_configuration": "misconfiguration",
}

#: Line 0 is the sentinel for a whole-file finding, matching the Sprint 3
#: review contract so the frontend renders it the same way.
FILE_LEVEL_LINE = 0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def severity_rank(severity: str) -> int:
    """Lower rank sorts first. Unknown severities sort last rather than raising."""
    try:
        return SEVERITIES.index(severity)
    except ValueError:
        return len(SEVERITIES)


def normalize_severity(value: Any, *, default: str = "medium") -> str:
    """Coerce an arbitrary severity label onto the supported vocabulary.

    Unrecognised input falls back to ``default`` rather than failing the scan:
    one odd severity string should not cost a reviewer the whole finding set.
    """
    if not isinstance(value, str):
        return default
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    if key in SEVERITIES:
        return key
    return _SEVERITY_ALIASES.get(key, default)


def normalize_category(value: Any, *, default: str = "misconfiguration") -> str:
    """Coerce an arbitrary category label onto the supported taxonomy."""
    if not isinstance(value, str):
        return default
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    if key in CATEGORIES:
        return key
    return _CATEGORY_ALIASES.get(key, default)


def normalize_scanner(value: Any, *, default: str = "code") -> str:
    if not isinstance(value, str):
        return default
    key = value.strip().lower()
    return key if key in SCANNERS else default


_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def normalize_path(path: Any) -> str:
    """Normalize a repository-relative path to forward slashes.

    Strips a leading ``./`` and any ``/`` prefix, and converts Windows separators
    so a fingerprint computed on one platform matches the same file elsewhere.
    A path that escapes the repository root is reduced to its basename, since
    there is no valid reviewable location outside the tree.
    """
    if not isinstance(path, str):
        return ""
    cleaned = path.strip().replace("\\", "/")
    cleaned = _WINDOWS_DRIVE_RE.sub("", cleaned)
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    cleaned = cleaned.lstrip("/")
    # Collapse any traversal that survived; we never resolve outside the repo.
    parts = [part for part in cleaned.split("/") if part not in ("", ".", "..")]
    return "/".join(parts)


class SecurityFinding(BaseModel):
    """A single deterministic security finding.

    ``model_config`` forbids extra fields, which is load-bearing: a scanner that
    accidentally attaches the matched line (and therefore a secret) fails
    validation at the boundary instead of persisting the value.
    """

    model_config = ConfigDict(extra="forbid")

    finding_id: str = ""
    repository_id: str = ""
    file: str = ""
    line: int = FILE_LEVEL_LINE
    column: int | None = None
    category: SecurityCategory = "misconfiguration"
    severity: SecuritySeverity = "medium"
    confidence: float = 0.5
    title: str
    description: str
    remediation: str
    scanner: ScannerType = "code"
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=_utcnow)

    @field_validator("severity", mode="before")
    @classmethod
    def _coerce_severity(cls, value: Any) -> Any:
        return normalize_severity(value)

    @field_validator("category", mode="before")
    @classmethod
    def _coerce_category(cls, value: Any) -> Any:
        return normalize_category(value)

    @field_validator("scanner", mode="before")
    @classmethod
    def _coerce_scanner(cls, value: Any) -> Any:
        return normalize_scanner(value)

    @field_validator("file", mode="before")
    @classmethod
    def _coerce_file(cls, value: Any) -> Any:
        return normalize_path(value)

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, value: Any) -> Any:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return 0.5
        return max(0.0, min(1.0, float(value)))

    @field_validator("line", mode="before")
    @classmethod
    def _coerce_line(cls, value: Any) -> Any:
        # Line 0 is the whole-file sentinel, so a negative or unparseable line
        # collapses to it rather than surfacing a nonsense position.
        try:
            number = int(value)
        except (TypeError, ValueError):
            return FILE_LEVEL_LINE
        return max(FILE_LEVEL_LINE, number)

    @field_validator("column", mode="before")
    @classmethod
    def _coerce_column(cls, value: Any) -> Any:
        if value is None:
            return None
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return max(0, number)

    @field_validator("title", "description", "remediation", mode="before")
    @classmethod
    def _coerce_text(cls, value: Any) -> Any:
        # Multi-line matcher output is collapsed: a finding is a sentence, not
        # a code excerpt, and a code excerpt is where secrets would leak.
        if not isinstance(value, str):
            return ""
        return " ".join(value.split())

    @property
    def file_level(self) -> bool:
        """True when the finding applies to the file rather than one line."""
        return self.line == FILE_LEVEL_LINE

    def as_response(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SeverityCounts(BaseModel):
    """Finding counts per severity. Every severity key is always present."""

    model_config = ConfigDict(extra="forbid")

    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0

    def as_dict(self) -> dict[str, int]:
        return {severity: getattr(self, severity) for severity in SEVERITIES}

    def total(self) -> int:
        return sum(self.as_dict().values())


class SecurityRiskSummary(BaseModel):
    """Deterministic risk picture for one repository scan.

    ``weighted_risk`` uses the same weights the Security page has always used
    (critical 8, high 3, medium 1) so a posture number does not silently change
    meaning when this engine replaces the review-derived estimate.
    """

    model_config = ConfigDict(extra="forbid")

    total_findings: int = 0
    severity_counts: SeverityCounts = Field(default_factory=SeverityCounts)
    weighted_risk: int = 0
    posture_score: int = 100
    category_distribution: dict[str, int] = Field(default_factory=dict)
    scanner_distribution: dict[str, int] = Field(default_factory=dict)
    files_scanned: int = 0
    files_skipped: int = 0
    findings_by_file: dict[str, int] = Field(default_factory=dict)
    dependencies_analyzed: int = 0

    def as_response(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class RepositoryPosture(BaseModel):
    """Latest posture for one repository, or an explicit 'never scanned' state."""

    model_config = ConfigDict(extra="forbid")

    repository_id: str
    owner: str = ""
    repository: str = ""
    full_name: str = ""
    has_scan: bool = False
    scan_id: str | None = None
    scanned_at: str | None = None
    summary: SecurityRiskSummary = Field(default_factory=SecurityRiskSummary)
    methodology: str = ""


class CreateSecurityScanRequest(BaseModel):
    """Body for starting a repository security scan."""

    model_config = ConfigDict(extra="forbid")

    owner: str = Field(min_length=1, max_length=200)
    repository: str = Field(min_length=1, max_length=200)
    provider: str = "github"
    ref: str | None = None
    max_files: int | None = Field(default=None, ge=1, le=2000)

    @field_validator("provider")
    @classmethod
    def _known_provider(cls, value: str) -> str:
        key = value.strip().lower()
        if key not in ("github", "gitlab"):
            raise ValueError("provider must be 'github' or 'gitlab'")
        return key

    @field_validator("owner", "repository")
    @classmethod
    def _trim(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned


class SecurityScan(BaseModel):
    """A stored scan and its headline risk numbers.

    Findings are included on the single-scan read and omitted from list
    responses via :meth:`without_findings`, so a repository with thousands of
    findings does not return them all on every overview request.
    """

    model_config = ConfigDict(extra="forbid")

    scan_id: str = ""
    schema_version: int = 1
    status: ScanStatus = "complete"
    repository_id: str
    owner: str
    repository: str
    full_name: str = ""
    provider: str = "github"
    ref: str | None = None
    commit_sha: str | None = None
    summary: SecurityRiskSummary = Field(default_factory=SecurityRiskSummary)
    findings: list[SecurityFinding] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    duration_ms: int | None = None
    scanned_at: str | None = None
    #: Which advisory source contributed known-CVE findings. ``"none"`` means
    #: only mechanically-derived risks are present, which a reader needs to know
    #: before reading "no vulnerabilities found".
    vulnerability_source: str = "none"

    def without_findings(self) -> SecurityScan:
        return self.model_copy(update={"findings": []})


class SecurityFindingQuery(BaseModel):
    """Validated filter set for a findings read.

    Unknown filter values are rejected rather than silently matching nothing, so
    a client bug surfaces immediately instead of looking like a clean scan.
    """

    model_config = ConfigDict(extra="forbid")

    severity: str | None = None
    category: str | None = None
    scanner: str | None = None
    file: str | None = None

    @field_validator("severity")
    @classmethod
    def _severity_known(cls, value: str | None) -> str | None:
        if value is None:
            return None
        key = value.strip().lower()
        if key not in SEVERITIES:
            raise ValueError(f"Unknown severity '{value}'")
        return key

    @field_validator("category")
    @classmethod
    def _category_known(cls, value: str | None) -> str | None:
        if value is None:
            return None
        key = value.strip().lower()
        if key not in CATEGORIES:
            raise ValueError(f"Unknown category '{value}'")
        return key

    @field_validator("scanner")
    @classmethod
    def _scanner_known(cls, value: str | None) -> str | None:
        if value is None:
            return None
        key = value.strip().lower()
        if key not in SCANNERS:
            raise ValueError(f"Unknown scanner '{value}'")
        return key

    @field_validator("file")
    @classmethod
    def _file_normalized(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_path(value)
        return normalized or None


class SecurityFindingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: str
    total: int
    findings: list[SecurityFinding] = Field(default_factory=list)


class SecurityExplanation(BaseModel):
    """Model-written prose for one finding.

    Explicitly incapable of influencing severity, risk, existence or ownership:
    every field here is display-only text, and the scanner verdict it accompanies
    was already fixed before this was produced.
    """

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    explanation: str
    impact: str
    remediation: str
    model: str | None = None
    #: Explains why no prose is attached, when ``explanation`` is empty.
    unavailable_reason: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.explanation)
