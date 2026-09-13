from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any

SEVERITY_HINTS: list[tuple[re.Pattern[str], str, str, str, float, str, str]] = [
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
        "security",
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
        "security",
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
        "security",
    ),
    (
        re.compile(r"\b(?:pickle|yaml)\s*\.\s*(?:safe_)?(?:load|loads)\s*\(", re.IGNORECASE),
        "Unsafe deserialization",
        "Loading untrusted serialized data can trigger arbitrary code execution.",
        "high",
        0.8,
        "Use safe serialization formats and validate untrusted data before deserialization.",
        "security",
    ),
    (
        re.compile(r"\b(?:eval|exec|os\.system|subprocess\s*\.\s*(?:call|run|Popen)|child_process)\s*\("),
        "Dynamic code execution",
        "Dynamic code or process execution should never receive untrusted input.",
        "high",
        0.75,
        "Avoid eval() and other dynamic execution of untrusted input. Use a safe parser or allowlisted operations instead.",
        "security",
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
        "security",
    ),
    (
        re.compile(r"\bchmod\s+\d{4}\b|<\s*(?:script|iframe|object)\b|\.innerHTML\s*=", re.IGNORECASE),
        "Client-side injection risk",
        "Review for injection (XSS/markup); never render unsanitized input.",
        "medium",
        0.6,
        "Escape or sanitize untrusted output using the appropriate context-aware mechanism.",
        "security",
    ),
]

BUG_HINTS: list[tuple[re.Pattern[str], str, str, str, float, str, str]] = [
    (
        re.compile(r"\bif\s*\(?\s*[a-zA-Z_$]\w*\s*=\s*(?!=)(?!:)"),
        "Assignment instead of comparison",
        "An assignment appears where a condition is expected; this condition is usually always-true or a typo for ==.",
        "high",
        0.85,
        "Use == for equality checks inside conditions (e.g. if x == expected instead of if x = expected).",
        "bug",
    ),
    (
        re.compile(r"\b([a-zA-Z_$]\w*)\s*==\s*\1\b"),
        "Self-comparison (always true)",
        "A value is compared with itself, so the condition is always true; this is usually a swapped variable.",
        "medium",
        0.7,
        "Compare the value against the intended operand, not itself.",
        "bug",
    ),
    (
        re.compile(r"\b([a-zA-Z_$]\w*)\s*!=\s*\1\b"),
        "Self-negated comparison (always false)",
        "A value is compared to itself with !=, so the condition is always false; this is usually a swapped variable.",
        "medium",
        0.7,
        "Compare the value against the intended operand, not itself.",
        "bug",
    ),
    (
        re.compile(r"^\s*([a-zA-Z_$]\w*)\s*=\s*\1\s*(?:#.*)?$"),
        "Pointless self-assignment",
        "A variable is assigned its own value, which does nothing; the intended expression may be missing.",
        "low",
        0.75,
        "Remove the self-assignment or assign the intended value.",
        "bug",
    ),
    (
        re.compile(r"\b([a-zA-Z_$]\w*)\s*(?:[/%])+\s*0(?:\.0+)?(?!\.\d)\b"),
        "Division or modulo by zero",
        "An arithmetic expression divides or takes modulo by a zero literal, which raises a runtime error.",
        "high",
        0.8,
        "Guard the divisor so it can never be zero (or zero-point-zero) at runtime.",
        "bug",
    ),
    (
        re.compile(r"\bdef\s+\w+\s*\([^)]*=\s*(?:\[\]|\{\}|list\s*\(\s*\)|set\s*\(\s*\)|dict\s*\(\s*\)|[^)\]]*\s*#\s*Mutable)"),
        "Mutable default argument",
        "A mutable object is used as a default argument; it is shared across all calls and accumulates state.",
        "medium",
        0.8,
        "Use None as the default and construct the mutable inside the function body.",
        "bug",
    ),
    (
        re.compile(
            r"^\s*except(?:\s+[a-zA-Z_]\w*(?:\s+as\s+\w+)?)?\s*:\s*(?:pass|break|continue)\s*(?:#.*)?$"
            r"|^\s*except\s*:\s*(?:#.*)?$"
        ),
        "Broad exception silently swallowed",
        "An exception is caught and silently ignored, which hides failures and makes debugging harder.",
        "medium",
        0.6,
        "Handle the exception explicitly or re-raise it; avoid bare except and silent pass blocks.",
        "bug",
    ),
    (
        re.compile(
            r"^\s*(?:list|dict|set|tuple|str|int|float|bytes|bool|input|id|map|filter|zip|len|range|sum|min|max|"
            r"sorted|reversed|type|object|print|format)\s*=[^=]"
        ),
        "Variable shadows built-in name",
        "A variable reuses a built-in name, which can break unrelated code that expects the built-in behavior.",
        "low",
        0.55,
        "Rename the variable so it does not shadow the built-in.",
        "bug",
    ),
    (
        re.compile(r"\b[a-zA-Z_]\w*\s*==\s*None\b"),
        "None compared with ==",
        "None identity compares with ==, which is fragile; None is a singleton meant for is comparisons.",
        "medium",
        0.75,
        "Use `is None` / `is not None` instead of == / != None.",
        "bug",
    ),
    (
        re.compile(r"\b[a-zA-Z_]\w*\s+(?:==|is)\s+(?:True|False)\b"),
        "Identity comparison with boolean constant",
        "A value is compared against a boolean literal; return the boolean expression directly instead.",
        "medium",
        0.75,
        "Return the boolean value directly or compare with is when checking identity.",
        "bug",
    ),
]

ALL_HINTS = SEVERITY_HINTS + BUG_HINTS

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
    - category = the true pattern category ("security" or "bug")
    - heuristic_severity = the true pattern severity ("critical"/"high"/"medium"/"low")
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

        evidence: list[tuple[str, str, str, float, str, str]] = []
        for pattern, title, description, hint_severity, confidence, recommendation, category in ALL_HINTS:
            if pattern.search(text):
                evidence.append((title, description, hint_severity, confidence, recommendation, category))
        if not evidence:
            continue

        file_path, target_line = _current_file_and_line(patch_lines, idx)
        remaining_line = re.sub(r"^\d+\s*", "", text)
        sanitized = remaining_line.strip()[:256]
        for title, description, hint_severity, confidence, recommendation, category in evidence:
            findings.append(
                {
                    "id": _finding_id(title, file_path, target_line),
                    "title": title,
                    "description": description,
                    "severity": "low",
                    "category": category,
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