# Phase 7 — AI Insights & Reports: Final Report

## 1. Files created

Backend (6 new source files + 1 test file additions):

- `backend/app/schemas/insight.py` — Pydantic models: `InsightReportType` (repository|pull_request), `InsightTrend` (metric/status/early/late/delta/note), `InsightRisk` (id/level/score/title/reason), `InsightRecommendation` (priority/title/basis), `InsightNarrative`, `InsightFeedbackSummary`, `InsightActivity`, `InsightMetrics`, `InsightReport`, `InsightListResponse`, `GenerateInsightRequest`.
- `backend/app/services/insight_repository.py` — persistence for generated reports: insert, list (page/per_page/repository/report_type, newest-first, user-scoped), latest-by-repo, get-by-id+ownership, indexes.
- `backend/app/services/insight_service.py` — the generation pipeline: scope loading, deterministic metrics, trends, risk engine, feedback aggregation, activity windowing, Gemini narrative, report assembly.
- `backend/app/routers/insights.py` — `POST /insights/generate`, `GET /insights`, `GET /insights/repository/{owner}/{repository}`, `GET /insights/{insight_id}` (declared before the id route; `^[0-9a-f]{24}$` + ownership).
- `backend/app/services/gemini_service.py` — added `build_insights_prompt`, `generate_insights_narrative`, `GEMINI_INSIGHT_JSON_CONFIG`, `GeminiInsightNarrative`; prompt carries only aggregate metrics (no findings/code/secrets).
- `backend/app/services/review_repository.py` — added `list_reviews_for_scope`, `list_findings_for_reviews`, `list_feedback_for_scope`.

Backend tests:

- `backend/tests/conftest.py` — `insight_db` fixture + insights FakeCollection support.
- `backend/tests/test_insights.py` — 21 tests (routes, service, repository, prompt-safety).

Frontend (2 new source/test files):

- `frontend/src/api/insights.ts` — `generateInsight`, `getInsights` (page/perPage/repository/reportType), `getLatestRepositoryInsight`, `getInsight`.
- `frontend/src/pages/InsightsPage.tsx` — hero, generator console (repository + optional PR), live report view, archive sidebar.
- `frontend/src/__tests__/InsightsPage.test.tsx` — 8 tests (render, loading, error, generation, PR payload, generation error, archive refresh, open archived report).

## 2. Files modified

- `backend/app/main.py` — registered the insights router + report collection indexes.
- `backend/tests/test_insights.py`, `backend/tests/conftest.py` — see above.
- `frontend/src/types/index.ts` — 14 insight interfaces.
- `frontend/src/App.tsx` — `/insights` route.
- `frontend/src/components/Layout/Sidebar.tsx` — Insights nav item (between Documentation and Feedback Loop).
- `frontend/src/pages/DashboardPage.tsx` — `latestInsight` (`getInsights({ perPage: 1 })`) + new `InsightStrip` below the hero.
- `frontend/src/test/fixtures.ts`, `frontend/src/__tests__/App.test.tsx`, `frontend/src/__tests__/DashboardPage.test.tsx` — `vi.mock('../api/insights')` coverage.

## 3. Insight data model

Reports are stored per user in a dedicated `insights` collection. Every report is immutable history: it captures the deterministic metrics, trends, risks, feedback summary, activity window and (when Gemini is available) a narrative and model name, plus `source_review_ids` linking to the exact reviews analyzed. Reports scoped to a PR store `pull_request`; repository reports store `pull_request: null`. Ownership is enforced on every read (list/latest/get) by `user_id`.

## 4. Report generation pipeline

`POST /insights/generate` with `{owner, repository, pull_request?}` authenticates via `get_current_user` only (no GitHub token requirement), loads all reviews + findings + feedback for the scope directly from stored pipeline data, then builds: metrics → trends → risks → feedback summary → activity → (optional) Gemini narrative → persisted report (HTTP 201). The report type is derived (`pull_request` when a PR number is provided, else `repository`).

## 5. Metrics

`InsightMetrics` aggregates the real review history: total findings, critical/high/medium/low/info counts, findings-per-review (2 dp), critical share (2 dp), unique pull requests, accepted/dismissed feedback counts, and acceptance rate. Every field comes from stored documents — nothing is fabricated. A scope with zero reviews returns 422, never a zero report.

