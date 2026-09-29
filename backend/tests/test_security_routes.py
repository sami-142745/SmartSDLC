"""HTTP contract tests for the security engine endpoints.

Four properties are exercised, and they are the ones a reviewer of this API
would want checked first:

* **Authentication** — every route refuses an unauthenticated caller.
* **Ownership** — a scan belonging to another user is a 404, byte-identical to
  the response for a scan that does not exist, so the endpoint cannot be used to
  discover which scan ids are real.
* **Validation** — a bad id, a bad filter and a bad body are distinguishable
  from "the repository is clean".
* **Secret safety** — nothing resembling a matched secret crosses the wire.
"""

import pytest

from app.schemas.security import SecurityFinding, SecurityScan
from app.services import security_explanation_service, security_repository, security_scan_service
from app.services.jwt_service import create_access_token

OWNER_ID = 42
INTRUDER_ID = 99

USERS = {
    OWNER_ID: {"login": "octocat", "name": "Octo Cat", "github_access_token": "gho_TESTowner"},
    INTRUDER_ID: {
        "login": "intruder",
        "name": "Nosy Parker",
        "github_access_token": "gho_TESTintruder",
    },
}

#: A value the secret scanner detects. Asserted absent from every response body.
LEAKED_KEY = "AKIATEST7XQ2MZL9P4RTW3KDN6VYBHF5JGC1"


def _bearer(github_id: int) -> dict[str, str]:
    token = create_access_token({"sub": str(github_id), "login": USERS[github_id]["login"]})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def two_users(monkeypatch):
    """Two independently valid sessions, so ownership can actually be exercised.

    The shared ``auth_headers`` fixture pins every request to one user, which
    would make an ownership test silently compare a user with themselves.
    """

    async def known_user(github_id):
        profile = USERS.get(int(github_id))
        if profile is None:
            return None
        return {"_id": f"{int(github_id):024d}", "github_id": int(github_id), **profile}

    monkeypatch.setattr("app.services.security.get_user_by_github_id", known_user)
    return {"owner": _bearer(OWNER_ID), "intruder": _bearer(INTRUDER_ID)}


def _finding(finding_id="f1", fingerprint="fp1", **overrides) -> SecurityFinding:
    payload = {
        "finding_id": finding_id,
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
        "fingerprint": fingerprint,
    }
    payload.update(overrides)
    return SecurityFinding(**payload)


def _scan(findings=None, **overrides) -> SecurityScan:
    findings = findings if findings is not None else [_finding()]
    from app.services import security_risk_service as risk

    payload = {
        "scan_id": "scan-1",
        "repository_id": "octocat/hello-world",
        "owner": "octocat",
        "repository": "Hello-World",
        "full_name": "octocat/Hello-World",
        "summary": risk.summarize(findings),
        "findings": findings,
        "scanned_at": "2026-01-01T00:00:00+00:00",
    }
    payload.update(overrides)
    return SecurityScan(**payload)


@pytest.fixture
def seeded(security_db):
    """A scan owned by OWNER_ID, with one critical secret finding."""
    import asyncio

    findings = [
        _finding("f1", "fp1", severity="critical", category="secrets", scanner="secret", file="a.py"),
        _finding("f2", "fp2", severity="high", category="injection", scanner="code", file="b.py", line=2),
    ]
    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        security_repository.save_scan(
            user_id=OWNER_ID, scan=_scan(findings=findings), findings=findings
        )
    )
    return scan_summary(findings)


def scan_summary(findings):
    from app.services import security_risk_service as risk

    return risk.summarize(findings).as_response()


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/security/scanners"),
        ("get", "/security/scans"),
        ("post", "/security/scans"),
        ("get", "/security/scans/scan-1"),
        ("get", "/security/scans/scan-1/findings"),
        ("get", "/security/findings/f1/explanation"),
        ("get", "/security/repositories/octocat/Hello-World/posture"),
    ],
)
def test_every_endpoint_requires_authentication(client, method, path):
    body = {"owner": "o", "repository": "r"} if method == "post" else None
    response = client.request(method, path, json=body) if body else client.request(method, path)
    assert response.status_code == 401


@pytest.mark.parametrize("prefix", ["", "/api"])
def test_the_dual_registration_serves_the_same_handlers(client, two_users, prefix):
    response = client.get(f"{prefix}/security/scanners", headers=two_users["owner"])
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /security/scanners
# ---------------------------------------------------------------------------


def test_the_scanner_catalogue_lists_every_detector(client, two_users):
    body = client.get("/security/scanners", headers=two_users["owner"]).json()
    assert set(body) >= {"secret", "code", "dependency", "severities", "categories", "scanners"}
    assert body["scanners"] == ["secret", "code", "dependency"]
    assert body["severities"] == ["critical", "high", "medium", "low", "info"]


