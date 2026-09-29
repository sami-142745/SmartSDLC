"""Integration tests for the Sprint 3 review service and its HTTP surface.

These exercise the paths that decide whether a stored review is *honest*:
an empty diff must produce zero findings rather than an invented one, a
failed model call must degrade the status without discarding the diff, and a
finding for a file that is not part of the change must be dropped.
"""

import pytest

from app.schemas.ai_review import FILE_LEVEL_LINE, Review, ReviewFinding
from app.services import ai_review_repository, ai_review_service
from app.services.gemini_service import (
    AIReviewPayload,
    GeminiUnavailable,
    MalformedModelResponse,
)
from app.services.scm import ScmProvider

pytestmark = pytest.mark.asyncio

MODIFIED_PATCH = (
    "@@ -10,4 +10,5 @@ def handler():\n"
    "     context\n"
    "-    old_call()\n"
    "+    new_call()\n"
    "+    extra()\n"
    "     tail"
)

PR_FILES = [
    {
        "filename": "src/service.py",
        "status": "modified",
        "additions": 2,
        "deletions": 1,
        "patch": MODIFIED_PATCH,
    }
]

PR = {"number": 42, "title": "Refactor the handler", "head_sha": "deadbeef", "head": {"sha": "deadbeef"}}


class FakeClient:
    def __init__(self, files=None):
        self._files = PR_FILES if files is None else files

    async def get_pull_request(self, owner, repo, number):
        return dict(PR)

    async def get_pull_request_files(self, owner, repo, number):
        return self._files


def _payload(findings=None, assessment="Looks reasonable."):
    return AIReviewPayload.model_validate(
        {"summary": {"overall_assessment": assessment}, "findings": findings or []}
    )


def _install_ai(monkeypatch, result):
    """Replace the model call with a fixed result or raiser."""

    async def _fake(context):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(ai_review_service, "generate_ai_review", _fake)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_diff_produces_a_valid_empty_review(monkeypatch, fake_db):
    """No changed files must mean zero findings, never a fabricated one."""
    _install_ai(monkeypatch, AssertionError("the model must not be called"))
    review = await ai_review_service.run_ai_review(
        FakeClient(files=[]), "octocat", "Hello-World", 42, user_id=1
    )
    assert review.findings == []
    assert review.status == "complete"
    assert review.ai_status == "skipped"
    assert review.summary.assessment_score == 100
    assert review.review_id


@pytest.mark.asyncio
async def test_binary_only_diff_skips_the_model(monkeypatch, fake_db):
    _install_ai(monkeypatch, AssertionError("the model must not be called"))
    review = await ai_review_service.run_ai_review(
        FakeClient(files=[{"filename": "logo.png", "status": "modified"}]),
        "octocat",
        "Hello-World",
        42,
        user_id=1,
    )
    assert review.ai_status == "skipped"
    assert review.findings == []
    assert review.files[0].is_binary is True


@pytest.mark.asyncio
async def test_ai_findings_are_anchored_to_the_real_diff(monkeypatch, fake_db):
    _install_ai(
        monkeypatch,
        _payload(
            [
                {
                    "file": "src/service.py",
                    "line": 11,
                    "severity": "high",
                    "category": "bugs",
                    "title": "Off-by-one",
                    "description": "loop skips the last element",
                    "suggestion": "use <= n",
                    "original_code": "hallucinated quote",
                }
            ]
        ),
    )
    review = await ai_review_service.run_ai_review(
        FakeClient(), "octocat", "Hello-World", 42, user_id=1
    )
    assert review.status == "complete"
    assert len(review.findings) == 1
    finding = review.findings[0]
    assert finding.line == 11
    # The model's quoted code is discarded when it does not match the diff.
    assert finding.original_code == "new_call()"
    assert finding.source == "ai"


@pytest.mark.asyncio
async def test_finding_for_a_file_outside_the_diff_is_dropped(monkeypatch, fake_db):
    _install_ai(
        monkeypatch,
        _payload([{"file": "some/other/file.py", "line": 3, "title": "Not in this PR"}]),
    )
    review = await ai_review_service.run_ai_review(
        FakeClient(), "octocat", "Hello-World", 42, user_id=1
    )
    assert all(f.file != "some/other/file.py" for f in review.findings)


@pytest.mark.asyncio
async def test_unresolvable_line_degrades_to_file_level(monkeypatch, fake_db):
    _install_ai(
        monkeypatch,
        _payload([{"file": "src/service.py", "line": 9000, "title": "Vague"}]),
    )
    review = await ai_review_service.run_ai_review(
        FakeClient(), "octocat", "Hello-World", 42, user_id=1
    )
    ai_findings = [f for f in review.findings if f.source == "ai"]
    assert ai_findings and ai_findings[0].line == FILE_LEVEL_LINE
    assert ai_findings[0].is_file_level is True


