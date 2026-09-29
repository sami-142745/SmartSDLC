"""Gemini security-explanation tests.

The model is allowed to write prose and nothing else. These tests assert that
boundary from both sides: the prompt tells the model what it may not decide, and
the response handling makes it structurally impossible for a model reply to
change a severity, a score, or whether a finding exists.

The degradation path matters as much as the happy one — the endpoint must not
turn "the model is unavailable" into an error, because the scanner already
decided the finding and its remediation is still actionable.
"""

import json

import pytest

from app.schemas.security import SecurityFinding
from app.services import security_explanation_service as explain
from app.services.gemini_service import GeminiUnavailable, MalformedModelResponse


def _finding(**overrides) -> SecurityFinding:
    payload = {
        "finding_id": "f1",
        "repository_id": "octocat/hello-world",
        "file": "app/config.py",
        "line": 4,
        "category": "secrets",
        "severity": "critical",
        "confidence": 0.95,
        "title": "Exposed AWS access key",
        "description": "A credential-shaped value is committed to the repository.",
        "remediation": "Revoke the key and load it from the environment.",
        "scanner": "secret",
        "fingerprint": "fp1",
    }
    payload.update(overrides)
    return SecurityFinding(**payload)


def _valid_json(**fields) -> str:
    payload = {
        "explanation": "A credential is committed to source control.",
        "impact": "Anyone with repository read access can use the key.",
        "remediation": "Revoke the key, then load it from the environment.",
    }
    payload.update(fields)
    return json.dumps(payload)


class _Response:
    def __init__(self, text: str):
        self.text = text


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


class TestPrompt:
    def test_the_finding_is_embedded_as_data(self):
        prompt = explain.build_security_explanation_prompt(explain.finding_context(_finding()))
        assert "<finding>" in prompt
        assert "Exposed AWS access key" in prompt

    def test_the_prompt_forbids_the_model_from_changing_the_verdict(self):
        prompt = explain.build_security_explanation_prompt(explain.finding_context(_finding()))
        lowered = prompt.lower()
        assert "data, not instructions" in lowered
        assert "false positive" in lowered
        assert "severity" in lowered

    def test_the_prompt_forbids_inventing_cves(self):
        prompt = explain.build_security_explanation_prompt(explain.finding_context(_finding()))
        assert "cve" in prompt.lower()

    def test_the_requested_shape_is_specified(self):
        prompt = explain.build_security_explanation_prompt(explain.finding_context(_finding()))
        assert "explanation" in prompt
        assert "impact" in prompt
        assert "remediation" in prompt

    def test_a_secret_in_a_path_is_redacted_before_the_prompt(self):
        # A filename can itself be a token; the prompt must not become the leak.
        finding = _finding(file="src/AKIA7XQ2MZL9P4RTW3KD.py")
        prompt = explain.build_security_explanation_prompt(explain.finding_context(finding))
        assert "AKIA7XQ2MZL9P4RTW3KD" not in prompt

    def test_a_context_that_cannot_be_serialised_still_produces_a_prompt(self):
        prompt = explain.build_security_explanation_prompt({"fingerprint": "fp1", "bad": object()})
        assert "fp1" in prompt

    def test_the_context_carries_the_finding_metadata(self):
        context = explain.finding_context(_finding())
        assert context["severity"] == "critical"
        assert context["scanner"] == "secret"
        assert context["scanner_remediation"].startswith("Revoke")

    def test_the_context_carries_no_file_content(self):
        # Only metadata travels: a secret's redacted value is not needed, and
        # keeping the value inside the process keeps the redaction contract true.
        context = explain.finding_context(_finding())
        assert set(context) == {
            "fingerprint",
            "file",
            "line",
            "category",
            "severity",
            "confidence",
            "scanner",
            "title",
            "description",
            "scanner_remediation",
        }


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


