from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any

SEVERITY_HINTS: list[tuple[re.Pattern[str], str, str, str, float, str]] = [
    (
        re.compile(
            r"\b(?:BEGIN |-----BEGIN )?(?:RSA |DSA |EC |OPENSSH |PGP )?(?:PRIVATE KEY|PRIVATE KEY-----|"
            r"OBJECT-----|BEGIN CERTIFICATE-----)\b"
        ),
        "Embedded secret key",
        "A private key or certificate appears to be committed to the repository.",
        "critical",
        0.95,
        "Remove hardcoded credentials and load secrets from environment variables or a secure secret manager.",
    ),
    (
        re.compile(
            r"\b(?:AKIA[0-9A-Z]{16}|ghp_[0-9A-Za-z]{36}|gho_[0-9A-Za-z]{36}|"
            r"xox[baprs]-[0-9A-Za-z-]{10,}|sk-[0-9A-Za-z-]{20,}|"
            r"AIza[0-9A-Za-z_-]{35}|ya29\.[0-9A-Za-z_-]+)\b"
        ),
        "Possible API secret token",
        "A high-entropy token that looks like a service or API secret may be committed.",
        "high",
        0.85,
        "Remove hardcoded credentials and load secrets from environment variables or a secure secret manager.",
    ),
    (
        re.compile(
            r"\b(?:password|passwd|secret|token|apikey|api_key|credential|access_key)"
            r"\s*[:=]\s*[\"'][^\"']{6,}[\"']",
            re.IGNORECASE,
        ),
        "Hardcoded credential",
        "A value assigned to a credential-like variable appears hardcoded.",
        "high",
        0.8,
        "Remove hardcoded credentials and load secrets from environment variables or a secure secret manager.",
    ),
    (
        re.compile(r"\b(?:pickle|yaml)\s*\.\s*(?:safe_)?(?:load|loads)\s*\(", re.IGNORECASE),
        "Unsafe deserialization",
        "Loading untrusted serialized data can trigger arbitrary code execution.",
        "high",
        0.8,
        "Use safe serialization formats and validate untrusted data before deserialization.",
    ),
    (
        re.compile(r"\b(?:eval|exec|os\.system|subprocess\s*\.\s*(?:call|run|Popen)|child_process)\s*\("),
        "Dynamic code execution",
        "Dynamic code or process execution should never receive untrusted input.",
        "high",
        0.75,
        "Avoid eval() and other dynamic execution of untrusted input. Use a safe parser or allowlisted operations instead.",
    ),
    (
        re.compile(
            r"\b(?:execute|query|raw|exec|run)\s*\(\s*f[\"']|"
            r"\b(?:SELECT|INSERT|UPDATE|DELETE|CREATE|DROP)\b[^;]{0,200}(?:\]|\+|\{|%s\s*\+)",
            re.IGNORECASE,
        ),
        "Possible SQL injection",
        "Dynamic SQL assembled from strings or f-strings may be injectable; use parameters.",
        "high",
        0.7,
        "Use parameterized queries/prepared statements or an ORM instead of building SQL with untrusted input.",
    ),
    (
        re.compile(r"\bchmod\s+\d{4}\b|<\s*(?:script|iframe|object)\b|\.innerHTML\s*=", re.IGNORECASE),
        "Client-side injection risk",
        "Review for injection (XSS/markup); never render unsanitized input.",
        "medium",
        0.6,
        "Escape or sanitize untrusted output using the appropriate context-aware mechanism.",
    ),
]

_FULL_LINE_COMMENT_PREFIXES = ("#", "//", "<!--")


