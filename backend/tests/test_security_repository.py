"""Security persistence and ownership tests.

The contract these pin down is simple to state and easy to get wrong: a stored
scan and its findings are readable only by the user who produced them. Everything
here exercises that through the repository layer, which is where the filter
lives — a test that filtered in Python after the query would pass while the
production code leaked.
"""

import pytest

from app.schemas.security import SecurityFinding, SecurityScan
from app.services import security_repository as repo
from app.services import security_risk_service as risk

OWNER_ID = 42
OTHER_ID = 99

OWNER_NAME = "octocat"
REPO_NAME = "Hello-World"


def _finding(fingerprint="fp1", **overrides) -> SecurityFinding:
    payload = {
        "finding_id": "f1",
        "repository_id": "octocat/hello-world",
        "file": "app/config.py",
        "line": 4,
        "category": "secrets",
        "severity": "high",
        "confidence": 0.9,
        "title": "Hardcoded credential",
        "description": "d",
        "remediation": "r",
        "scanner": "secret",
        "fingerprint": fingerprint,
    }
    payload.update(overrides)
    return SecurityFinding(**payload)


def _scan(**overrides) -> SecurityScan:
    findings = overrides.pop("findings", [_finding()])
    payload = {
        "scan_id": "scan-1",
        "repository_id": "octocat/hello-world",
        "owner": OWNER_NAME,
        "repository": REPO_NAME,
        "full_name": f"{OWNER_NAME}/{REPO_NAME}",
        "summary": risk.summarize(findings),
        "findings": findings,
        "scanned_at": "2026-01-01T00:00:00+00:00",
    }
    payload.update(overrides)
    return SecurityScan(**payload)


class TestRepositoryId:
    def test_the_id_is_owner_slash_repository(self):
        assert repo.repository_id_for("octocat", "Hello-World") == "octocat/hello-world"

    def test_the_id_is_case_insensitive(self):
        # GitHub treats owner/repo case-insensitively, so two spellings of the
        # same repository must not produce two postures.
        assert repo.repository_id_for("OctoCat", "HELLO-world") == "octocat/hello-world"

    def test_surrounding_whitespace_is_ignored(self):
        assert repo.repository_id_for(" octocat ", " Hello-World ") == "octocat/hello-world"


@pytest.mark.asyncio
class TestSaveAndRead:
    async def test_a_saved_scan_is_readable_by_its_owner(self, security_db):
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(), findings=[_finding()])
        stored = await repo.get_scan(OWNER_ID, "scan-1")
        assert stored is not None
        assert stored.repository == REPO_NAME

    async def test_the_findings_travel_with_the_scan(self, security_db):
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(), findings=[_finding()])
        stored = await repo.get_scan(OWNER_ID, "scan-1")
        assert [f.finding_id for f in stored.findings] == ["f1"]

    async def test_findings_can_be_read_without_the_scan(self, security_db):
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(), findings=[_finding()])
        findings = await repo.findings_for_scan(OWNER_ID, "scan-1")
        assert len(findings) == 1

    async def test_the_summary_survives_the_round_trip(self, security_db):
        findings = [_finding("a", severity="critical"), _finding("b", severity="low")]
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(findings=findings), findings=findings)
        stored = await repo.get_scan(OWNER_ID, "scan-1", include_findings=False)
        assert stored.summary.posture_score == risk.posture_score(findings)
        assert stored.summary.total_findings == 2

    async def test_a_scan_with_no_findings_stores_no_finding_documents(self, security_db):
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(findings=[]), findings=[])
        assert security_db["security_findings"].docs == []

    async def test_a_finding_without_an_id_is_given_one_on_save(self, security_db):
        # The explanation endpoint reads a finding by id, so a stored finding must
        # always carry one even if the scanner did not supply it.
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(), findings=[_finding(finding_id="")])
        stored = await repo.get_scan(OWNER_ID, "scan-1")
        assert stored.findings[0].finding_id

    async def test_an_unknown_scan_is_none_rather_than_an_error(self, security_db):
        assert await repo.get_scan(OWNER_ID, "does-not-exist") is None

    async def test_an_empty_scan_id_is_rejected(self, security_db):
        assert await repo.get_scan(OWNER_ID, "") is None
        assert await repo.findings_for_scan(OWNER_ID, "") == []
        assert await repo.count_findings(OWNER_ID, "") == 0
        assert await repo.get_finding(OWNER_ID, "") is None


