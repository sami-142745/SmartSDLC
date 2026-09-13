# Phase 12 — GitLab Provider Support: Final Report

## 1. Files created

Backend:

- `backend/app/services/scm.py` — provider abstraction: `ScmProvider` enum (github|gitlab), `ScmAPIError` (status/message/category), `ERROR_STATUS_BY_CATEGORY`, `scm_error_response(provider, error)` (provider-aware error mapping), `merge_request_term(provider)`, and `get_scm_client` factory.
- `backend/app/services/gitlab_client.py` — `GitLabClient` adapter over `https://gitlab.com/api/v4` exposing the same immutable interface as `GitHubClient`: `get_user`, `get_repository`, `list_repositories` (`X-Next-Page` → `has_more`), `list_pull_requests` (state map open→opened / closed→closed / all→all), `get_pull_request`, `get_pull_request_files` (additions/deletions computed from `diff` lines), `get_pull_request_diff` (`.diff` text), `get_repository_tree` (reshaped `{path,type,sha,url}` entries) and `get_file_content` (`.raw` ref). Project ids are URL-encoded `owner%2Frepo`.
- `backend/tests/test_scm.py` — `ScmProvider` values, `merge_request_term`, `get_scm_client` dispatch, error mapping (including the provider-aware GitLab branch).
- `backend/tests/test_gitlab_client.py` — 13 async tests (mock HTTP transport) covering endpoints, headers/PAT, pagination, project path encoding, MR state mapping, file status/count computation, raw diff payload, tree reshaping and raw file access.

Frontend:

- `frontend/src/components/ProviderToggle.tsx` — segmented GitHub/GitLab control (`role="tablist"`).
- `frontend/src/__tests__/ScmProvider.test.tsx` — 4 tests: repository list retargets to GitLab, `PullRequestsPage` merge-request terminology, `RepoPage` GitLab rendering/links, `PullRequestDetailPage` GitLab link + provider passthrough.

## 2. Files modified

Backend:

- `backend/app/services/github_client.py` — `GitHubAPIError = ScmAPIError` alias so `except GitHubAPIError` catches both adapters.
- `backend/app/routers/github.py` — every route gained `provider: ScmProvider = Query(ScmProvider.github)` and now routes through `_client_for(provider, token)`; errors use the shared `scm_error_response(provider, e)` (no more local `_error_from_github`).
- `backend/app/routers/reviews.py`, `backend/app/routers/documents.py` — same provider query + shared error mapping; workflows persist `provider.value`.
- `backend/tests/test_github_routes.py` — 2 new regression tests (GitLab auth failure stays session-safe; GitHub genuine 401 unchanged). Existing route tests still patch `app.routers.github.GitHubClient`, kept intact because the routers branch inline.

Frontend:

- `frontend/src/types/index.ts` — `ScmProvider` type.
- `frontend/src/api/github.ts` — all 5 functions accept `provider: ScmProvider = 'github'` (appended last so existing `toHaveBeenCalledWith` assertions kept meaning) and attach `?provider=` only for GitLab.
- `frontend/src/api/reviews.ts` — `runReview` accepts `provider`, posts `provider=gitlab` when set.
- `frontend/src/pages/RepositoriesPage.tsx` — persistent header + provider toggle; refetches per provider; detail links carry `?provider=gitlab`; per-provider empty-state copy.
- `frontend/src/pages/PullRequestsPage.tsx` — toggle in the route filters; helper copy becomes "MERGE REQUESTS / merge request(s)" for GitLab; navigation carries the provider.
- `frontend/src/pages/RepoPage.tsx` — reads `?provider=`, passes it through, dynamic "Repository security map · GitHub/GitLab", "Open on GitHub/GitLab", and merge-request terminology.
- `frontend/src/pages/PullRequestDetailPage.tsx` — provider param on detail/diff/files calls, "Open on GitLab", and the review link carries `?provider=`.
- `frontend/src/pages/ReviewPage.tsx` — reads `?provider=` and forwards it to `runReview`.
- `frontend/src/__tests__/RepoPage.test.tsx`, `frontend/src/__tests__/ReviewPage.test.tsx` — updated for the appended provider arg.

## 3. Provider abstraction

`ScmProvider` drives every cross-cutting decision. Providers never leak past the router layer: review and documentation pipelines receive `provider.value` and reuse the same GitHub-shaped data so no other service changes were required. `scm_error_response` centralizes the mapping so every router returns identical semantics.

## 4. GitLab client adapter

`GitLabClient(token)` uses the connected account token as a `PRIVATE-TOKEN` header against the v4 API (pragmatic Phase-12 adapter — no new OAuth flow). Outputs are reshaped to the GitHub-client contract (`full_name`, `number`, `head`, `base`, `user`, `additions/deletions`, `html_url`, …) so callers cannot tell which provider served the data. Pagination reuses `X-Next-Page`.

## 5. Error semantics