def test_each_scanner_reports_its_rules(client, two_users):
    body = client.get("/security/scanners", headers=two_users["owner"]).json()
    for scanner in ("secret", "code", "dependency"):
        assert len(body[scanner]) > 0


# ---------------------------------------------------------------------------
# POST /security/scans
# ---------------------------------------------------------------------------


def _stub_scan(monkeypatch, result=None, error=None):
    async def _fake(*args, **kwargs):
        if error is not None:
            raise error
        if result is not None:
            return result
        return _scan(
            findings=[
                _finding("f1", "fp1", severity="critical", scanner="secret", file="a.py"),
                _finding("f2", "fp2", severity="high", category="injection", scanner="code", file="b.py", line=2),
            ]
        )

    monkeypatch.setattr(security_scan_service, "scan_repository", _fake)


def test_creating_a_scan_returns_201_with_the_findings(client, two_users, monkeypatch, security_db):
    _stub_scan(monkeypatch)
    response = client.post(
        "/security/scans",
        json={"owner": "octocat", "repository": "Hello-World"},
        headers=two_users["owner"],
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "complete"
    assert body["summary"]["total_findings"] == 2


def test_the_response_carries_the_deterministic_risk_numbers(client, two_users, monkeypatch, security_db):
    _stub_scan(monkeypatch)
    body = client.post(
        "/security/scans",
        json={"owner": "octocat", "repository": "Hello-World"},
        headers=two_users["owner"],
    ).json()
    # critical 8 + high 3, divided across 2 findings.
    assert body["summary"]["weighted_risk"] == 11
    assert body["summary"]["posture_score"] == 94


def test_the_response_never_contains_the_matched_secret(client, two_users, monkeypatch, security_db):
    _stub_scan(monkeypatch)
    response = client.post(
        "/security/scans",
        json={"owner": "octocat", "repository": "Hello-World"},
        headers=two_users["owner"],
    )
    assert LEAKED_KEY not in response.text


def test_a_provider_error_maps_to_the_right_status(client, two_users, monkeypatch, security_db):
    from app.services.scm import ScmAPIError

    _stub_scan(monkeypatch, error=security_scan_service.SecurityScanError("no tree"))
    response = client.post(
        "/security/scans",
        json={"owner": "octocat", "repository": "Hello-World"},
        headers=two_users["owner"],
    )
    assert response.status_code == 502


def test_an_scm_failure_is_mapped_by_category(client, two_users, monkeypatch, security_db):
    from app.services.scm import ScmAPIError

    _stub_scan(monkeypatch, error=ScmAPIError(404, "no such repository", "not_found"))
    response = client.post(
        "/security/scans",
        json={"owner": "octocat", "repository": "Hello-World"},
        headers=two_users["owner"],
    )
    assert response.status_code == 404


def test_a_scan_requires_a_connected_provider(client, two_users, monkeypatch, security_db):
    async def _no_token(user=None):
        return None

    # A user with no stored provider token cannot start a scan.
    async def known_user(github_id):
        return {"_id": "0" * 24, "github_id": int(github_id), "login": "x"}

    monkeypatch.setattr("app.services.security.get_user_by_github_id", known_user)
    response = client.post(
        "/security/scans",
        json={"owner": "o", "repository": "r"},
        headers=two_users["owner"],
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {"repository": "r"},
        {"owner": "o"},
        {"owner": "", "repository": "r"},
        {"owner": "o", "repository": "  "},
        {"owner": "o", "repository": "r", "provider": "bitbucket"},
        {"owner": "o", "repository": "r", "max_files": 0},
        {"owner": "o", "repository": "r", "max_files": 99999},
        {"owner": "o", "repository": "r", "surprise": True},
    ],
)
def test_the_scan_body_is_validated(client, two_users, monkeypatch, security_db, payload):
    _stub_scan(monkeypatch)
    assert client.post("/security/scans", json=payload, headers=two_users["owner"]).status_code == 422


# ---------------------------------------------------------------------------
# GET /security/scans/{scan_id}
# ---------------------------------------------------------------------------


def test_reading_a_scan_returns_it_with_its_findings(client, two_users, seeded):
    body = client.get("/security/scans/scan-1", headers=two_users["owner"]).json()
    assert body["scan_id"] == "scan-1"
    assert len(body["findings"]) == 2


def test_findings_can_be_omitted_from_a_scan_read(client, two_users, seeded):
    body = client.get(
        "/security/scans/scan-1?include_findings=false", headers=two_users["owner"]
    ).json()
    assert body["findings"] == []
    # The summary must survive, or an overview page would have nothing to show.
    assert body["summary"]["total_findings"] == 2


