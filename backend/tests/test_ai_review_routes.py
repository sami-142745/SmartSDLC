"""HTTP contract tests for the Sprint 3 AI review endpoints.

Verifies the three documented paths, the root/``/api`` dual registration, the
error mapping, and — importantly — that the new ``/reviews/{review_id}`` route
does not shadow the legacy ``/reviews/{owner}/{repo}/{number}`` surface it was
mounted alongside.
"""

import pytest

from app.schemas.ai_review import Review, ReviewFinding, ReviewSummary
from app.services import ai_review_repository, ai_review_service
from app.services.scm import ScmAPIError
from app.services.jwt_service import create_access_token

FINDING = ReviewFinding(
    finding_id="a-1",
    file="src/service.py",
    line=11,
    severity="critical",
    category="security",
    confidence=0.9,
    title="SQL injection",
    description="string is concatenated into a query",
    suggestion="use parameters",
    original_code="q = 'SELECT ' + name",
    suggested_code="q = 'SELECT ?'",
    source="ai",
)


def _review(review_id="507f1f77bcf86cd799439011", **overrides) -> Review:
    payload = {
        "review_id": review_id,
        "owner": "octocat",
        "repository": "Hello-World",
        "pull_request_number": 42,
        "pull_request_title": "Fix bug",
        "commit_sha": "abc123",
        "provider": "github",
        "status": "complete",
        "ai_status": "complete",
        "summary": ReviewSummary(assessment_score=72, total_findings=1),
        "files": [],
        "findings": [FINDING],
    }
    payload.update(overrides)
    return Review.model_validate(payload)


@pytest.fixture
def ai_review_db(monkeypatch):
    """Point the v2 repository at an in-memory database."""
    from tests.conftest import FakeDb

    db = FakeDb()
    monkeypatch.setattr(ai_review_repository, "get_db", lambda: db)
    return db


#: The user id the seeded review belongs to.
OWNER_ID = 42

#: A different, fully authenticated account. It has a valid token and a
#: connected provider, so it passes every dependency except ownership.
INTRUDER_ID = 99

_USERS = {
    OWNER_ID: {"login": "octocat", "name": "Octo Cat", "github_access_token": "gho_owner_token"},
    INTRUDER_ID: {
        "login": "intruder",
        "name": "Nosy Parker",
        "github_access_token": "gho_intruder_token",
    },
}


def _bearer(github_id: int) -> dict[str, str]:
    token = create_access_token({"sub": str(github_id), "login": _USERS[github_id]["login"]})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def two_users(monkeypatch):
    """Resolve either of two real users by id, so ownership can be exercised.

    Ownership tests need a second valid session, which the shared `auth_headers`
    fixture cannot provide: it pins every request to one user id, so a test
    using both would silently exercise the same account twice.
    """

    async def known_user(github_id):
        profile = _USERS.get(int(github_id))
        if profile is None:
            return None
        return {"_id": f"{int(github_id):024d}", "github_id": int(github_id), **profile}

    monkeypatch.setattr("app.services.security.get_user_by_github_id", known_user)
    return {
        "owner": _bearer(OWNER_ID),
        "intruder": _bearer(INTRUDER_ID),
    }


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/reviews"),
        ("post", "/api/reviews"),
        ("get", "/reviews/507f1f77bcf86cd799439011"),
        ("get", "/reviews/507f1f77bcf86cd799439011/findings"),
    ],
)
def test_all_endpoints_require_authentication(client, method, path):
    payload = {"owner": "o", "repository": "r", "pull_request_number": 1} if method == "post" else None
    response = getattr(client, method)(path, json=payload) if payload else getattr(client, method)(path)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /reviews
# ---------------------------------------------------------------------------


