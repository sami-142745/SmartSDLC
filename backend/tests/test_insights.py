import asyncio
import datetime
import json

import pytest

from app.services.gemini_service import GeminiUnavailable, _normalize_insight_narrative, build_insights_prompt
from app.services import insight_repository, insight_service
from app.services import review_repository
from app.services.jwt_service import create_access_token


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _days_ago(days: int) -> datetime.datetime:
    return _utcnow() - datetime.timedelta(days=days)


def _review_doc(**overrides):
    doc = {
        "owner": "acme",
        "repository": "webapp",
        "pull_request_number": 10,
        "status": "completed",
        "total_finding_count": 0,
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "info_count": 0,
        "user_id": 42,
        "created_at": _days_ago(6),
    }
    doc.update(overrides)
    return doc


def _finding_doc(review_id, severity, category, source="gemini", **overrides):
    doc = {
        "review_id": review_id,
        "user_id": 42,
        "severity": severity,
        "category": category,
        "source": source,
    }
    doc.update(overrides)
    return doc


def _feedback_doc(review_id, action, category, severity, **overrides):
    doc = {
        "review_id": review_id,
        "finding_id": "f-1",
        "user_id": 42,
        "action": action,
        "category": category,
        "severity": severity,
        "owner": "acme",
        "repository": "webapp",
        "pull_request_number": 10,
        "created_at": _days_ago(2),
    }
    doc.update(overrides)
    return doc


async def _insert_review(insight_db, review):
    result = await insight_db["reviews"].insert_one(review)
    return str(result.inserted_id)


def _run(coro):
    return asyncio.run(coro)


async def _seed_webapp(insight_db):
    server_date = _utcnow()

    review_a = await _insert_review(
        insight_db,
        _review_doc(created_at=server_date - datetime.timedelta(days=6), total_finding_count=3, critical_count=2, high_count=1),
    )
    review_b = await _insert_review(
        insight_db,
        _review_doc(created_at=server_date - datetime.timedelta(days=3), total_finding_count=2, critical_count=1, medium_count=1),
    )
    review_c = await _insert_review(
        insight_db,
        _review_doc(created_at=server_date - datetime.timedelta(days=1), total_finding_count=2, high_count=1, low_count=1),
    )

    await insight_db["review_findings"].insert_many(
        [
            _finding_doc(review_a, "critical", "security", source="combined"),
            _finding_doc(review_a, "critical", "security"),
            _finding_doc(review_a, "high", "bug"),
            _finding_doc(review_b, "critical", "security"),
            _finding_doc(review_b, "medium", "complexity"),
            _finding_doc(review_c, "high", "performance"),
            _finding_doc(review_c, "low", "style"),
        ]
    )

    await insight_db["review_feedback"].insert_many(
        [
            _feedback_doc(review_a, "accepted", "security", "critical", created_at=server_date - datetime.timedelta(days=5)),
            _feedback_doc(review_b, "accepted", "security", "critical", created_at=server_date - datetime.timedelta(days=2)),
            _feedback_doc(review_b, "dismissed", "complexity", "medium", created_at=server_date - datetime.timedelta(days=2)),
        ]
    )

    return [review_a, review_b, review_c]


@pytest.fixture
def no_gemini(monkeypatch):
    async def _unavailable(context):
        raise GeminiUnavailable("Gemini analysis unavailable")

    monkeypatch.setattr("app.services.gemini_service.generate_insights_narrative", _unavailable)


@pytest.fixture
def any_user_headers(monkeypatch):
    async def get_user(github_id):
        return {
            "github_id": github_id,
            "login": f"user{github_id}",
            "name": f"User {github_id}",
            "github_access_token": "gho_super_secret_token",
        }

    monkeypatch.setattr("app.services.security.get_user_by_github_id", get_user)

    def _headers(sub):
        token = create_access_token({"sub": str(sub), "login": f"user{sub}"})
        return {"Authorization": f"Bearer {token}"}

    return _headers


class _FakeNarrative:
    def __init__(self, **kwargs):
        self._payload = kwargs

    def model_dump(self):
        return self._payload