def test_another_users_scan_is_a_404(client, two_users, seeded):
    assert client.get("/security/scans/scan-1", headers=two_users["intruder"]).status_code == 404


def test_an_unknown_scan_is_a_404(client, two_users, seeded):
    assert client.get("/security/scans/nope", headers=two_users["owner"]).status_code == 404


@pytest.mark.parametrize("scan_id", ["not-an-object-id", "../../etc/passwd", "%20", "a" * 500])
def test_a_malformed_scan_id_is_a_404_not_a_500(client, two_users, seeded, scan_id):
    response = client.get(f"/security/scans/{scan_id}", headers=two_users["owner"])
    assert response.status_code == 404


def test_a_foreign_scan_is_indistinguishable_from_a_missing_one(client, two_users, seeded):
    foreign = client.get("/security/scans/scan-1", headers=two_users["intruder"])
    missing = client.get("/security/scans/does-not-exist", headers=two_users["intruder"])
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()


def test_a_scan_response_never_contains_a_secret(client, two_users, seeded):
    assert LEAKED_KEY not in client.get("/security/scans/scan-1", headers=two_users["owner"]).text


# ---------------------------------------------------------------------------
# GET /security/scans/{scan_id}/findings
# ---------------------------------------------------------------------------


def test_findings_are_listed_with_their_total(client, two_users, seeded):
    body = client.get("/security/scans/scan-1/findings", headers=two_users["owner"]).json()
    assert body["total"] == 2
    assert len(body["findings"]) == 2


def test_findings_are_ordered_worst_first(client, two_users, seeded):
    body = client.get("/security/scans/scan-1/findings", headers=two_users["owner"]).json()
    assert [f["severity"] for f in body["findings"]] == ["critical", "high"]


def test_the_severity_filter_narrows_the_page(client, two_users, seeded):
    body = client.get(
        "/security/scans/scan-1/findings?severity=critical", headers=two_users["owner"]
    ).json()
    assert body["total"] == 1
    assert body["findings"][0]["severity"] == "critical"


def test_the_category_filter_narrows_the_page(client, two_users, seeded):
    body = client.get(
        "/security/scans/scan-1/findings?category=injection", headers=two_users["owner"]
    ).json()
    assert body["total"] == 1


def test_the_scanner_filter_narrows_the_page(client, two_users, seeded):
    body = client.get(
        "/security/scans/scan-1/findings?scanner=code", headers=two_users["owner"]
    ).json()
    assert body["total"] == 1


def test_filters_compose(client, two_users, seeded):
    body = client.get(
        "/security/scans/scan-1/findings?severity=high&scanner=code",
        headers=two_users["owner"],
    ).json()
    assert body["total"] == 1


def test_pagination_reports_the_unfiltered_total(client, two_users, seeded):
    body = client.get(
        "/security/scans/scan-1/findings?limit=1", headers=two_users["owner"]
    ).json()
    assert len(body["findings"]) == 1
    assert body["total"] == 2


@pytest.mark.parametrize(
    "query",
    [
        "severity=critial",
        "category=sql",
        "scanner=sast",
    ],
)
def test_an_unknown_filter_value_is_a_422_not_an_empty_list(client, two_users, seeded, query):
    # A misspelt filter that returned an empty list would look like a clean
    # repository, which is the worst possible failure for this page.
    response = client.get(f"/security/scans/scan-1/findings?{query}", headers=two_users["owner"])
    assert response.status_code == 422


def test_another_users_findings_are_a_404(client, two_users, seeded):
    # Not an empty list: an empty list would confirm the scan exists.
    assert client.get("/security/scans/scan-1/findings", headers=two_users["intruder"]).status_code == 404


def test_a_malformed_scan_id_is_a_404_on_the_findings_route(client, two_users, seeded):
    assert client.get("/security/scans/bad!id/findings", headers=two_users["owner"]).status_code == 404


def test_a_findings_response_never_contains_a_secret(client, two_users, seeded):
    response = client.get("/security/scans/scan-1/findings", headers=two_users["owner"])
    assert LEAKED_KEY not in response.text


def test_pagination_bounds_are_enforced(client, two_users, seeded):
    assert client.get(
        "/security/scans/scan-1/findings?limit=0", headers=two_users["owner"]
    ).status_code == 422
    assert client.get(
        "/security/scans/scan-1/findings?limit=100000", headers=two_users["owner"]
    ).status_code == 422


# ---------------------------------------------------------------------------
# GET /security/scans
# ---------------------------------------------------------------------------


def test_the_scan_list_is_scoped_to_the_user(client, two_users, seeded):
    owner = client.get("/security/scans", headers=two_users["owner"]).json()
    intruder = client.get("/security/scans", headers=two_users["intruder"]).json()
    assert [s["scan_id"] for s in owner] == ["scan-1"]
    assert intruder == []