def test_create_review_returns_201_with_the_full_review(client, auth_headers, monkeypatch, ai_review_db):
    async def _fake_run(client_, owner, repo, number, **kwargs):
        return _review(review_id="507f1f77bcf86cd799439011")

    monkeypatch.setattr(ai_review_service, "run_ai_review", _fake_run)
    response = client.post(
        "/reviews",
        json={"owner": "octocat", "repository": "Hello-World", "pull_request_number": 42},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["owner"] == "octocat"
    assert body["pull_request_number"] == 42
    assert body["summary"]["assessment_score"] == 72
    assert body["summary"]["assessment_label"] == "AI review assessment"
    assert body["findings"][0]["finding_id"] == "a-1"
    assert body["findings"][0]["suggested_code"] == "q = 'SELECT ?'"
    assert body["schema_version"] == 2


def test_create_review_is_available_under_the_api_prefix(client, auth_headers, monkeypatch, ai_review_db):
    async def _fake_run(client_, owner, repo, number, **kwargs):
        return _review(review_id="507f1f77bcf86cd799439011")

    monkeypatch.setattr(ai_review_service, "run_ai_review", _fake_run)
    response = client.post(
        "/api/reviews",
        json={"owner": "octocat", "repository": "Hello-World", "pull_request_number": 42},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["review_id"] == "507f1f77bcf86cd799439011"


@pytest.mark.parametrize(
    "payload",
    [
        {"repository": "r", "pull_request_number": 1},  # no owner
        {"owner": "o", "pull_request_number": 1},  # no repository
        {"owner": "o", "repository": "r"},  # no pull request number
        {"owner": "o", "repository": "r", "pull_request_number": 0},  # below range
        {"owner": "", "repository": "r", "pull_request_number": 1},  # empty
        {"owner": "o", "repository": "r", "pull_request_number": 1, "surprise": True},  # extra
    ],
)
def test_create_review_validates_its_body(client, auth_headers, payload, ai_review_db):
    assert client.post("/reviews", json=payload, headers=auth_headers).status_code == 422


def test_create_review_defaults_an_unknown_provider_to_github(client, auth_headers, monkeypatch, ai_review_db):
    seen = {}

    async def _fake_run(client_, owner, repo, number, provider=None, **kwargs):
        seen["provider"] = provider.value
        return _review()

    monkeypatch.setattr(ai_review_service, "run_ai_review", _fake_run)
    client.post(
        "/reviews",
        json={"owner": "o", "repository": "r", "pull_request_number": 1, "provider": "bitbucket"},
        headers=auth_headers,
    )
    assert seen["provider"] == "github"


@pytest.mark.parametrize(
    ("category", "status"),
    [
        ("not_found", 404),
        ("rate_limit", 429),
        ("authentication", 401),
        ("server", 502),
        ("network", 503),
    ],
)
def test_create_review_maps_provider_errors(client, auth_headers, monkeypatch, ai_review_db, category, status):
    async def _failing(client_, owner, repo, number, **kwargs):
        raise ScmAPIError(500, "provider exploded", category)

    monkeypatch.setattr(ai_review_service, "run_ai_review", _failing)
    response = client.post(
        "/reviews",
        json={"owner": "o", "repository": "r", "pull_request_number": 1},
        headers=auth_headers,
    )
    assert response.status_code == status
    assert response.json()["detail"] == "provider exploded"


def test_create_review_surfaces_a_ai_failure_as_a_stored_partial_review(client, auth_headers, monkeypatch, ai_review_db):
    """A model outage must still return a usable review, not a 5xx."""

    async def _failing(client_, owner, repo, number, **kwargs):
        return _review(status="partial", ai_status="unavailable", error="Gemini API key is not configured")

    monkeypatch.setattr(ai_review_service, "run_ai_review", _failing)
    response = client.post(
        "/reviews",
        json={"owner": "o", "repository": "r", "pull_request_number": 1},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["ai_status"] == "unavailable"
    assert response.json()["error"] == "Gemini API key is not configured"


# ---------------------------------------------------------------------------
# GET /reviews/{id}
# ---------------------------------------------------------------------------


def test_get_review_returns_the_stored_review(client, auth_headers, ai_review_db):
    review_id = _seed(ai_review_db)
    response = client.get(f"/reviews/{review_id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["review_id"] == review_id
    assert body["owner"] == "octocat"
    assert body["summary"]["assessment_label"] == "AI review assessment"
    assert len(body["findings"]) == 3
    # Most severe first, by rank rather than alphabetically.
    assert [f["severity"] for f in body["findings"]] == ["critical", "medium", "low"]
    assert body["findings"][0]["category"] == "security"
    assert body["findings"][0]["original_code"] == "x"
    # Internal denormalized keys never reach the API.
    assert "severity_rank" not in body["findings"][0]
    assert "user_id" not in body["findings"][0]
    assert "_id" not in body


def test_get_review_works_under_the_api_prefix(client, auth_headers, ai_review_db):
    review_id = _seed(ai_review_db)
    assert client.get(f"/api/reviews/{review_id}", headers=auth_headers).status_code == 200


@pytest.mark.parametrize("review_id", ["507f1f77bcf86cd799439011", "not-an-object-id", "0" * 24, "%20"])
def test_get_review_404s_for_unknown_and_malformed_ids(client, auth_headers, review_id, ai_review_db):
    """An invalid id and a missing one are indistinguishable: both 404."""
    response = client.get(f"/reviews/{review_id}", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Review not found"


# ---------------------------------------------------------------------------
# GET /reviews/{id}/findings
# ---------------------------------------------------------------------------


def test_get_findings_returns_sorted_findings(client, auth_headers, ai_review_db):
    review_id = _seed(ai_review_db)
    response = client.get(f"/reviews/{review_id}/findings", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["review_id"] == review_id
    assert body["total"] == 3
    assert [f["severity"] for f in body["findings"]] == ["critical", "medium", "low"]
    assert "severity_rank" not in body["findings"][0]
    assert "user_id" not in body["findings"][0]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("severity=critical", 1),
        ("severity=low", 1),
        ("severity=info", 0),
        ("category=security", 1),
        ("category=testing", 2),
        ("category=performance", 0),
        ("file=src/service.py", 1),
        ("file=other.py", 0),
        ("sort=line", 3),
        ("sort=confidence", 3),
    ],
)
def test_get_findings_filters_and_sorts(client, auth_headers, ai_review_db, query, expected):
    review_id = _seed(ai_review_db)
    response = client.get(f"/reviews/{review_id}/findings?{query}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == expected


@pytest.mark.parametrize(
    "query",
    ["severity=apocalyptic", "category=architecture", "sort=password", "sort=; drop table"],
)
def test_get_findings_rejects_unknown_filter_values(client, auth_headers, ai_review_db, query):
    """A bad filter must be a 422, not a misleading empty list."""
    review_id = _seed(ai_review_db)
    response = client.get(f"/reviews/{review_id}/findings?{query}", headers=auth_headers)
    assert response.status_code == 422


def test_get_findings_404s_for_an_unknown_review(client, auth_headers, ai_review_db):
    assert client.get("/reviews/507f1f77bcf86cd799439011/findings", headers=auth_headers).status_code == 404


# ---------------------------------------------------------------------------
# No regression against the legacy surface
# ---------------------------------------------------------------------------


def test_legacy_review_routes_are_unaffected(client, auth_headers, monkeypatch):
    """The new /reviews/{review_id} route must not shadow the legacy 4-segment path."""

    async def _fake_run(gh, o, r, n, user_id=None, **kwargs):
        return {"status": "complete", "repository": r, "owner": o, "pull_request_number": n, "findings": []}

    monkeypatch.setattr("app.routers.reviews.run_review", _fake_run)
    assert client.post("/reviews/octocat/Hello-World/12", headers=auth_headers).status_code == 200


def test_feedback_history_route_still_wins_over_the_review_id_route():
    """``/reviews/feedback`` and ``/reviews/{review_id}`` are both two segments.

    FastAPI matches in registration order, and the legacy router is included
    first, so the static path must keep resolving to the feedback handler. This
    is asserted on the route table rather than over HTTP so the check does not
    need a database.
    """
    from app.main import app

    two_segment_review_routes = [
        (route.path, route.name)
        for route in app.routes
        if getattr(route, "path", "").startswith("/reviews/") and route.path.count("/") == 2
    ]
    assert ("/reviews/feedback", "list_feedback_history") in two_segment_review_routes
    assert ("/reviews/{review_id}", "get_review") in two_segment_review_routes
    order = [name for _, name in two_segment_review_routes]
    assert order.index("list_feedback_history") < order.index("get_review")


def test_review_endpoints_are_under_both_the_root_and_the_api_prefix():
    from app.main import app

    paths = {getattr(route, "path", "") for route in app.routes}
    for path in ("/reviews", "/reviews/{review_id}", "/reviews/{review_id}/findings"):
        assert path in paths
        assert f"/api{path}" in paths


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _seed(db) -> str:
    """Write one review with three findings directly into the fake database."""
    review_id = "507f1f77bcf86cd799439011"
    db["ai_reviews"].docs.append(
        {
            "_id": review_id,
            "schema_version": 2,
            "status": "complete",
            "ai_status": "complete",
            "owner": "octocat",
            "repository": "Hello-World",
            "pull_request_number": 42,
            "pull_request_title": "Fix bug",
            "commit_sha": "abc123",
            "provider": "github",
            "summary": ReviewSummary(assessment_score=72, total_findings=3).model_dump(mode="json"),
            "files": [],
            "suggestions": [],
            "user_id": 42,
        }
    )
    severities = ["critical", "low", "medium"]
    for index, severity in enumerate(severities):
        db["ai_review_findings"].docs.append(
            {
                "review_id": review_id,
                "finding_id": f"a-{index}",
                "file": "src/service.py" if index == 0 else f"other{index}.py",
                "line": 11,
                "severity": severity,
                "severity_rank": ["critical", "high", "medium", "low", "info"].index(severity),
                "category": "security" if index == 0 else "testing",
                "confidence": 0.5 + index / 10,
                "title": f"Finding {index}",
                "description": "d",
                "suggestion": "s",
                "original_code": "x",
                "suggested_code": "y",
                "source": "ai",
                "user_id": 42,
            }
        )
    return review_id


# ------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Ownership: a review is readable only by the account that created it
# ---------------------------------------------------------------------------


def test_owner_can_read_their_own_review(client, two_users, ai_review_db):
    review_id = _seed(ai_review_db)

    response = client.get(f"/reviews/{review_id}", headers=two_users["owner"])

    assert response.status_code == 200
    body = response.json()
    assert body["review_id"] == review_id
    assert body["owner"] == "octocat"
    assert len(body["findings"]) == 3


def test_owner_can_read_their_own_findings(client, two_users, ai_review_db):
    review_id = _seed(ai_review_db)

    response = client.get(f"/reviews/{review_id}/findings", headers=two_users["owner"])

    assert response.status_code == 200
    body = response.json()
    assert body["review_id"] == review_id
    assert body["total"] == 3
    assert [f["severity"] for f in body["findings"]] == ["critical", "medium", "low"]


def test_another_authenticated_user_cannot_read_someone_elses_review(
    client, two_users, ai_review_db
):
    """A valid token and connected account are not enough: ownership is required."""
    review_id = _seed(ai_review_db)

    response = client.get(f"/reviews/{review_id}", headers=two_users["intruder"])

    assert response.status_code == 404
    assert response.json() == {"detail": "Review not found"}
    # Nothing from the review leaks, not even a partial body.
    assert "octocat" not in response.text
    assert "Finding 0" not in response.text


def test_another_authenticated_user_cannot_read_someone_elses_findings(
    client, two_users, ai_review_db
):
    review_id = _seed(ai_review_db)

    response = client.get(f"/reviews/{review_id}/findings", headers=two_users["intruder"])

    assert response.status_code == 404
    assert response.json() == {"detail": "Review not found"}


def test_another_users_findings_are_not_reachable_even_when_filtering(
    client, two_users, ai_review_db
):
    """Filter parameters must not turn the 404 into a usable summary of the review."""
    review_id = _seed(ai_review_db)

    response = client.get(
        f"/reviews/{review_id}/findings?severity=critical&sort=confidence",
        headers=two_users["intruder"],
    )

    assert response.status_code == 404


def test_a_review_that_does_not_exist_behaves_like_one_owned_by_someone_else(
    client, two_users, ai_review_db
):
    """The 404 must not distinguish "missing" from "not yours".

    If the two responses differed, a caller could enumerate valid review ids
    belonging to other accounts without ever reading their contents.
    """
    review_id = _seed(ai_review_db)
    missing_id = "507f1f77bcf86cd799439099"

    not_yours = client.get(f"/reviews/{review_id}", headers=two_users["intruder"])
    does_not_exist = client.get(f"/reviews/{missing_id}", headers=two_users["intruder"])
    missing_findings = client.get(
        f"/reviews/{missing_id}/findings", headers=two_users["intruder"]
    )
    not_yours_findings = client.get(
        f"/reviews/{review_id}/findings", headers=two_users["intruder"]
    )

    assert not_yours.status_code == does_not_exist.status_code == 404
    assert not_yours.json() == does_not_exist.json() == {"detail": "Review not found"}
    assert not_yours_findings.json() == missing_findings.json() == {"detail": "Review not found"}


def test_a_nonexistent_review_is_a_404_for_the_owner_too(client, two_users, ai_review_db):
    _seed(ai_review_db)

    response = client.get(
        "/reviews/507f1f77bcf86cd799439099/findings", headers=two_users["owner"]
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Review not found"}


def test_a_malformed_review_id_is_a_404_rather_than_a_500(client, two_users, ai_review_db):
    _seed(ai_review_db)

    for bad_id in ("not-an-object-id", "123", "  "):
        response = client.get(f"/reviews/{bad_id}", headers=two_users["owner"])
        assert response.status_code == 404, bad_id


def test_ownership_is_enforced_under_the_api_prefix_too(client, two_users, ai_review_db):
    review_id = _seed(ai_review_db)

    assert client.get(f"/api/reviews/{review_id}", headers=two_users["owner"]).status_code == 200
    assert (
        client.get(
            f"/api/reviews/{review_id}/findings", headers=two_users["intruder"]
        ).status_code
        == 404
    )


def test_unauthenticated_requests_still_fail_before_the_ownership_check(client, ai_review_db):
    review_id = _seed(ai_review_db)

    assert client.get(f"/reviews/{review_id}").status_code == 401
    assert client.get(f"/reviews/{review_id}/findings").status_code == 401


# ---------------------------------------------------------------------------
# Ownership at the repository layer
#
# The routes are the enforcement point, but scoping belongs in the query so a
# future caller cannot forget it.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_review_by_id_requires_a_matching_user(ai_review_db):
    review_id = _seed(ai_review_db)

    assert await ai_review_repository.find_review_by_id(review_id, user_id=OWNER_ID) is not None
    assert await ai_review_repository.find_review_by_id(review_id, user_id=INTRUDER_ID) is None
    assert await ai_review_repository.find_review_by_id(review_id, user_id=1) is None


@pytest.mark.asyncio
async def test_list_findings_requires_a_matching_user(ai_review_db):
    review_id = _seed(ai_review_db)

    owned = await ai_review_repository.list_findings(review_id, user_id=OWNER_ID)
    assert len(owned) == 3

    assert await ai_review_repository.list_findings(review_id, user_id=INTRUDER_ID) == []
    assert await ai_review_repository.list_findings(review_id, user_id=1) == []


@pytest.mark.asyncio
async def test_findings_query_carries_both_review_id_and_user_id(ai_review_db):
    """The user id must be part of the filter, not a post-fetch check."""
    review_id = _seed(ai_review_db)
    captured: list[dict] = []

    original = ai_review_repository.get_db

    def spy():
        db = original()
        collection = db[ai_review_repository.FINDINGS_COLLECTION]
        real_find = collection.find

        def find(query, *args, **kwargs):
            captured.append(dict(query))
            return real_find(query, *args, **kwargs)

        collection.find = find
        return db

    ai_review_repository.get_db = spy
    try:
        await ai_review_repository.list_findings(review_id, user_id=INTRUDER_ID)
    finally:
        ai_review_repository.get_db = original

    assert captured == [{"review_id": review_id, "user_id": INTRUDER_ID}]


def test_scoping_argument_is_required_not_optional():
    """`user_id` has no default, so omitting it is a TypeError, not a silent all-users read."""
    import inspect

    for func in (ai_review_repository.find_review_by_id, ai_review_repository.list_findings):
        parameter = inspect.signature(func).parameters["user_id"]
        assert parameter.default is inspect.Parameter.empty
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