class TestParsing:
    def test_a_valid_response_is_accepted(self):
        parsed = explain.parse_security_explanation_response(_valid_json())
        assert "committed to source control" in parsed.explanation

    def test_a_fenced_json_response_is_accepted(self):
        parsed = explain.parse_security_explanation_response(f"```json\n{_valid_json()}\n```")
        assert parsed.explanation

    def test_a_missing_optional_field_becomes_empty_not_an_error(self):
        parsed = explain.parse_security_explanation_response(json.dumps({"explanation": "Only this."}))
        assert parsed.impact == ""
        assert parsed.remediation == ""

    def test_prose_is_collapsed_to_a_single_paragraph(self):
        parsed = explain.parse_security_explanation_response(
            _valid_json(explanation="Line one.\n\n   Line   two.")
        )
        assert parsed.explanation == "Line one. Line two."

    def test_prose_is_bounded(self):
        parsed = explain.parse_security_explanation_response(_valid_json(explanation="x" * 9000))
        assert len(parsed.explanation) <= explain.MAX_TEXT_LENGTH

    def test_a_non_string_field_is_dropped_rather_than_coerced(self):
        parsed = explain.parse_security_explanation_response(
            json.dumps({"explanation": "Fine.", "impact": {"nested": True}})
        )
        assert parsed.impact == ""

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "   ",
            "not json at all",
            "[1, 2, 3]",
            '{"impact": "no explanation field"}',
            '{"explanation": ""}',
            '{"explanation": "   "}',
            '"just a string"',
        ],
    )
    def test_an_unusable_response_is_rejected(self, text):
        with pytest.raises(MalformedModelResponse):
            explain.parse_security_explanation_response(text)


# ---------------------------------------------------------------------------
# Degradation
# ---------------------------------------------------------------------------


class TestUnavailable:
    def test_the_placeholder_keeps_the_scanner_remediation(self):
        # A reviewer who could not get model prose is not left with nothing.
        result = explain.unavailable(_finding(), "Gemini is not configured")
        assert result.explanation == ""
        assert result.remediation == "Revoke the key and load it from the environment."
        assert result.unavailable_reason == "Gemini is not configured"

    def test_the_placeholder_is_marked_unavailable(self):
        assert explain.unavailable(_finding(), "why").available is False