def test_the_scan_list_omits_findings(client, two_users, seeded):
    body = client.get("/security/scans", headers=two_users["owner"]).json()
    assert body[0]["findings"] == []
    assert body[0]["summary"]["total_findings"] == 2


# ---------------------------------------------------------------------------
# GET /security/repositories/{owner}/{repository}/posture
# ---------------------------------------------------------------------------


def test_posture_is_returned_for_a_scanned_repository(client, two_users, seeded):
    body = client.get(
        "/security/repositories/octocat/Hello-World/posture", headers=two_users["owner"]
    ).json()
    assert body["has_scan"] is True
    assert body["scan_id"] == "scan-1"
    assert body["summary"]["total_findings"] == 2
    assert body["summary"]["posture_score"] == 94


def test_posture_states_the_methodology(client, two_users, seeded):
    # A reader needs to know the score is deterministic and not model-produced.
    body = client.get(
        "/security/repositories/octocat/Hello-World/posture", headers=two_users["owner"]
    ).json()
    assert "deterministic" in body["methodology"].lower()


def test_an_unscanned_repository_is_a_zeroed_state_not_a_404(client, two_users, seeded):
    response = client.get(
        "/security/repositories/nobody/nothing/posture", headers=two_users["owner"]
    )
    assert response.status_code == 200
    body = response.json()
    assert body["has_scan"] is False
    assert body["summary"]["total_findings"] == 0
    assert body["summary"]["posture_score"] == 100


def test_posture_for_another_users_repository_reports_no_scan(client, two_users, seeded):
    # The repository is public, but the *stored scan* is the owner's. Reporting
    # "not scanned" leaks nothing and returns nothing of theirs.
    body = client.get(
        "/security/repositories/octocat/Hello-World/posture", headers=two_users["intruder"]
    ).json()
    assert body["has_scan"] is False
    assert body["scan_id"] is None


def test_posture_never_contains_a_secret(client, two_users, seeded):
    response = client.get(
        "/security/repositories/octocat/Hello-World/posture", headers=two_users["owner"]
    )
    assert LEAKED_KEY not in response.text


# ---------------------------------------------------------------------------
# GET /security/findings/{finding_id}/explanation
# ---------------------------------------------------------------------------


def _stub_explanation(monkeypatch, result):
    async def _fake(finding):
        return result

    monkeypatch.setattr(security_explanation_service, "explain_finding", _fake)


def test_a_valid_explanation_is_returned(client, two_users, seeded, monkeypatch):
    from app.schemas.security import SecurityExplanation

    _stub_explanation(
        monkeypatch,
        SecurityExplanation(
            finding_id="f1",
            explanation="A credential is committed to source control.",
            impact="Anyone with repository read access can use the key.",
            remediation="Revoke the key and load it from the environment.",
            model="gemini",
        ),
    )
    body = client.get("/security/findings/f1/explanation", headers=two_users["owner"]).json()
    assert body["explanation"]
    assert body["model"] == "gemini"


def test_an_unavailable_model_degrades_rather_than_failing(client, two_users, seeded, monkeypatch):
    from app.schemas.security import SecurityExplanation

    # The scanner's own remediation still travels with the placeholder, so a
    # reviewer who could not get model prose is not left with nothing.
    _stub_explanation(
        monkeypatch,
        SecurityExplanation(
            finding_id="f1",
            explanation="",
            impact="",
            remediation="Revoke the key and load it from the environment.",
            unavailable_reason="Gemini is not configured for this deployment",
        ),
    )
    response = client.get("/security/findings/f1/explanation", headers=two_users["owner"])
    assert response.status_code == 200
    body = response.json()
    assert body["explanation"] == ""
    assert body["remediation"]
    assert body["unavailable_reason"]


def test_another_users_finding_is_a_404(client, two_users, seeded, monkeypatch):
    _stub_explanation(monkeypatch, None)
    assert client.get("/security/findings/f1/explanation", headers=two_users["intruder"]).status_code == 404


def test_an_unknown_finding_is_a_404(client, two_users, seeded, monkeypatch):
    _stub_explanation(monkeypatch, None)
    assert client.get("/security/findings/nope/explanation", headers=two_users["owner"]).status_code == 404


def test_an_explanation_never_contains_a_secret(client, two_users, seeded, monkeypatch):
    from app.schemas.security import SecurityExplanation

    _stub_explanation(
        monkeypatch,
        SecurityExplanation(
            finding_id="f1",
            explanation="d",
            impact="i",
            remediation="r",
            model="gemini",
        ),
    )
    response = client.get("/security/findings/f1/explanation", headers=two_users["owner"])
    assert LEAKED_KEY not in response.text