def _scan_line(text: str, state: dict[str, bool]) -> bool:
    """Return True when ``text`` is non-executable prose and pattern checks should be skipped.

    Tracks Python docstring (``\"\"\"``/``'''``) and ``/* ... */`` block-comment
    regions across lines so that explanatory comments and docstrings describing a
    vulnerability do not themselves produce findings.
    """
    stripped = text.strip()
    triple_count = stripped.count('"""') + stripped.count("'''")

    if state["in_triple"]:
        if triple_count > 0 and triple_count % 2 == 1:
            state["in_triple"] = False
        return True

    if state["in_block_comment"]:
        if "*/" in stripped:
            state["in_block_comment"] = False
        return True

    if stripped.startswith(_FULL_LINE_COMMENT_PREFIXES) or stripped.startswith("/*"):
        if stripped.startswith("/*") and "*/" not in stripped:
            state["in_block_comment"] = True
        return True

    if triple_count > 0:
        if triple_count % 2 == 1:
            state["in_triple"] = True
        return True

    if "/*" in stripped:
        state["in_block_comment"] = True
        return True

    return False


def _current_file_and_line(patch_lines: list[str], idx: int) -> tuple[str, int | None]:
    """Walk a unified diff and return (file, new_line_number) for the line at idx."""
    filename = file_path = "unknown"
    added_line = None
    new_line = None
    for line in patch_lines[: idx + 1]:
        if line.startswith("+++ b/"):
            file_path = line[6:].strip()
        elif line.startswith("--- a/"):
            filename = file_path or line[6:].strip()
        elif "diff --git" in line:
            match = re.search(r"diff --git a/(\S+) b/", line)
            if match:
                filename = match.group(1)
        elif line.startswith("@@"):
            match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)?\s*@@", line)
            if match:
                new_line = int(match.group(1))
        elif not line.startswith(("diff --git", "index ", "--- ", "+++ ")):
            if line.startswith("+"):
                if new_line is not None:
                    added_line = new_line
                    new_line += 1
            elif line.startswith("-"):
                pass
            else:
                if new_line is not None:
                    new_line += 1
    return (file_path or filename, added_line if added_line is not None else new_line)


def _finding_id(*parts: Any) -> str:
    raw = "|".join(str(p) for p in parts)
    return "h-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _dedupe(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for finding in findings:
        key = (finding["id"], finding["file"], finding["title"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def run_heuristics(patch: str, filename: str | None = None) -> list[dict[str, Any]]:
    """Run pattern heuristics over a unified diff and return advisory findings.

    Every finding is produced with:
    - source = "heuristic"
    - severity = "low" (advisory only; the review score grades it)
    - heuristic_severity = the true pattern severity ("critical"/"high"/"medium")
    - heuristic_confidence = pattern confidence
    - recommendation = category-specific remediation for the matched pattern

    Resolution is correctly mapped onto added/context lines: a finding on a
    removed (``-``) line is attributed to the replacing added line when present.

    Full-line comments and docstring/block-comment prose are skipped so that a
    vulnerability described in comments does not produce duplicate findings.
    """
    filename = filename or "unknown"
    findings: list[dict[str, Any]] = []
    patch_lines = patch.splitlines()
    if not patch_lines:
        return findings

    state: dict[str, bool] = {"in_triple": False, "in_block_comment": False}

    for idx, line in enumerate(patch_lines):
        if line.startswith("diff --git") or line.startswith("+++ "):
            state = {"in_triple": False, "in_block_comment": False}

        text = line.lstrip("+-")
        if _scan_line(text, state):
            continue

        evidence: list[tuple[str, str, str, float, str]] = []
        for pattern, title, description, hint_severity, confidence, recommendation in SEVERITY_HINTS:
            if pattern.search(text):
                evidence.append((title, description, hint_severity, confidence, recommendation))
        if not evidence:
            continue

        file_path, target_line = _current_file_and_line(patch_lines, idx)
        remaining_line = re.sub(r"^\d+\s*", "", text)
        sanitized = remaining_line.strip()[:256]
        for title, description, hint_severity, confidence, recommendation in evidence:
            findings.append(
                {
                    "id": _finding_id(title, file_path, target_line),
                    "title": title,
                    "description": description,
                    "severity": "low",
                    "category": "security",
                    "file": file_path,
                    "line": target_line,
                    "code": sanitized,
                    "recommendation": recommendation,
                    "confidence": round(confidence, 2),
                    "source": "heuristic",
                    "heuristic_severity": hint_severity,
                    "heuristic_confidence": round(confidence, 2),
                }
            )

    return _dedupe(findings)