## 6. Trends methodology

For each metric the review timeline is split into earlier vs later halves; each half is aggregated and the trend computed from the two points. Classification: `increasing`/`decreasing` (|delta| ≥ 1) / `stable` (delta < 1), else `insufficient` when fewer than 2 comparable buckets. Confidence is shown per metric; trends are computed per metric not extrapolated — conclusions are only drawn from the observed windows.

## 7. Risk engine

8 deterministic risks are computed from real data with fixed thresholds: `CONCENTRATION_THRESHOLD = 0.5`, `MEDIUM = 0.4`, `COMPLEXITY_MIN_FINDINGS = 5`, `FEEDBACK_MIN_VOLUME = 3`, `LOW_ACCEPTANCE_THRESHOLD = 0.5`. Risks carry a level (low/medium/high), a score (1-100), and a human-readable reason (e.g. recurrence of critical security findings, security-category concentration, recent overall deterioration, low feedback acceptance, complexity density). Determinism is verified by a test that asserts two runs produce identical `metrics` dumps.

## 8. Feedback & activity

`compute_feedback` collapses per-finding feedback into accepted/dismissed totals, per-category and per-severity maps, and acceptance rate. `compute_activity` reports review count, unique PRs, reviews this week (UTC week boundary), findings this month, plus first/latest review timestamps. All comparisons are timezone-safe (see item 15).

## 9. Gemini narrative

When a real `GEMINI_API_KEY` is present, `generate_insights_narrative` asks Gemini 2.5 Flash (default) or `GEMINI_MODEL` for strict JSON `{executive_summary, trend_interpretation, risk_explanation, recommendations}`. The prompt deliberately contains **only aggregate metrics** — never findings, diffs, code or secrets. On `GeminiUnavailable` or malformed output the report still completes with `narrative: null`, `model: null`, `status: complete`, matching the Phase 4 behaviour.

## 10. Insight history / API

`GET /insights` lists newest-first with `page`/`per_page`/`repository`/`report_type` filters and `total_pages`. `GET /insights/repository/{owner}/{repository}` returns the latest repository report (404 when none). `GET /insights/{insight_id}` returns one report with ownership 404 otherwise; invalid ObjectIds are 404 (route regex). All are user-scoped.

## 11. Frontend — Insights page

`/insights` renders a trajectory hero, a generator console (repository selector fed from `getRepositories`, optional PR number), a live report view and an archive sidebar. The live view shows the executive summary/narrative blocks (or a Gemini-unavailable notice), metrics stats, severity pie + category bar charts (reusing the Phase 6 charts), activity/feedback, trends rows, triggered risks (level badge + score + reason), and prioritized recommendations. Loading, error-with-retry and empty states are handled throughout; archive entries click through to the full report.

## 12. Frontend — dashboard strip

`CinematicDashboard` fetches the latest insight (`getInsights({ perPage: 1 })`) and renders an `InsightStrip` beneath the hero when a report exists: repo + type, "31 findings across 8 reviews", recommended-actions count, critical count, acceptance rate, and an "Open report" link to `/insights`. It renders nothing (no error splash) on failure or when no report exists yet.

## 13. Tests passed/failed

- Backend: `pytest` — **263 passed, 0 failed (1 deprecation warning)**; `python -m compileall app tests` OK. (`test_insights.py`: 21 tests covering auth, 422 on empty scope, repository vs PR scope, metrics determinism, all 8 risks incl. thresholds, feedback aggregation incl. low-acceptance risk, trends including single-review `insufficient`, history pagination/filtering, latest-by-repo, id ownership, narrative parsing, prompt safety, and the naive-UTC regression test.)
- Frontend: **54 passed / 54 across 16 files, 0 failed**; `npx tsc --noEmit` clean.

## 14. npm build result

- `npm run build` (tsc + vite build) succeeds using a **pre-existing** chunk-size warning on the unchanged `CyberScene` bundle (909.40 kB, gzip 243.59 kB); the insights code ships inside `index` 415.89 kB (gzip 126.99 kB), `react-vendor` 215.74 kB, `charts` 400.09 kB, css 96.02 kB (gzip 17.09 kB).