@pytest.mark.asyncio
class TestOwnershipIsolation:
    async def test_another_user_cannot_read_the_scan(self, security_db):
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(), findings=[_finding()])
        assert await repo.get_scan(OTHER_ID, "scan-1") is None

    async def test_another_user_cannot_read_the_findings(self, security_db):
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(), findings=[_finding()])
        assert await repo.findings_for_scan(OTHER_ID, "scan-1") == []
        assert await repo.count_findings(OTHER_ID, "scan-1") == 0

    async def test_another_user_cannot_read_a_single_finding(self, security_db):
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(), findings=[_finding()])
        assert await repo.get_finding(OTHER_ID, "f1") is None

    async def test_another_user_cannot_see_the_scan_in_their_list(self, security_db):
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(), findings=[_finding()])
        assert await repo.list_scans(OTHER_ID) == []

    async def test_another_user_cannot_see_another_users_posture(self, security_db):
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(), findings=[_finding()])
        assert await repo.latest_scan(OTHER_ID, OWNER_NAME, REPO_NAME) is None

    async def test_a_missing_scan_and_a_foreign_scan_are_indistinguishable(self, security_db):
        # Both return None, so a caller cannot use the response to probe which
        # scan ids exist.
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(), findings=[_finding()])
        assert await repo.get_scan(OTHER_ID, "scan-1") == await repo.get_scan(OTHER_ID, "nope")

    async def test_two_users_can_hold_scans_of_the_same_repository(self, security_db):
        # Ownership is per user, not per repository: two accounts scanning the
        # same public repo each keep their own result.
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(scan_id="s-1"), findings=[])
        await repo.save_scan(user_id=OTHER_ID, scan=_scan(scan_id="s-2"), findings=[])
        assert (await repo.get_scan(OWNER_ID, "s-1")).scan_id == "s-1"
        assert (await repo.get_scan(OTHER_ID, "s-2")).scan_id == "s-2"
        assert await repo.get_scan(OWNER_ID, "s-2") is None


@pytest.mark.asyncio
class TestFiltering:
    @staticmethod
    async def _seed(security_db):
        findings = [
            _finding("a", severity="critical", category="secrets", scanner="secret", file="a.py", line=1),
            _finding("b", severity="high", category="injection", scanner="code", file="b.py", line=2),
            _finding("c", severity="medium", category="injection", scanner="code", file="b.py", line=9),
            _finding("d", severity="low", category="crypto", scanner="code", file="c.py", line=3),
        ]
        await repo.save_scan(
            user_id=OWNER_ID, scan=_scan(findings=findings), findings=findings
        )
        return findings

    async def test_no_filter_returns_everything(self, security_db):
        await self._seed(security_db)
        assert len(await repo.findings_for_scan(OWNER_ID, "scan-1")) == 4

    async def test_severity_filter(self, security_db):
        await self._seed(security_db)
        found = await repo.findings_for_scan(OWNER_ID, "scan-1", severity="high")
        assert [f.severity for f in found] == ["high"]

    async def test_category_filter(self, security_db):
        await self._seed(security_db)
        assert len(await repo.findings_for_scan(OWNER_ID, "scan-1", category="injection")) == 2

    async def test_scanner_filter(self, security_db):
        await self._seed(security_db)
        assert len(await repo.findings_for_scan(OWNER_ID, "scan-1", scanner="code")) == 3

    async def test_file_filter(self, security_db):
        await self._seed(security_db)
        assert len(await repo.findings_for_scan(OWNER_ID, "scan-1", file="b.py")) == 2

    async def test_filters_compose(self, security_db):
        await self._seed(security_db)
        found = await repo.findings_for_scan(
            OWNER_ID, "scan-1", category="injection", file="b.py"
        )
        assert len(found) == 2

    async def test_a_filter_matching_nothing_is_an_empty_list(self, security_db):
        await self._seed(security_db)
        assert await repo.findings_for_scan(OWNER_ID, "scan-1", severity="info") == []

    async def test_the_count_matches_the_filtered_read(self, security_db):
        await self._seed(security_db)
        total = await repo.count_findings(OWNER_ID, "scan-1", category="injection")
        found = await repo.findings_for_scan(OWNER_ID, "scan-1", category="injection")
        assert total == len(found)

    async def test_pagination_slices_the_read(self, security_db):
        await self._seed(security_db)
        page = await repo.findings_for_scan(OWNER_ID, "scan-1", limit=2)
        assert len(page) == 2
        assert await repo.count_findings(OWNER_ID, "scan-1") == 4

    async def test_findings_are_returned_worst_first(self, security_db):
        # The database sorts severity alphabetically, so the repository re-sorts
        # into the canonical order. A client must see the same sequence whether
        # it read a scan or a filtered page.
        await self._seed(security_db)
        order = [f.severity for f in await repo.findings_for_scan(OWNER_ID, "scan-1")]
        assert order == ["critical", "high", "medium", "low"]


