"""Domain contract tests for the security finding schema.

These tests exist to pin the guarantees the rest of the system relies on:
normalization of loose scanner output, the extra-field ban that keeps file
content out of a finding, and the exact severity vocabulary.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.security import (
    CATEGORIES,
    SCANNERS,
    SEVERITIES,
    SecurityFinding,
    SecurityFindingQuery,
    SecurityScan,
    normalize_category,
    normalize_severity,
    normalize_path,
    severity_rank,
)


def _finding(**overrides) -> SecurityFinding:
    payload = {
        "file": "app/config.py",
        "line": 4,
        "category": "secrets",
        "severity": "high",
        "confidence": 0.9,
        "title": "Hardcoded credential",
        "description": "A credential is assigned in source.",
        "remediation": "Load it from a secret manager.",
        "scanner": "secret",
        "fingerprint": "abc123",
    }
    payload.update(overrides)
    return SecurityFinding(**payload)


class TestSeverityVocabulary:
    def test_exact_severity_is_preserved(self):
        for severity in SEVERITIES:
            assert normalize_severity(severity) == severity

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("CRITICAL", "critical"),
            ("High", "high"),
            ("blocker", "critical"),
            ("major", "high"),
            ("warn", "medium"),
            ("informational", "info"),
            ("crit", "critical"),
        ],
    )
    def test_aliases_map_onto_the_vocabulary(self, raw, expected):
        assert normalize_severity(raw) == expected

    def test_unknown_severity_falls_back_rather_than_failing_a_scan(self):
        assert normalize_severity("apocalyptic") == "medium"
        assert normalize_severity(None) == "medium"
        assert normalize_severity(7) == "medium"

    def test_default_is_configurable(self):
        assert normalize_severity("nonsense", default="low") == "low"

    def test_rank_orders_most_severe_first(self):
        ranks = [severity_rank(s) for s in SEVERITIES]
        assert ranks == sorted(ranks)
        assert ranks[0] == 0

    def test_unknown_severity_ranks_last_instead_of_raising(self):
        assert severity_rank("bogus") == len(SEVERITIES)

    def test_finding_rejects_a_severity_outside_the_vocabulary(self):
        # An out-of-vocabulary severity is coerced, never stored verbatim.
        assert _finding(severity="apocalyptic").severity == "medium"


class TestCategoryVocabulary:
    def test_every_category_is_explicit(self):
        assert set(CATEGORIES) == set(CATEGORIES)  # sanity: no duplicates lost
        assert len(CATEGORIES) == len(set(CATEGORIES))

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("secret", "secrets"),
            ("sql_injection", "injection"),
            ("weak_crypto", "crypto"),
            ("rce", "code_execution"),
            ("auth", "authentication"),
            ("supply_chain", "dependencies"),
            ("config", "misconfiguration"),
        ],
    )
    def test_aliases_map_onto_the_taxonomy(self, raw, expected):
        assert normalize_category(raw) == expected

    def test_unknown_category_falls_back(self):
        assert normalize_category("whatever") == "misconfiguration"

    def test_every_scanner_is_explicit(self):
        assert set(SCANNERS) == {"secret", "code", "dependency"}


class TestPathNormalization:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("./app/main.py", "app/main.py"),
            ("app\\services\\db.py", "app/services/db.py"),
            ("/etc/passwd", "etc/passwd"),
            ("../../etc/passwd", "etc/passwd"),
            ("C:/repo/app.py", "repo/app.py"),
            ("  app/x.py  ", "app/x.py"),
            ("app//double//slash.py", "app/double/slash.py"),
        ],
    )
    def test_paths_normalize_to_repository_relative_forward_slashes(self, raw, expected):
        assert normalize_path(raw) == expected

    def test_non_string_path_becomes_empty(self):
        assert normalize_path(None) == ""
        assert normalize_path(12) == ""


class TestFindingValidation:
    def test_text_fields_collapse_whitespace(self):
        finding = _finding(title="Hardcoded\n   credential\t", description="a\nb")
        assert finding.title == "Hardcoded credential"
        assert finding.description == "a b"

    def test_extra_fields_are_rejected(self):
        # This is the mechanism that stops a scanner from attaching the matched
        # source line. It must not be relaxed.
        with pytest.raises(ValidationError):
            _finding(matched_text="password = 'hunter2'")

    def test_confidence_is_clamped(self):
        assert _finding(confidence=5.0).confidence == 1.0
        assert _finding(confidence=-2).confidence == 0.0
        assert _finding(confidence="nope").confidence == 0.5

    def test_boolean_confidence_is_not_treated_as_a_number(self):
        # ``True`` is an int in Python; accepting it would silently store 1.0.
        assert _finding(confidence=True).confidence == 0.5

    def test_line_is_normalized_to_a_valid_position(self):
        assert _finding(line=-3).line == 0
        assert _finding(line="nonsense").line == 0
        assert _finding(line=12).line == 12

    def test_line_zero_is_the_whole_file_sentinel(self):
        assert _finding(line=0).file_level is True
        assert _finding(line=1).file_level is False

    def test_column_is_optional_and_normalized(self):
        assert _finding(column=None).column is None
        assert _finding(column=-1).column == 0
        assert _finding(column="bad").column is None
        assert _finding(column=7).column == 7

    def test_created_at_defaults_to_now(self):
        finding = SecurityFinding(
            title="t", description="d", remediation="r", scanner="code"
        )
        assert isinstance(finding.created_at, datetime)
        assert finding.created_at.tzinfo is not None

    def test_serialized_form_is_json_safe(self):
        payload = _finding().as_response()
        assert payload["severity"] == "high"
        # mode="json" must yield a string, not a datetime object.
        assert isinstance(payload["created_at"], str)


class TestScanContract:
    def test_scan_defaults_are_safe(self):
        scan = SecurityScan(
            scan_id="s1", repository_id="o/r", owner="o", repository="r"
        )
        assert scan.status == "complete"
        assert scan.vulnerability_source == "none"
        assert scan.findings == []
        assert scan.summary.total_findings == 0
        assert scan.summary.posture_score == 100

    def test_without_findings_keeps_the_summary(self):
        scan = SecurityScan(
            scan_id="s1",
            repository_id="o/r",
            owner="o",
            repository="r",
            findings=[_finding()],
        )
        trimmed = scan.without_findings()
        assert trimmed.findings == []
        assert trimmed.scan_id == scan.scan_id


class TestFindingQuery:
    def test_valid_filters_pass_through(self):
        query = SecurityFindingQuery(
            severity="critical", category="secrets", scanner="secret", file="./app/x.py"
        )
        assert query.file == "app/x.py"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"severity": "critial"},
            {"category": "injections"},
            {"scanner": "sast"},
        ],
    )
    def test_unknown_filter_values_are_rejected(self, kwargs):
        # A misspelled filter must fail loudly. Silently matching nothing would
        # look exactly like a clean repository.
        with pytest.raises(ValidationError):
            SecurityFindingQuery(**kwargs)

    def test_filters_are_all_optional(self):
        assert SecurityFindingQuery().severity is None