## 15. Live-browser bug found & fixed

Earlier backend runs (262 passed) did not catch a real-data-only crash: MongoDB decodes BSON datetimes as **offset-naive UTC** by default, while the service computed `week_start` as offset-aware, so `created_at >= week_start` raised `TypeError: can't compare offset-naive and offset-aware datetimes` in `compute_activity`. Because the unhandled 500 dropped the `Access-Control-Allow-Origin` header, the browser surfaced it as `TypeError: Failed to fetch` → "Cannot reach the SmartSDLC backend", although `POST /documents/generate` worked.

Fix: added `_coerce_utc()` in `insight_service.py` — any naive timestamp (or missing `created_at`) is normalized to aware UTC on read at the single source of truth (`_review_created_at`, feedback `created_at`), so all comparisons/min/max/sorts stay timezone-safe. Added `test_generation_handles_naive_utc_timestamps`, seeding reviews + feedback with `tzinfo=None` values. Backend now **263 passed** and a live `POST /insights/generate` returns 200.

## 16. Live browser verification

Via headed Chrome (CDP, profile in the opencode temp dir, authenticated as `sami-142745`), after `docker compose up -d --build backend frontend`:

- `/insights` renders the hero, 11-repository selector, and empty archive.
- Generate → `sami-142745/Tnsif`: `POST /insights/generate` → **HTTP 200**, report **complete**, model **gemini-3.6-flash**, narrative rendered (executive summary, trend interpretation, risk explanation, recommendations), metrics (31 findings, 4 critical / 10 high / 1 medium / 16 low), severity/category charts, activity ("8 reviews · 2 PRs · 8 this week"), feedback (1 accepted / 0 dismissed / 100% acceptance), trends (findings 7 → 24 increasing, critical 1 → 3 increasing, activity stable), and triggered risks.
- Archive shows the generated reports; the dashboard `Latest Intelligence` strip shows "31 findings across 8 reviews · 4 recommended actions · 4 CRITICAL · 31 FINDINGS · 100% ACCEPTANCE · Open report".
- Regression pass: `/documents`, `/history`, `/repositories`, `/pull-requests`, `/feedback` and `/dashboard` all load with no backend errors.

## 17. Docker validation

- `docker compose up -d --build backend frontend` — backend + frontend rebuilt/recreated; **mongo and the legacy `smartsdlc-mongodb` containers were never stopped or removed**; no volumes deleted.
- `curl.exe http://localhost:8000/openapi.json` — **26 routes**, including `/insights/generate`, `/insights/repository/{owner}/{repository}`, `/insights`, `/insights/{insight_id}`.
- `docker compose ps` — backend, frontend, mongo all Up; unhealthy outputs none.

## 18. Security & integrity notes

- Insights require only the user JWT; GitHub token and Gemini key never reach the browser.
- Gemini prompt contains aggregate metrics only — no findings, code, or secrets.
- Reports are immutable, user-scoped, and reference their exact `source_review_ids`.
- 404 (not 403) is returned for other users' reports and invalid IDs; invalid ObjectIds never hit the DB.
- All datetimes are normalized to aware UTC before any comparison.

## 19. Remaining limitations

- Live narrative depends on a real `GEMINI_API_KEY`; with the placeholder/unset key the report degrades cleanly to `narrative: null`.
- Archive timestamps are rendered in UTC on the archive list while the report header uses local time — cosmetic, unchanged by design scope.
- Pre-existing (out of scope, not introduced here): React duplicate-key warning in the dashboard recent-reviews feed, recharts 2.x deprecation notice, `npm audit` entries for transitive dev dependencies, and the CyberScene chunk-size warning.
- Live verification created repository/test reports for `sami-142745/Tnsif` in the user's account — real pipeline artifacts, left in place.

## 20. Conclusion

Phase 7 ships a complete, deterministic insights system: backend metrics/trends/risk engine/feedback/activity over real review history with a Gemini narrative layer, and a full frontend with report generation, live report view, archive and a dashboard intelligence strip. All 263 backend and 54 frontend tests pass, the TypeScript build is clean, and the feature is verified end-to-end in the browser against live data — including the fix for the naive-UTC crash that only surfaced with real stored records.