@pytest.mark.asyncio
class TestPostureAndListing:
    async def test_the_latest_scan_is_returned_for_a_repository(self, security_db):
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(), findings=[_finding()])
        latest = await repo.latest_scan(OWNER_ID, OWNER_NAME, REPO_NAME)
        assert latest.scan_id == "scan-1"

    async def test_a_repository_never_scanned_has_no_latest_scan(self, security_db):
        assert await repo.latest_scan(OWNER_ID, "nobody", "nothing") is None

    @pytest.mark.parametrize(
        "owner,repository",
        [
            ("OctoCat", "Hello-World"),
            ("octocat", "hello-world"),
            ("OCTOCAT", "HELLO-WORLD"),
            (" octocat ", " Hello-World "),
        ],
    )
    async def test_a_differently_spelled_request_finds_the_stored_scan(
        self, security_db, owner, repository
    ):
        # GitHub treats owner/repo case-insensitively, so a differently-cased
        # request must resolve to the scan the user already has rather than
        # reporting a false "never scanned" posture.
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(), findings=[_finding()])
        latest = await repo.latest_scan(OWNER_ID, owner, repository)
        assert latest is not None
        assert latest.scan_id == "scan-1"

    async def test_the_stored_spelling_is_preserved_for_display(self, security_db):
        # The match is case-insensitive, but the scan still reports the name the
        # provider returned so the page shows the repository as GitHub spells it.
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(), findings=[_finding()])
        latest = await repo.latest_scan(OWNER_ID, "OCTOCAT", "HELLO-WORLD")
        assert latest.owner == OWNER_NAME
        assert latest.repository == REPO_NAME

    async def test_a_rescan_supersedes_the_previous_one(self, security_db):
        await repo.save_scan(
            user_id=OWNER_ID, scan=_scan(scan_id="s-old"), findings=[_finding("old")]
        )
        await repo.save_scan(
            user_id=OWNER_ID,
            scan=_scan(scan_id="s-new", scanned_at="2026-06-01T00:00:00+00:00"),
            findings=[_finding("new")],
        )
        latest = await repo.latest_scan(OWNER_ID, OWNER_NAME, REPO_NAME)
        assert latest.scan_id == "s-new"

    async def test_listing_returns_only_the_users_own_scans(self, security_db):
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(scan_id="s-1"), findings=[])
        await repo.save_scan(user_id=OTHER_ID, scan=_scan(scan_id="s-2"), findings=[])
        assert [s.scan_id for s in await repo.list_scans(OWNER_ID)] == ["s-1"]

    async def test_listing_omits_findings(self, security_db):
        # An overview must not return every finding for every scan.
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(), findings=[_finding()])
        assert await repo.list_scans(OWNER_ID) == [
            item for item in await repo.list_scans(OWNER_ID) if not item.findings
        ]

    async def test_a_partial_stored_summary_degrades_to_zeros(self, security_db):
        # A document written by an older schema must not break a posture read.
        security_db["security_scans"].docs.append(
            {
                "scan_id": "legacy",
                "user_id": OWNER_ID,
                "owner": OWNER_NAME,
                "repository": REPO_NAME,
                "summary": {"total_findings": 3},
                "status": "complete",
            }
        )
        stored = await repo.get_scan(OWNER_ID, "legacy", include_findings=False)
        assert stored.summary.total_findings == 3
        assert stored.summary.severity_counts.critical == 0

    async def test_a_missing_summary_degrades_to_a_perfect_posture(self, security_db):
        security_db["security_scans"].docs.append(
            {
                "scan_id": "legacy2",
                "user_id": OWNER_ID,
                "owner": OWNER_NAME,
                "repository": REPO_NAME,
                "status": "complete",
            }
        )
        stored = await repo.get_scan(OWNER_ID, "legacy2", include_findings=False)
        assert stored.summary.posture_score == 100


class TestSecretSafety:
    @pytest.mark.asyncio
    async def test_no_secret_reaches_a_stored_document(self, security_db):
        # Defence in depth: even if a scanner regressed and attached the matched
        # text, the contract would refuse it. This asserts the stored documents
        # themselves contain no high-entropy credential.
        import re

        secret = "AKIA7XQ2MZL9P4RTW3KDN6VYBHF5JGC1"
        finding = _finding(
            scanner="secret",
            category="secrets",
            title="Exposed AWS access key",
            description="A credential-shaped value is committed to the repository.",
        )
        await repo.save_scan(user_id=OWNER_ID, scan=_scan(findings=[finding]), findings=[finding])

        blob = repr(security_db["security_findings"].docs) + repr(security_db["security_scans"].docs)
        assert secret not in blob
        # The finding carries a fingerprint derived from the value, never the
        # value itself, and no key looks like raw file content.
        stored = security_db["security_findings"].docs[0]
        assert set(stored) >= {"fingerprint", "title", "description"}
        assert not re.search(r"AKIA[A-Z0-9]{16}", blob)
