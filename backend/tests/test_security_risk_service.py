"""Risk calculator tests.

The property under test throughout is *determinism*: the same findings must
always produce the same numbers, and no model may participate. The weights are
the ones the Security page has always used (critical 8, high 3, medium 1), and
the last test in the file pins that they have not drifted.
"""

import pytest

from app.schemas.security import SEVERITIES, SecurityFinding
from app.services import security_risk_service as risk


def _finding(severity: str = "medium", **overrides) -> SecurityFinding:
    payload = {
        "repository_id": "octo/repo",
        "file": "app/config.py",
        "line": 4,
        "category": "secrets",
        "severity": severity,
        "confidence": 0.9,
        "title": "Hardcoded credential",
        "description": "d",
        "remediation": "r",
        "scanner": "secret",
        "fingerprint": "abc123",
    }
    payload.update(overrides)
    return SecurityFinding(**payload)


def _findings(*severities) -> list[SecurityFinding]:
    return [_finding(severity, fingerprint=f"fp{index}") for index, severity in enumerate(severities)]


class TestWeights:
    def test_the_weights_are_the_ones_the_security_page_uses(self):
        assert risk.SEVERITY_WEIGHTS["critical"] == 8
        assert risk.SEVERITY_WEIGHTS["high"] == 3
        assert risk.SEVERITY_WEIGHTS["medium"] == 1

    def test_low_and_info_contribute_nothing(self):
        # Weighting a note as heavily as a real problem would let a repository of
        # informational chatter score worse than one with an exploitable finding.
        assert risk.SEVERITY_WEIGHTS["low"] == 0
        assert risk.SEVERITY_WEIGHTS["info"] == 0

    def test_weighted_risk_sums_the_weights(self):
        assert risk.weighted_risk(_findings("critical", "high", "medium")) == 12

    def test_weighted_risk_of_nothing_is_zero(self):
        assert risk.weighted_risk([]) == 0

    def test_exposure_and_weighted_risk_are_the_same_number(self):
        findings = _findings("critical", "critical", "high")
        assert risk.exposure_score(findings) == risk.weighted_risk(findings) == 19

    def test_an_unknown_severity_is_coerced_to_medium_by_the_contract(self):
        # The finding model normalises the label before scoring ever sees it, so
        # an odd string from a scanner is a medium rather than a zero-weighted
        # finding that would hide real exposure.
        assert _finding("nonsense").severity == "medium"
        assert risk.weighted_risk([_finding("nonsense")]) == 1

    def test_the_weights_are_lookup_safe_for_any_band(self):
        # A severity outside the vocabulary must not raise out of the sum.
        assert risk.SEVERITY_WEIGHTS.get("nonexistent", 0) == 0


class TestPostureScore:
    def test_a_clean_repository_scores_the_ceiling(self):
        assert risk.posture_score([]) == risk.SCORE_CEILING == 100

    def test_the_score_never_falls_below_the_floor(self):
        # The penalty is a per-finding mean, so an all-critical repository is the
        # worst case. Past the 200-finding cap the divisor is fixed and the score
        # falls linearly, reaching the floor at 2 500 criticals and no further.
        assert risk.posture_score(_findings(*["critical"] * 2500)) == risk.SCORE_FLOOR
        assert risk.posture_score(_findings(*["critical"] * 5000)) >= risk.SCORE_FLOOR

    def test_a_single_critical_costs_eight_points(self):
        assert risk.posture_score(_findings("critical")) == 92

    def test_a_single_high_costs_three_points(self):
        assert risk.posture_score(_findings("high")) == 97

    def test_a_single_medium_costs_one_point(self):
        assert risk.posture_score(_findings("medium")) == 99

    def test_low_and_info_do_not_move_the_score(self):
        assert risk.posture_score(_findings("low", "info")) == 100

    def test_the_penalty_is_shared_across_the_findings(self):
        # Two findings means the penalty is halved, so a lone critical at 92
        # becomes 96 rather than 84.
        assert risk.posture_score(_findings("critical", "low")) == 96

    def test_the_score_never_rises_with_severity(self):
        # critical, high, medium, low, info: the most severe band must not score
        # better than the one below it.
        scores = [risk.posture_score(_findings(severity)) for severity in SEVERITIES]
        assert scores == sorted(scores)

    def test_the_finding_cap_bounds_the_penalty_ratio(self):
        # Up to the cap the penalty is a true mean (8 for all criticals, so 92).
        # Past it the divisor stops growing, so 400 criticals cost 16 points
        # rather than the 8 a true mean would give.
        assert risk.posture_score(_findings(*(["critical"] * 200))) == 92
        assert risk.posture_score(_findings(*(["critical"] * 400))) == 84