class TestInsightRoutes:
    def test_generate_requires_auth(self, client):
        response = client.post(
            "/insights/generate",
            json={"owner": "acme", "repository": "webapp"},
        )
        assert response.status_code == 401

    def test_generate_repository_report(
        self, client, insight_db, no_gemini, any_user_headers
    ):
        _run(_seed_webapp(insight_db))

        response = client.post(
            "/insights/generate",
            json={"owner": "acme", "repository": "webapp"},
            headers=any_user_headers(42),
        )
        assert response.status_code == 200, response.text
        body = response.json()

        assert body["report_type"] == "repository"
        assert body["pull_request"] is None
        assert body["status"] == "complete"
        assert body["narrative"] is None
        assert body["model"] is None
        assert isinstance(body["duration_ms"], int)

        metrics = body["metrics"]
        assert metrics["total_findings"] == 7
        assert metrics["critical_findings"] == 3
        assert metrics["high_findings"] == 2
        assert metrics["medium_findings"] == 1
        assert metrics["low_findings"] == 1
        assert metrics["security_findings"] == 3
        assert metrics["severity_distribution"] == {
            "critical": 3,
            "high": 2,
            "medium": 1,
            "low": 1,
            "info": 0,
        }
        assert metrics["category_distribution"]["security"] == 3
        assert metrics["finding_source_distribution"] == {"combined": 1, "gemini": 6}
        assert metrics["recurring_categories"] == ["security"]
        assert metrics["average_findings_per_review"] == 2.33

        activity = body["activity"]
        assert activity["review_count"] == 3
        assert activity["pull_request_count"] == 1
        assert 1 <= activity["reviews_this_week"] <= 3
        assert len(activity["reviews_over_time"]) == 1
        assert activity["reviews_over_time"][0]["reviews"] == 3
        assert activity["reviews_over_time"][0]["findings"] == 7

        trends = {trend["metric"]: trend for trend in body["trends"]}
        assert trends["findings"]["status"] == "increasing"
        assert trends["findings"]["earlier"] == 3
        assert trends["findings"]["later"] == 4
        assert trends["critical_findings"]["status"] == "decreasing"
        assert trends["review_activity"]["status"] == "increasing"
        assert trends["feedback_activity"]["status"] == "increasing"

        risk_map = {risk["key"]: risk for risk in body["risks"]}
        assert len(body["risks"]) == 8
        assert risk_map["critical_findings_present"]["triggered"] is True
        assert risk_map["high_critical_concentration"]["triggered"] is True
        assert risk_map["recurrent_security"]["triggered"] is True
        assert risk_map["critical_recurrence"]["triggered"] is True
        assert risk_map["recent_risk_deterioration"]["triggered"] is True
        assert risk_map["elevated_medium_concentration"]["triggered"] is False
        assert risk_map["complexity_burden"]["triggered"] is False

        recommendations = body["recommendations"]
        assert recommendations[0]["priority"] == "high"
        assert any("critical" in rec["message"] for rec in recommendations)

        assert len(insight_db["insights"].docs) == 1
        stored = insight_db["insights"].docs[0]
        assert stored["user_id"] == 42
        assert stored["metrics"]["total_findings"] == 7

    def test_generate_pull_request_report(self, client, insight_db, no_gemini, any_user_headers):
        now = _utcnow()
        pr10 = _run(_insert_review(
            insight_db,
            _review_doc(pull_request_number=10, created_at=now - datetime.timedelta(days=2), total_finding_count=1, high_count=1),
        ))
        _run(insight_db["review_findings"].insert_one(_finding_doc(pr10, "high", "performance")))
        pr12 = _run(_insert_review(
            insight_db,
            _review_doc(pull_request_number=12, created_at=now - datetime.timedelta(days=1), total_finding_count=2, critical_count=2),
        ))
        _run(insight_db["review_findings"].insert_one(_finding_doc(pr12, "critical", "security")))

        response = client.post(
            "/insights/generate",
            json={"owner": "acme", "repository": "webapp", "pull_request": 12},
            headers=any_user_headers(42),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["report_type"] == "pull_request"
        assert body["pull_request"] == 12
        assert body["metrics"]["total_findings"] == 1
        assert body["metrics"]["critical_findings"] == 1
        assert len(body["source_review_ids"]) == 1
        assert body["source_review_ids"][0] == pr12

    def test_generate_without_review_history_returns_422(self, client, insight_db, no_gemini, any_user_headers):
        response = client.post(
            "/insights/generate",
            json={"owner": "acme", "repository": "noreviews"},
            headers=any_user_headers(42),
        )
        assert response.status_code == 422
        assert "No review history available for repository acme/noreviews yet." in response.json()["detail"]

    def test_generate_invalid_payload(self, client, insight_db, no_gemini, any_user_headers):
        response = client.post(
            "/insights/generate",
            json={"owner": "", "repository": ""},
            headers=any_user_headers(42),
        )
        assert response.status_code == 422

    def test_generate_with_narrative(self, client, insight_db, any_user_headers):
        now = _utcnow()

        async def _fake_narrative(context):
            return _FakeNarrative(
                executive_summary="Executive summary text",
                trend_interpretation="Trend interpretation text",
                risk_explanation="Risk explanation text",
                recommendations=["Recommendation one"],
            )

        import app.services.insight_service as insight_module

        insight_module.gemini_service.generate_insights_narrative = _fake_narrative

        _run(_insert_review(insight_db, _review_doc(total_finding_count=1, critical_count=1)))
        _run(insight_db["review_findings"].insert_one(_finding_doc("r1", "critical", "security")))

        response = client.post(
            "/insights/generate",
            json={"owner": "acme", "repository": "webapp"},
            headers=any_user_headers(42),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["narrative"]["executive_summary"] == "Executive summary text"
        assert body["narrative"]["trend_interpretation"] == "Trend interpretation text"
        assert body["narrative"]["risk_explanation"] == "Risk explanation text"
        assert body["narrative"]["recommendations"] == ["Recommendation one"]
        assert body["model"]

    def test_list_insights_pagination_and_filter(self, client, insight_db, no_gemini, any_user_headers):
        now = _utcnow()
        for repo, pr, days in (("webapp", 10, 3), ("webapp", 11, 2), ("api", 5, 1)):
            review_id = _run(_insert_review(
                insight_db,
                _review_doc(owner="acme", repository=repo, pull_request_number=pr, created_at=now - datetime.timedelta(days=days), total_finding_count=1, high_count=1),
            ))
            _run(insight_db["review_findings"].insert_one(_finding_doc(review_id, "high", "performance")))

        headers = any_user_headers(42)
        client.post("/insights/generate", json={"owner": "acme", "repository": "webapp"}, headers=headers)
        client.post("/insights/generate", json={"owner": "acme", "repository": "webapp", "pull_request": 11}, headers=headers)
        client.post("/insights/generate", json={"owner": "acme", "repository": "api"}, headers=headers)

        response = client.get("/insights?page=1&per_page=2", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert body["total_pages"] == 2
        assert len(body["items"]) == 2

        response = client.get("/insights?repository=api", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["repository"] == "api"

        response = client.get("/insights?report_type=pull_request", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["report_type"] == "pull_request"

    def test_repository_insight_latest(self, client, insight_db, no_gemini, any_user_headers):
        now = _utcnow()
        review_id = _run(_insert_review(
            insight_db,
            _review_doc(created_at=now - datetime.timedelta(days=1), total_finding_count=1, high_count=1),
        ))
        _run(insight_db["review_findings"].insert_one(_finding_doc(review_id, "high", "bug")))

        headers = any_user_headers(42)
        client.post("/insights/generate", json={"owner": "acme", "repository": "webapp"}, headers=headers)
        second_id = client.post(
            "/insights/generate",
            json={"owner": "acme", "repository": "webapp"},
            headers=headers,
        ).json()["id"]

        response = client.get("/insights/repository/acme/webapp", headers=headers)
        assert response.status_code == 200
        assert response.json()["id"] == second_id

        response = client.get("/insights/repository/acme/unknown", headers=headers)
        assert response.status_code == 404

    def test_get_insight_by_id_and_ownership(self, client, insight_db, no_gemini, any_user_headers):
        now = _utcnow()
        review_id = _run(_insert_review(
            insight_db,
            _review_doc(created_at=now - datetime.timedelta(days=1), total_finding_count=1, high_count=1),
        ))
        _run(insight_db["review_findings"].insert_one(_finding_doc(review_id, "high", "bug")))

        report_id = client.post(
            "/insights/generate",
            json={"owner": "acme", "repository": "webapp"},
            headers=any_user_headers(42),
        ).json()["id"]

        response = client.get(f"/insights/{report_id}", headers=any_user_headers(42))
        assert response.status_code == 200
        assert response.json()["repository"] == "webapp"

        response = client.get(f"/insights/{report_id}", headers=any_user_headers(7))
        assert response.status_code == 404

        response = client.get("/insights/not-a-valid-id", headers=any_user_headers(42))
        assert response.status_code == 404

        response = client.get("/insights", headers=any_user_headers(7))
        assert response.status_code == 200
        assert response.json()["items"] == []


class TestInsightService:
    @pytest.mark.asyncio
    async def test_insufficient_trends_for_single_review(self, insight_db, no_gemini):
        review_id = await _insert_review(
            insight_db,
            _review_doc(total_finding_count=1, critical_count=1),
        )
        await insight_db["review_findings"].insert_one(_finding_doc(review_id, "critical", "security"))

        report = await insight_service.generate_insight(
            user_id=42,
            owner="acme",
            repository="webapp",
            generate_narrative=False,
        )
        statuses = {trend.metric: trend.status for trend in report.trends}
        assert set(statuses.values()) == {"insufficient"}
        findings_trend = next(t for t in report.trends if t.metric == "findings")
        assert "Insufficient" in (findings_trend.note or "")

    @pytest.mark.asyncio
    async def test_metrics_deterministic(self, insight_db, no_gemini):
        await _seed_webapp(insight_db)
        first = await insight_service.generate_insight(
            user_id=42,
            owner="acme",
            repository="webapp",
            generate_narrative=False,
        )
        second = await insight_service.generate_insight(
            user_id=42,
            owner="acme",
            repository="webapp",
            generate_narrative=False,
        )
        assert first.metrics.model_dump() == second.metrics.model_dump()

    @pytest.mark.asyncio
    async def test_generation_handles_naive_utc_timestamps(self, insight_db, no_gemini):
        """MongoDB returns naive-UTC datetimes by default; the report must not crash."""
        server_date = _utcnow()
        r1 = await _insert_review(
            insight_db,
            _review_doc(
                created_at=(server_date - datetime.timedelta(days=2)).replace(tzinfo=None),
                total_finding_count=2,
                high_count=2,
            ),
        )
        r2 = await _insert_review(
            insight_db,
            _review_doc(
                created_at=(server_date - datetime.timedelta(days=1)).replace(tzinfo=None),
                total_finding_count=1,
                critical_count=1,
            ),
        )
        await insight_db["review_findings"].insert_many(
            [_finding_doc(r1, "high", "bug"), _finding_doc(r1, "high", "performance")]
        )
        await insight_db["review_findings"].insert_one(_finding_doc(r2, "critical", "security"))
        await insight_db["review_feedback"].insert_one(
            _feedback_doc(r1, "accepted", "bug", "high", created_at=(server_date - datetime.timedelta(days=1)).replace(tzinfo=None))
        )

        report = await insight_service.generate_insight(
            user_id=42,
            owner="acme",
            repository="webapp",
            generate_narrative=False,
        )

        assert report.status == "complete"
        assert report.activity.review_count == 2
        assert report.metrics.total_findings == 3
        assert report.activity.first_review_at is not None
        assert report.activity.latest_review_at is not None
        assert report.feedback.total_feedback == 1

    def test_feedback_aggregation(self):
        feedback = [
            _feedback_doc("r1", "accepted", "security", "critical"),
            _feedback_doc("r1", "dismissed", "security", "critical"),
            _feedback_doc("r2", "accepted", "bug", "high"),
        ]
        summary = insight_service.compute_feedback(feedback)
        assert summary["total_accepted"] == 2
        assert summary["total_dismissed"] == 1
        assert summary["total_feedback"] == 3
        assert summary["acceptance_rate"] == round(2 / 3, 2)
        assert summary["category_feedback"]["security"] == {"accepted": 1, "dismissed": 1, "total": 2}
        assert summary["severity_feedback"]["critical"] == {"accepted": 1, "dismissed": 1, "total": 2}

    @pytest.mark.asyncio
    async def test_low_feedback_acceptance_risk(self, insight_db, no_gemini):
        now = _utcnow()
        r1 = await _insert_review(insight_db, _review_doc(created_at=now - datetime.timedelta(days=2), total_finding_count=2, high_count=2))
        r2 = await _insert_review(insight_db, _review_doc(created_at=now - datetime.timedelta(days=1), total_finding_count=2, high_count=2))
        await insight_db["review_findings"].insert_many(
            [_finding_doc(r1, "high", "bug"), _finding_doc(r1, "high", "performance")]
        )
        await insight_db["review_findings"].insert_many(
            [_finding_doc(r2, "high", "bug"), _finding_doc(r2, "high", "performance")]
        )
        await insight_db["review_feedback"].insert_many(
            [
                _feedback_doc(r1, "dismissed", "bug", "high"),
                _feedback_doc(r1, "dismissed", "performance", "high"),
                _feedback_doc(r2, "accepted", "bug", "high"),
                _feedback_doc(r2, "dismissed", "performance", "high"),
            ]
        )
        report = await insight_service.generate_insight(
            user_id=42,
            owner="acme",
            repository="webapp",
            generate_narrative=False,
        )
        risk_map = {risk.key: risk for risk in report.risks}
        assert risk_map["low_feedback_acceptance"].triggered is True

    @pytest.mark.asyncio
    async def test_empty_scope_raises_insight_error(self, insight_db, no_gemini):
        with pytest.raises(insight_service.InsightGenerationError) as exc_info:
            await insight_service.generate_insight(
                user_id=42,
                owner="acme",
                repository="webapp",
                generate_narrative=False,
            )
        assert "No review history available for repository acme/webapp yet." in str(exc_info.value)


class TestInsightRepository:
    @pytest.mark.asyncio
    async def test_scope_functions_filter_and_order(self, insight_db):
        now = _utcnow()
        older = await _insert_review(insight_db, _review_doc(created_at=now - datetime.timedelta(days=3)))
        newer = await _insert_review(insight_db, _review_doc(created_at=now - datetime.timedelta(days=1)))
        other_repo = await _insert_review(insight_db, _review_doc(owner="acme", repository="api"))
        other_user = await _insert_review(insight_db, _review_doc(user_id=7))

        await insight_db["review_findings"].insert_many(
            [
                _finding_doc(older, "high", "bug"),
                _finding_doc(newer, "critical", "security"),
                _finding_doc(other_repo, "low", "style"),
            ]
        )

        reviews = await review_repository.list_reviews_for_scope(42, "acme", "webapp")
        ids = [str(review["_id"]) for review in reviews]
        assert ids == [older, newer]

        pr_scoped = await review_repository.list_reviews_for_scope(42, "acme", "webapp", pull_request_number=10)
        assert len(pr_scoped) == 2

        findings = await review_repository.list_findings_for_reviews([older, newer])
        assert {finding["severity"] for finding in findings} == {"high", "critical"}
        assert len(await review_repository.list_findings_for_reviews([other_repo])) == 1

        assert len(await review_repository.list_feedback_for_scope(42, "acme", "webapp")) == 0

    def test_is_valid_insight_id(self):
        assert insight_repository.is_valid_insight_id("0123456789abcdef01234567") is True
        assert insight_repository.is_valid_insight_id("short") is False
        assert insight_repository.is_valid_insight_id(None) is False

    @pytest.mark.asyncio
    async def test_get_insight_validates_ownership(self, insight_db):
        saved = await insight_repository.save_insight(
            {"user_id": 42, "owner": "acme", "repository": "webapp", "metrics": {}, "created_at": _utcnow()}
        )
        assert insight_repository.is_valid_insight_id(saved) is True
        assert (await insight_repository.get_insight(saved, 42)) is not None
        assert (await insight_repository.get_insight(saved, 7)) is None
        assert (await insight_repository.get_insight("bogus", 42)) is None


class TestInsightPromptSafety:
    def test_prompt_contains_only_aggregate_metrics(self):
        context = {
            "repository": "acme/webapp",
            "metrics": {"total_findings": 7, "critical_findings": 3},
            "trends": [{"metric": "findings", "status": "increasing", "earlier": 3, "later": 4}],
        }
        prompt = build_insights_prompt(context)
        assert '"total_findings": 7' in prompt
        assert "findings" in prompt

    @pytest.mark.asyncio
    async def test_finding_content_never_reaches_the_narrative(self, insight_db):
        now = _utcnow()
        review_id = await _insert_review(
            insight_db,
            _review_doc(created_at=now - datetime.timedelta(days=1), total_finding_count=1, high_count=1),
        )
        captured = {}

        async def _recording_narrative(context):
            captured["context"] = dict(context)
            return _FakeNarrative(
                executive_summary="summary",
                trend_interpretation=None,
                risk_explanation=None,
                recommendations=[],
            )

        import app.services.insight_service as insight_module

        insight_module.gemini_service.generate_insights_narrative = _recording_narrative

        await insight_db["review_findings"].insert_one(
            _finding_doc(
                review_id,
                "high",
                "bug",
                title="Leaked ghp_LIVE_SECRET_0123456789",
                recommendation="use ghp_LIVE_SECRET_0123456789 to fix",
            )
        )

        await insight_service.generate_insight(
            user_id=42,
            owner="acme",
            repository="webapp",
            generate_narrative=True,
        )

        serialized = json.dumps(captured["context"], default=str)
        assert "ghp_LIVE_SECRET_0123456789" not in serialized
        assert "ghp_" not in serialized
        assert '"total_findings": 1' in serialized

    def test_normalize_narrative(self):
        narrative = _normalize_insight_narrative(
            {
                "executive_summary": "  Healthy posture  ",
                "trend_interpretation": None,
                "risk_explanation": "Risks noted",
                "recommendations": ["Fix criticals", 123, ""],
            }
        )
        assert narrative is not None
        assert narrative.executive_summary == "Healthy posture"
        assert narrative.recommendations == ["Fix criticals"]
        assert _normalize_insight_narrative("not a dict") is None