@pytest.mark.asyncio
async def test_model_outage_keeps_the_diff_and_downgrades_to_partial(monkeypatch, fake_db):
    _install_ai(monkeypatch, GeminiUnavailable("Gemini API key is not configured"))
    review = await ai_review_service.run_ai_review(
        FakeClient(), "octocat", "Hello-World", 42, user_id=1
    )
    assert review.ai_status == "unavailable"
    assert review.status == "partial"
    assert review.error == "Gemini API key is not configured"
    # The deterministic work still happened.
    assert review.files and review.files[0].path == "src/service.py"
    assert review.summary.files_reviewed == 1


@pytest.mark.asyncio
async def test_malformed_model_output_is_distinguishable_from_an_outage(monkeypatch, fake_db):
    _install_ai(monkeypatch, MalformedModelResponse("Model response was not valid JSON"))
    review = await ai_review_service.run_ai_review(
        FakeClient(), "octocat", "Hello-World", 42, user_id=1
    )
    assert review.ai_status == "malformed"
    assert review.status == "partial"
    assert "not valid JSON" in review.error


@pytest.mark.asyncio
async def test_malformed_response_subclass_keeps_specific_status(monkeypatch, fake_db):
    """MalformedModelResponse must not be swallowed by the broader handler."""
    _install_ai(monkeypatch, MalformedModelResponse("bad envelope"))
    review = await ai_review_service.run_ai_review(
        FakeClient(), "octocat", "Hello-World", 42, user_id=1
    )
    assert review.ai_status == "malformed"


