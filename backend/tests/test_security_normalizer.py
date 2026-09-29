"""Finding normalizer tests.

The normalizer is the contract boundary: three scanners with three payload
shapes enter, one validated :class:`SecurityFinding` shape leaves. The tests
here cover that conversion and the three properties every consumer relies on —
stable identity, deduplication, and a total deterministic order.
"""

import pytest

from app.schemas.security import SEVERITIES, SecurityFinding
from app.services import security_normalizer as normalizer
from app.services.security_normalizer import (
    NormalizationError,
    normalize_finding,
    normalize_findings,
    sanitize_payload,
)


def payload(**overrides):
    base = {
        "file": "app/config.py",
        "line": 4,
        "category": "secrets",
        "severity": "high",
        "confidence": 0.9,
        "title": "Hardcoded credential",
        "description": "d",
        "remediation": "r",
        "scanner": "secret",
        "rule_id": "secret.credential_assignment",
    }
    base.update(overrides)
    return base


class TestPayloadSanitisation:
    def test_unknown_keys_are_dropped(self):
        cleaned = sanitize_payload(payload(unexpected="value"))
        assert "unexpected" not in cleaned

    def test_the_rule_id_is_preserved_for_fingerprinting(self):
        assert sanitize_payload(payload())["rule_id"] == "secret.credential_assignment"

    @pytest.mark.parametrize(
        "key",
        ["match", "matched_text", "snippet", "code", "source", "line_text", "content", "value", "secret", "context"],
    )
    def test_content_bearing_keys_are_rejected_loudly(self, key):
        # Dropping these silently would hide a scanner regression that attaches
        # file content — and for a secret scanner, that is a leak.
        with pytest.raises(NormalizationError):
            sanitize_payload(payload(**{key: "leaked content"}))

    def test_a_non_mapping_payload_is_rejected(self):
        with pytest.raises(NormalizationError):
            sanitize_payload(["not", "a", "mapping"])


class TestNormalizeFinding:
    def test_a_scanner_payload_becomes_a_validated_finding(self):
        finding = normalize_finding(payload(), repository_id="octo/repo")
        assert isinstance(finding, SecurityFinding)
        assert finding.repository_id == "octo/repo"
        assert finding.severity == "high"
        assert finding.scanner == "secret"

    def test_severity_is_validated_and_coerced(self):
        assert normalize_finding(payload(severity="BLOCKER")).severity == "critical"
        assert normalize_finding(payload(severity="nonsense")).severity == "medium"

    def test_category_is_validated_and_coerced(self):
        assert normalize_finding(payload(category="sqli")).category == "injection"
        assert normalize_finding(payload(category="unknown")).category == "misconfiguration"

    def test_scanner_provenance_is_preserved(self):
        for scanner_name in ("secret", "code", "dependency"):
            finding = normalize_finding(payload(scanner=scanner_name))
            assert finding.scanner == scanner_name

    def test_an_unknown_scanner_is_coerced_rather_than_dropped(self):
        assert normalize_finding(payload(scanner="sast")).scanner == "code"

    def test_paths_are_normalized(self):
        finding = normalize_finding(payload(file="./src\\app\\x.py"))
        assert finding.file == "src/app/x.py"

    def test_a_traversing_path_is_reduced_into_the_repository(self):
        finding = normalize_finding(payload(file="../../etc/passwd"))
        assert finding.file == "etc/passwd"
        assert ".." not in finding.file

    def test_a_missing_line_becomes_the_file_level_sentinel(self):
        assert normalize_finding({**payload(), "line": None}).line == 0
        assert normalize_finding({k: v for k, v in payload().items() if k != "line"}).line == 0

    def test_a_negative_line_is_clamped(self):
        assert normalize_finding(payload(line=-5)).line == 0

    def test_repository_id_is_attached(self):
        assert normalize_finding(payload(), repository_id="a/b").repository_id == "a/b"

    def test_a_content_bearing_payload_is_rejected_at_the_boundary(self):
        with pytest.raises(NormalizationError):
            normalize_finding(payload(snippet="password = 'x'"))


class TestFingerprinting:
    def test_a_fingerprint_is_generated_when_absent(self):
        assert normalize_finding(payload()).fingerprint

    def test_the_fingerprint_is_stable_for_the_same_rule_and_path(self):
        first = normalize_finding(payload(line=4)).fingerprint
        second = normalize_finding(payload(line=9)).fingerprint
        # A code finding that moves down the file is still the same finding.
        assert first == second

    def test_different_rules_produce_different_fingerprints(self):
        first = normalize_finding(payload(rule_id="code.eval")).fingerprint
        second = normalize_finding(payload(rule_id="code.exec")).fingerprint
        assert first != second

    def test_different_paths_produce_different_fingerprints(self):
        first = normalize_finding(payload(file="a.py")).fingerprint
        second = normalize_finding(payload(file="b.py")).fingerprint
        assert first != second

    def test_a_supplied_fingerprint_is_preserved(self):
        # The secret scanner supplies a value-derived fingerprint, which is what
        # makes cross-file dedupe of a leaked key possible.
        finding = normalize_finding(payload(fingerprint="deadbeef"))
        assert finding.fingerprint == "deadbeef"

    def test_fingerprints_are_hex_and_bounded(self):
        digest = normalize_finding(payload()).fingerprint
        assert len(digest) == 32
        int(digest, 16)