class TestDeterminism:
    def test_repeated_summaries_are_identical(self):
        findings = _findings("critical", "high", "medium", "low", "info")
        first = risk.summarize(findings).as_response()
        second = risk.summarize(list(reversed(findings))).as_response()
        assert first == second

    def test_recomputing_one_summary_gives_the_same_numbers(self):
        findings = _findings("critical", "high", "medium")
        assert risk.summarize(findings).as_response() == risk.summarize(findings).as_response()

    def test_summarize_reports_the_posture_the_page_will_show(self):
        assert risk.summarize(_findings("critical")).posture_score == 92

    def test_an_empty_summary_is_a_perfect_score_not_an_error(self):
        summary = risk.summarize([])
        assert summary.total_findings == 0
        assert summary.posture_score == 100
        assert summary.weighted_risk == 0


class TestSummary:
    def test_severity_counts_cover_every_band(self):
        summary = risk.summarize(_findings("critical", "high", "high"))
        assert summary.severity_counts.critical == 1
        assert summary.severity_counts.high == 2
        assert summary.severity_counts.medium == 0

    def test_severity_counts_include_the_absent_bands(self):
        # A client rendering a legend should not have to special-case a band with
        # no findings.
        assert set(risk.severity_counts([]).as_dict()) == set(SEVERITIES)

    def test_total_is_the_sum_of_the_severity_counts(self):
        findings = _findings("critical", "high", "medium", "low", "info")
        summary = risk.summarize(findings)
        assert summary.total_findings == summary.severity_counts.total() == 5

    def test_category_distribution_is_reported(self):
        findings = [
            _finding("high", category="injection", fingerprint="a"),
            _finding("high", category="injection", fingerprint="b"),
            _finding("low", category="crypto", fingerprint="c"),
        ]
        assert risk.summarize(findings).category_distribution == {"injection": 2, "crypto": 1}

    def test_scanner_distribution_is_reported(self):
        findings = [
            _finding("high", scanner="secret", fingerprint="a"),
            _finding("low", scanner="code", fingerprint="b"),
            _finding("low", scanner="code", fingerprint="c"),
        ]
        assert risk.summarize(findings).scanner_distribution == {"secret": 1, "code": 2}

    def test_findings_by_file_is_counted_per_file(self):
        findings = [
            _finding("high", file="a.py", fingerprint="a"),
            _finding("high", file="a.py", fingerprint="b"),
            _finding("low", file="b.py", fingerprint="c"),
        ]
        assert risk.summarize(findings).findings_by_file == {"a.py": 2, "b.py": 1}

    def test_the_scan_operational_counters_are_carried(self):
        summary = risk.summarize(
            _findings("high"), files_scanned=12, files_skipped=4, dependencies_analyzed=3
        )
        assert summary.files_scanned == 12
        assert summary.files_skipped == 4
        assert summary.dependencies_analyzed == 3

    def test_an_empty_distribution_is_an_empty_dict_not_a_missing_key(self):
        assert risk.summarize([]).category_distribution == {}
        assert risk.summarize([]).findings_by_file == {}


class TestGrade:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (100, "healthy"),
            (90, "healthy"),
            (89, "watch"),
            (70, "watch"),
            (69, "at_risk"),
            (40, "at_risk"),
            (39, "critical"),
            (0, "critical"),
        ],
    )
    def test_the_band_boundaries(self, score, expected):
        assert risk.grade(score) == expected

    def test_the_grades_are_ordered_from_best_to_worst(self):
        scores = [100, 80, 50, 10]
        assert [risk.grade(score) for score in scores] == [
            "healthy",
            "watch",
            "at_risk",
            "critical",
        ]


class TestRiskiestFiles:
    def test_the_worst_file_comes_first(self):
        findings = [
            _finding("low", file="busy.py", fingerprint="a"),
            _finding("low", file="busy.py", fingerprint="b"),
            _finding("low", file="busy.py", fingerprint="c"),
            _finding("low", file="quiet.py", fingerprint="d"),
        ]
        assert risk.riskiest_files(findings, limit=1) == ["busy.py"]

    def test_ties_break_on_path_so_the_list_is_stable(self):
        findings = [
            _finding("low", file="b.py", fingerprint="a"),
            _finding("low", file="a.py", fingerprint="b"),
        ]
        assert risk.riskiest_files(findings) == ["a.py", "b.py"]

    def test_no_findings_means_no_risky_files(self):
        assert risk.riskiest_files([]) == []