If the reused GitHub token is rejected by GitLab (HTTP 401 → category `authentication`) the response is now a **400** with a clear "connect a GitLab Personal Access Token" message — never a 401. Returning 401 there was actively harmful: the frontend interceptor treats any 401 as session expiry and logs the user out. A genuine GitHub token failure keeps its 401 (session) semantics.

## 6. Terminology

`merge_request_term` and the frontend `changeTerm` helpers switch "pull request" → "merge request" for GitLab across loading/error/empty states, the `PullRequestsPage` hero (PULL REQUESTS → MERGE REQUESTS), filters and detail links.

## 7. Frontend

The provider toggle appears on `/repositories` (hero) and `/pull-requests` (route filters); switching refetches on the provider. Later pages read `?provider=` from the location so the choice survives navigation, and GitLab flows stay coherent end-to-end (repository map → PR list → detail → review).

## 8. Tests passed/failed

- Backend: `pytest` — **338 passed, 0 failed, 2 warnings**; `python -m compileall -q app tests` OK. (Phase 12 added 21 tests: scm + gitlab client + provider passthrough + the two error-semantics regressions; previous totals were 315 → 336 → 338.)
- Frontend: **72 passed / 72 across 20 files, 0 failed**; `npx tsc --noEmit` clean.

## 9. npm build result

`npm run build` — **built in 14.98 s**, no errors (only the pre-existing CyberScene chunk-size warning).

## 10. Live-browser bug found & fixed

Automated tests passed but the live browser exposed a Phase-12-specific failure: toggling the provider to GitLab triggered `GET /repositories?provider=gitlab`, GitLab rejected the reused token with 401, the router mapped it straight to HTTP 401, and the frontend interceptor cleared the JWT and bounced `sami-142745` back to `/login`. Fix: provider-aware mapping in `scm.py` (GitLab `authentication` → 400 with a connect-PAT message; GitHub unchanged), wired through `github.py`, `reviews.py` and `documents.py`, with two regression tests. Backend 338 passed after the fix.

## 11. Live browser verification

Via headed Chrome (CDP, authenticated as `sami-142745`) after `docker compose up -d --build backend frontend`:

- `/repositories`: "GitHub · live feed" with live repositories (SmartSDLC, JobWise-AI, WEXA-AI, …); toggling GitLab switches the feed label, renders the connect-PAT error card, and **keeps the session** (no logout).
- `/pull-requests`: "PULL REQUESTS · Forwarded change pipeline · GitHub" → toggle → "MERGE REQUESTS · Forwarded change pipeline · GitLab".
- `/repositories/sami-142745/SmartSDLC`: repository map, "Open on GitHub ↗", "No open pull requests".
- `/workflows`: "Workflow Orchestration" + explicit empty state ("No workflows recorded yet.").
- `/feedback`: learning layer (1 accepted / 0 dismissed / 100%), neural ledger, and "ADAPTIVE REVIEW PRIORITIZATION" panel with the no-signals-yet message.
- `/settings`: account/connection/security + "WEBHOOK DELIVERIES" empty state.
- Backend log confirms `GET /repositories?page=1&per_page=30` → 200 and `&provider=gitlab` → **400** (not 401).

## 12. Docker validation

- `docker compose up -d --build backend frontend` — backend/frontend rebuilt and recreated; **mongo and the legacy `smartsdlc-mongodb` container were never stopped, removed, pruned or restarted** (status stayed "Up 3 days" throughout; no volumes deleted; no `--remove-orphans` used).
- `docker ps` — backend (:8000), frontend (:5173), mongo (:27018), legacy mongodb (:27017) all Up.

## 13. Security & integrity notes

- JWT is the only credential in the browser; GitHub/GitLab tokens and the Gemini key never reach the frontend.
- GitLab auth failures never masquerade as session expiry again.
- Provider tokens are read server-side via `GET`-supported dependency guards; no secret is logged (no `PRIVATE-TOKEN`, `Authorization`, or JWT appears in container logs).
- User-scoped ownership on all reads preserved; provider selection adds no new authz surface.

## 14. Remaining limitations

- GitLab support reuses the GitHub token as a `PRIVATE-TOKEN`; a real GitLab PAT must be connected before GitLab sync works (surfaced as a 400 error card, not a logout). No GitLab OAuth flow is built yet.
- No GitLab webhook events are ingested yet (webhooks remain GitHub-shaped).
- Terminology swaps on three top-level strings only; "pull requests" in Flow-steps of the pipeline banner stays as designed.
- Pre-existing, out of scope: CyberScene chunk-size warning, recharts 2.x deprecation notice, `npm audit` transitive dev entries.

## 15. Conclusion

Phase 12 ships a provider-aware SCM layer: `ScmProvider` + `scm_error_response`, a full `GitLabClient` adapter with GitHub-compatible output shaping, provider passthrough across repositories/pull requests/reviews/documents, and a frontend whose terminology and navigation adapt to GitLab end-to-end. All 338 backend and 72 frontend tests pass, the TypeScript build is clean, and the feature is verified live in the browser — including the fix for the GitLab-401-logout bug that only surfaced with real requests.