@pytest.mark.asyncio
async def test_duplicate_findings_across_sources_are_deduped(monkeypatch, fake_db):
    title = "Same  issue"
    _install_ai(
        monkeypatch,
        _payload(
            [
                {
                    "file": "src/service.py",
                    "line": 11,
                    "severity": "high",
                    "category": "bugs",
                    "title": title,
                    "description": "from the model",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        ai_review_service,
        "_heuristic_findings",
        lambda diff: [
            ReviewFinding(
                finding_id="h-1",
                file="src/service.py",
                line=11,
                severity="high",
                category="bugs",
                confidence=0.9,
                title="same issue",
                description="from the rules",
                source="heuristic",
            )
        ],
    )
    review = await ai_review_service.run_ai_review(
        FakeClient(), "octocat", "Hello-World", 42, user_id=1
    )
    # The richer AI finding wins; the heuristic duplicate is not double-counted.
    assert len(review.findings) == 1
    assert review.findings[0].description == "from the model"
    assert review.summary.total_findings == 1


@pytest.mark.asyncio
async def test_files_carry_their_finding_ids(monkeypatch, fake_db):
    _install_ai(
        monkeypatch,
        _payload([{"file": "src/service.py", "line": 11, "title": "Something"}]),
    )
    review = await ai_review_service.run_ai_review(
        FakeClient(), "octocat", "Hello-World", 42, user_id=1
    )
    assert review.files[0].finding_ids == [review.findings[0].finding_id]


@pytest.mark.asyncio
async def test_provider_metadata_is_persisted(monkeypatch, fake_db):
    _install_ai(monkeypatch, _payload())
    review = await ai_review_service.run_ai_review(
        FakeClient(), "octocat", "Hello-World", 42, provider=ScmProvider.github, user_id=7
    )
    assert review.owner == "octocat"
    assert review.repository == "Hello-World"
    assert review.pull_request_number == 42
    assert review.pull_request_title == "Refactor the handler"
    assert review.commit_sha == "deadbeef"
    assert review.provider == "github"
    assert review.duration_ms is not None


@pytest.mark.asyncio
async def test_suggestions_only_for_findings_that_propose_a_change(monkeypatch, fake_db):
    _install_ai(
        monkeypatch,
        _payload(
            [
                {"file": "src/service.py", "line": 11, "title": "Has a fix", "suggested_code": "safe()"},
                {"file": "src/service.py", "line": 12, "title": "No fix offered"},
            ]
        ),
    )
    review = await ai_review_service.run_ai_review(
        FakeClient(), "octocat", "Hello-World", 42, user_id=1
    )
    assert [s.title for s in review.suggestions] == ["Has a fix"]
    assert review.suggestions[0].suggested_code == "safe()"


@pytest.mark.asyncio
async def test_provider_errors_propagate(monkeypatch, fake_db):
    from app.services.scm import ScmAPIError

    class Failing(FakeClient):
        async def get_pull_request(self, owner, repo, number):
            raise ScmAPIError(404, "Not Found", "not_found")

    with pytest.raises(ScmAPIError):
        await ai_review_service.run_ai_review(Failing(), "o", "r", 1, user_id=1)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_saved_review_is_retrievable_with_its_findings(monkeypatch, fake_db):
    _install_ai(
        monkeypatch,
        _payload([{"file": "src/service.py", "line": 11, "severity": "critical", "category": "security", "title": "Injection"}]),
    )
    review = await ai_review_service.run_ai_review(
        FakeClient(), "octocat", "Hello-World", 42, user_id=1
    )

    stored = await ai_review_service.ai_review_repository.find_review_by_id(
        review.review_id, user_id=1
    )
    assert stored is not None
    findings = await ai_review_service.ai_review_repository.list_findings(review.review_id, user_id=1)
    assert len(findings) == 1
    assert findings[0]["title"] == "Injection"
    assert findings[0]["severity_rank"] == 0

    rehydrated = Review.model_validate(
        ai_review_service.ai_review_repository.serialize_review(stored, findings=findings)
    )
    assert rehydrated.review_id == review.review_id
    assert rehydrated.findings[0].finding_id == review.findings[0].finding_id


async def test_findings_default_sort_puts_most_severe_first(fake_db):
    """Severity must sort by rank, not alphabetically ("critical" < "info" < "low")."""
    review = Review(
        review_id="",
        owner="o",
        repository="r",
        pull_request_number=1,
        findings=[
            ReviewFinding(finding_id=f"f-{s}", file="a.py", line=1, severity=s, category="bugs", title=s)
            for s in ("low", "critical", "medium", "high", "info")
        ],
    )
    review_id = await ai_review_repository.save_review(review, user_id=1)
    ordered = await ai_review_repository.list_findings(review_id, user_id=1)
    assert [f["severity"] for f in ordered] == ["critical", "high", "medium", "low", "info"]


async def test_findings_can_be_sorted_by_an_explicit_field(fake_db):
    review = Review(
        review_id="",
        owner="o",
        repository="r",
        pull_request_number=1,
        findings=[
            ReviewFinding(finding_id="f1", file="a.py", line=30, severity="low", category="bugs", title="later", confidence=0.9),
            ReviewFinding(finding_id="f2", file="a.py", line=5, severity="low", category="bugs", title="earlier", confidence=0.1),
        ],
    )
    review_id = await ai_review_repository.save_review(review, user_id=1)
    by_line = await ai_review_repository.list_findings(review_id, user_id=1, sort="line")
    assert [f["line"] for f in by_line] == [5, 30]

    by_confidence = await ai_review_repository.list_findings(review_id, user_id=1, sort="confidence")
    assert [f["finding_id"] for f in by_confidence] == ["f1", "f2"]


async def test_findings_can_be_filtered(fake_db):
    review = Review(
        review_id="",
        owner="o",
        repository="r",
        pull_request_number=1,
        findings=[
            ReviewFinding(finding_id="f1", file="a.py", line=1, severity="critical", category="security", title="A"),
            ReviewFinding(finding_id="f2", file="b.py", line=2, severity="low", category="testing", title="B"),
        ],
    )
    review_id = await ai_review_repository.save_review(review, user_id=1)

    assert len(await ai_review_repository.list_findings(review_id, user_id=1, severity="critical")) == 1
    assert len(await ai_review_repository.list_findings(review_id, user_id=1, category="testing")) == 1
    assert len(await ai_review_repository.list_findings(review_id, user_id=1, file="a.py")) == 1
    assert len(await ai_review_repository.list_findings(review_id, user_id=1, severity="info")) == 0
    assert len(await ai_review_repository.list_findings(review_id, user_id=1)) == 2


def test_invalid_review_id_is_none_not_an_exception():
    from app.services.ai_review_repository import to_object_id

    assert to_object_id("not-an-object-id") is None
    assert to_object_id("") is None
    assert to_object_id(None) is None
    assert to_object_id("507f1f77bcf86cd799439011") is not None


def test_serialize_tolerates_unreadable_findings():
    from app.services.ai_review_repository import serialize_review

    payload = serialize_review(
        {"_id": "abc", "owner": "o", "repository": "r", "pull_request_number": 1},
        findings=[{"finding_id": "ok", "file": "a.py", "line": 1, "title": "fine"}, "junk", {"no_id": 1}],
    )
    assert payload["review_id"] == "abc"
    assert len(payload["findings"]) == 1
    assert payload["schema_version"] == 2
    assert payload["ai_status"] == "complete"


def test_serialize_handles_missing_document():
    from app.services.ai_review_repository import serialize_review

    assert serialize_review(None) is None

