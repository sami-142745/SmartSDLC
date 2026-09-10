import pytest

from app.services.severity import (
    compute_severity_score,
    map_score_to_severity,
    score_findings,
)


def test_compute_severity_score_zero():
    assert compute_severity_score() == 0.0


def test_compute_severity_score_security_dominates():
    score = compute_severity_score(security_evidence=1.0, complexity=0.0, history=0.0)
    assert score == pytest.approx(0.6, abs=0.01)


def test_compute_severity_score_complexity_contributes():
    score = compute_severity_score(security_evidence=0.0, complexity=1.0, history=0.0)
    assert score == pytest.approx(0.3, abs=0.01)


def test_compute_severity_score_history_contributes():
    score = compute_severity_score(security_evidence=0.0, complexity=0.0, history=1.0)
    assert score == pytest.approx(0.1, abs=0.01)


def test_map_score_to_severity_critical():
    assert map_score_to_severity(0.95) == "critical"


def test_map_score_to_severity_high():
    assert map_score_to_severity(0.75) == "high"


def test_map_score_to_severity_medium():
    assert map_score_to_severity(0.55) == "medium"


def test_map_score_to_severity_low():
    assert map_score_to_severity(0.3) == "low"


def test_map_score_to_severity_info():
    assert map_score_to_severity(0.05) == "info"


def test_score_findings_empty():
    result = score_findings([])
    assert result["score"] == 0.0
    assert result["severity"] == "info"
    assert result["critical_flags"] == 0


def test_score_findings_high_security_heuristic():
    findings = [
        {
            "source": "heuristic",
            "severity": "low",
            "heuristic_severity": "high",
            "confidence": 0.8,
            "category": "security",
        }
    ]
    result = score_findings(findings)
    assert result["score"] > 0
    assert result["severity"] in ("medium", "high", "critical")


def test_score_findings_critical_heuristic_adds_flags():
    findings = [
        {
            "source": "heuristic",
            "severity": "low",
            "heuristic_severity": "critical",
            "confidence": 1.0,
            "category": "security",
        }
    ]
    result = score_findings(findings)
    assert result["critical_flags"] == 1
    assert result["score"] > 0


def test_score_findings_gemini_complexity_high_contributes():
    findings = [
        {
            "source": "gemini",
            "severity": "high",
            "category": "complexity",
            "confidence": 0.9,
        }
    ]
    result = score_findings(findings)
    assert result["score"] > 0
    assert result["critical_flags"] == 0


def test_score_findings_gemini_low_complexity_ignored():
    findings = [
        {
            "source": "gemini",
            "severity": "low",
            "category": "complexity",
            "confidence": 0.9,
        }
    ]
    result = score_findings(findings)
    assert result["score"] == 0.0


def test_score_findings_combined_sources():
    findings = [
        {
            "source": "heuristic",
            "severity": "low",
            "heuristic_severity": "high",
            "confidence": 0.7,
            "category": "security",
        },
        {
            "source": "gemini",
            "severity": "critical",
            "category": "complexity",
            "confidence": 1.0,
        },
    ]
    result = score_findings(findings)
    assert result["score"] > 0
    assert result["severity"] in ("medium", "high", "critical")