class TestDeduplication:
    def _findings(self, count, **overrides):
        return [normalize_finding(payload(**overrides)) for _ in range(count)]

    def test_identical_findings_collapse_to_one(self):
        findings = self._findings(3)
        assert len(normalizer.dedupe(findings)) == 1

    def test_different_files_are_kept(self):
        findings = [
            normalize_finding(payload(file="a.py")),
            normalize_finding(payload(file="b.py")),
        ]
        assert len(normalizer.dedupe(findings)) == 2

    def test_the_surviving_duplicate_is_the_earliest_line(self):
        # A reviewer should be sent to the first place the problem appears, not
        # to whichever scanner happened to finish last.
        findings = [
            normalize_finding(payload(line=40)),
            normalize_finding(payload(line=7)),
        ]
        assert normalizer.dedupe(findings)[0].line == 7

    def test_normalize_findings_deduplicates_across_scanners(self):
        results = normalize_findings(
            [payload(), payload(), payload(file="other.py")]
        )
        assert len(results) == 2

    def test_dedupe_of_an_empty_list_is_empty(self):
        assert normalizer.dedupe([]) == []


class TestOrdering:
    def test_findings_are_ordered_by_severity_first(self):
        findings = normalize_findings(
            [
                payload(severity="low", file="a.py", rule_id="r1"),
                payload(severity="critical", file="b.py", rule_id="r2"),
                payload(severity="medium", file="c.py", rule_id="r3"),
            ]
        )
        assert [f.severity for f in findings] == ["critical", "medium", "low"]

    def test_within_a_severity_the_most_confident_comes_first(self):
        findings = normalize_findings(
            [
                payload(severity="high", confidence=0.5, file="a.py", rule_id="r1"),
                payload(severity="high", confidence=0.9, file="b.py", rule_id="r2"),
            ]
        )
        assert findings[0].confidence == 0.9

    def test_ordering_is_total_and_therefore_reproducible(self):
        raw = [
            payload(severity="high", file="z.py", rule_id="code.eval"),
            payload(severity="high", file="a.py", rule_id="code.exec"),
            payload(severity="critical", file="m.py", rule_id="code.sql_injection.python"),
        ]
        first = [f.fingerprint for f in normalize_findings(raw)]
        second = [f.fingerprint for f in normalize_findings(list(reversed(raw)))]
        assert first == second

    def test_shuffling_input_does_not_change_the_output(self):
        # A scan reads files concurrently; the output must not depend on which
        # request finished first.
        raw = [payload(file=f"f{i}.py", rule_id=f"r{i}") for i in range(12)]
        baseline = [f.fingerprint for f in normalize_findings(raw)]
        for rotation in range(1, 4):
            rotated = raw[rotation:] + raw[:rotation]
            assert [f.fingerprint for f in normalize_findings(rotated)] == baseline

    def test_every_severity_is_representable(self):
        findings = normalize_findings(
            [payload(severity=severity, rule_id=f"r{severity}") for severity in SEVERITIES]
        )
        assert len(findings) == len(SEVERITIES)


class TestAggregations:
    def _mixed(self):
        return normalize_findings(
            [
                payload(severity="critical", category="secrets", scanner="secret", file="a.py", rule_id="r1"),
                payload(severity="high", category="injection", scanner="code", file="b.py", rule_id="r2"),
                payload(severity="high", category="injection", scanner="code", file="b.py", line=9, rule_id="r3"),
                payload(severity="low", category="crypto", scanner="code", file="c.py", rule_id="r4"),
            ]
        )

    def test_severity_counts_include_zero_entries(self):
        counts = normalizer.severity_counts(self._mixed())
        assert set(counts) == set(SEVERITIES)
        assert counts["critical"] == 1
        assert counts["high"] == 2
        assert counts["medium"] == 0
        assert counts["info"] == 0

    def test_severity_counts_of_an_empty_set_are_all_zero(self):
        assert set(normalizer.severity_counts([]).values()) == {0}

    def test_category_distribution_counts_by_category(self):
        distribution = normalizer.category_distribution(self._mixed())
        assert distribution == {"secrets": 1, "injection": 2, "crypto": 1}

    def test_scanner_distribution_counts_by_scanner(self):
        assert normalizer.scanner_distribution(self._mixed()) == {"secret": 1, "code": 3}

    def test_findings_by_file_is_sorted_by_path(self):
        per_file = normalizer.findings_by_file(self._mixed())
        assert list(per_file) == ["a.py", "b.py", "c.py"]
        assert per_file["b.py"] == 2


class TestFiltering:
    def _mixed(self):
        return normalize_findings(
            [
                payload(severity="critical", category="secrets", scanner="secret", file="a.py", rule_id="r1"),
                payload(severity="high", category="injection", scanner="code", file="b.py", rule_id="r2"),
                payload(severity="high", category="injection", scanner="code", file="b.py", line=9, rule_id="r3"),
                payload(severity="low", category="crypto", scanner="code", file="c.py", rule_id="r4"),
            ]
        )

    def test_filter_by_severity(self):
        findings = self._mixed()
        assert len(normalizer.filter_findings(findings, severity="high")) == 2

    def test_filter_by_category(self):
        findings = self._mixed()
        assert len(normalizer.filter_findings(findings, category="injection")) == 2

    def test_filter_by_scanner(self):
        findings = self._mixed()
        assert len(normalizer.filter_findings(findings, scanner="code")) == 3

    def test_filter_by_normalized_file(self):
        findings = self._mixed()
        assert len(normalizer.filter_findings(findings, file="./b.py")) == 2

    def test_filters_compose(self):
        findings = self._mixed()
        result = normalizer.filter_findings(
            findings, severity="high", category="injection", file="b.py"
        )
        assert len(result) == 2

    def test_a_filter_matching_nothing_returns_an_empty_list(self):
        assert normalizer.filter_findings(self._mixed(), severity="info") == []

    def test_filtering_preserves_the_canonical_order(self):
        findings = self._mixed()
        result = normalizer.filter_findings(findings, severity=None)
        assert [f.severity for f in result] == ["critical", "high", "high", "low"]