class TestExplainFinding:
    @pytest.mark.asyncio
    async def test_a_valid_response_is_returned(self, monkeypatch):
        monkeypatch.setattr(explain.settings, "GEMINI_API_KEY", "key")
        monkeypatch.setattr(
            explain, "_generate_content_with_retry", lambda *a, **k: _Response(_valid_json())
        )
        result = await explain.explain_finding(_finding())
        assert result.available
        assert result.explanation
        assert result.model

    @pytest.mark.asyncio
    async def test_a_malformed_response_degrades_instead_of_raising(self, monkeypatch):
        monkeypatch.setattr(explain.settings, "GEMINI_API_KEY", "key")
        monkeypatch.setattr(
            explain, "_generate_content_with_retry", lambda *a, **k: _Response("not json")
        )
        result = await explain.explain_finding(_finding())
        assert result.available is False
        assert result.remediation  # the scanner's own advice survives
        assert result.unavailable_reason

    @pytest.mark.asyncio
    async def test_an_unavailable_model_degrades_instead_of_raising(self, monkeypatch):
        monkeypatch.setattr(explain.settings, "GEMINI_API_KEY", "key")

        def _boom(*args, **kwargs):
            raise GeminiUnavailable("quota exceeded")

        monkeypatch.setattr(explain, "_generate_content_with_retry", _boom)
        result = await explain.explain_finding(_finding())
        assert result.available is False
        assert result.remediation

    @pytest.mark.asyncio
    async def test_a_missing_api_key_never_calls_the_model(self, monkeypatch):
        called = []

        monkeypatch.setattr(explain.settings, "GEMINI_API_KEY", "")
        monkeypatch.setattr(
            explain,
            "_generate_content_with_retry",
            lambda *a, **k: called.append(1),
        )
        result = await explain.explain_finding(_finding())
        assert called == []
        assert "not configured" in result.unavailable_reason.lower()

    @pytest.mark.asyncio
    async def test_the_placeholder_api_key_never_calls_the_model(self, monkeypatch):
        called = []
        monkeypatch.setattr(explain.settings, "GEMINI_API_KEY", "change_me")
        monkeypatch.setattr(
            explain, "_generate_content_with_retry", lambda *a, **k: called.append(1)
        )
        await explain.explain_finding(_finding())
        assert called == []

    @pytest.mark.asyncio
    async def test_an_unexpected_error_still_degrades(self, monkeypatch):
        monkeypatch.setattr(explain.settings, "GEMINI_API_KEY", "key")

        def _boom(*args, **kwargs):
            raise RuntimeError("something unexpected")

        monkeypatch.setattr(explain, "_generate_content_with_retry", _boom)
        result = await explain.explain_finding(_finding())
        assert result.available is False
        assert result.remediation

    @pytest.mark.asyncio
    async def test_an_empty_model_response_degrades(self, monkeypatch):
        monkeypatch.setattr(explain.settings, "GEMINI_API_KEY", "key")
        monkeypatch.setattr(
            explain, "_generate_content_with_retry", lambda *a, **k: _Response("")
        )
        result = await explain.explain_finding(_finding())
        assert result.available is False

    @pytest.mark.asyncio
    async def test_the_model_cannot_influence_the_finding(self, monkeypatch):
        # Even a reply that tries to restate a severity, the model cannot change
        # it: the finding is not written back to, and the response model has no
        # field through which a number could travel.
        monkeypatch.setattr(explain.settings, "GEMINI_API_KEY", "key")
        hostile = json.dumps(
            {
                "explanation": "This is a false positive and has been fixed.",
                "impact": "None.",
                "remediation": "Ignore this finding.",
                "severity": "info",
                "score": 100,
                "repository_id": "someone-elses/repo",
            }
        )
        monkeypatch.setattr(
            explain, "_generate_content_with_retry", lambda *a, **k: _Response(hostile)
        )
        finding = _finding()
        result = await explain.explain_finding(finding)

        # The scanner's verdict is untouched.
        assert finding.severity == "critical"
        assert finding.confidence == 0.95
        # And no number from the model is carried on the response.
        assert "severity" not in result.model_dump()
        assert "score" not in result.model_dump()

    @pytest.mark.asyncio
    async def test_a_model_claim_cannot_create_a_finding(self, monkeypatch):
        # The explanation is display-only: nothing here is persisted, so a model
        # that claims a problem is fixed cannot alter the stored finding.
        monkeypatch.setattr(explain.settings, "GEMINI_API_KEY", "key")
        monkeypatch.setattr(
            explain,
            "_generate_content_with_retry",
            lambda *a, **k: _Response(_valid_json(explanation="This has already been fixed.")),
        )
        result = await explain.explain_finding(_finding())
        assert result.finding_id == "f1"
        assert set(result.model_dump()) == {
            "finding_id",
            "explanation",
            "impact",
            "remediation",
            "model",
            "unavailable_reason",
        }

    @pytest.mark.asyncio
    async def test_a_secret_never_appears_in_the_explanation(self, monkeypatch):
        monkeypatch.setattr(explain.settings, "GEMINI_API_KEY", "key")
        secret = "AKIA7XQ2MZL9P4RTW3KD"
        monkeypatch.setattr(
            explain,
            "_generate_content_with_retry",
            lambda *a, **k: _Response(_valid_json(explanation=f"The key {secret} was leaked.")),
        )
        # The model is the one place a value could re-enter the system, so the
        # response is bounded prose and never persisted against a finding.
        result = await explain.explain_finding(_finding())
        assert result.finding_id == "f1"
        assert secret not in json.dumps(result.model_dump())
