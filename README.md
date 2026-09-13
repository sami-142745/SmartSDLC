# SmartSDLC

Production-ready sample project: React (Vite + Tailwind) + FastAPI + MongoDB + GitHub OAuth + Gemini AI + GitHub Webhooks + Docker Compose.

## Architecture

- `backend/` — FastAPI app. Heuristic + Gemini AI pull-request reviews, GitHub OAuth, webhooks, review feedback, and dashboard aggregations. MongoDB via Motor.
- `frontend/` — React 18 + TypeScript + Tailwind + Vite SPA. GitHub OAuth sign-in, dashboard, repositories, pull requests, diff viewer, AI review UI with find/dismiss feedback, review history, and settings.
- `docker-compose.yml` — runs MongoDB, the backend on `:8000`, and the frontend dev server on `:5173`.

## Run locally

1) Create the environment file:

```bash
cp .env.example .env
```

Fill in at minimum:
- `GITHUB_CLIENT_ID`
- `GITHUB_CLIENT_SECRET`
- `GITHUB_OAUTH_CALLBACK_URL` (set this to `http://localhost:5173/login/callback`)
- `JWT_SECRET`
- `MONGODB_URI`
- `GEMINI_API_KEY`

2) Start all services:

```bash
docker compose up --build
```

3) Open the app at http://localhost:5173 and sign in with GitHub.

> The GitHub OAuth app must allow callback URL `http://localhost:5173/login/callback`. After signing in, the browser lands on the frontend callback, exchanges the code with the backend at `GET /auth/github/callback`, and stores only the resulting JWT in `localStorage` (github_access_token).

### Frontend in development (without Docker)

```bash
cd frontend
npm install
npm run dev
```

The API base URL is taken from `VITE_API_BASE_URL` (`frontend/.env` or root `.env`; defaults to `http://localhost:8000`). The frontend container reads the root `.env`.

## Routes (frontend)

| Route | Purpose |
| --- | --- |
| `/login` | Sign in with GitHub |
| `/login/callback` | Handles the GitHub OAuth redirect |
| `/dashboard` | Metrics, severity/category charts, recent reviews, repository metrics |
| `/repositories` | Browse repositories |
| `/repositories/:owner/:repo` | Pull requests for a repository |
| `/pull-requests` | Pick a repository and browse PRs |
| `/pull-requests/:owner/:repo/:number` | PR details, changed files, unified diff |
| `/reviews/:owner/:repo/:number` | Run/view AI review, findings, accept/dismiss feedback |
| `/history` | Paginated review history with filters |
| `/feedback` | Accepted/dismissed feedback log |
| `/settings` | Account, connection health, security notes |

## API (backend)

- `GET /auth/github/login` — start GitHub OAuth
- `GET /auth/github/callback` — exchange code for a JWT
- `POST /github/connect` — connect a GitHub token
- `GET /repositories`
- `GET /pullrequests`, `GET /pullrequests/{owner}/{repo}/{number}`, `.../files`, `.../diff`
- `POST /reviews/{owner}/{repo}/{number}` — run an AI review
- `GET /reviews/{owner}/{repo}/{number}`, `.../findings`
- `POST /reviews/{owner}/{repo}/{number}/findings/{finding_id}/feedback` — accept/dismiss
- `GET /reviews/feedback`
- `GET /dashboard`, `GET /history`, `GET /dashboard/repositories`, `GET /dashboard/feedback-summary`
- `POST /webhook`
- Interactive docs: http://localhost:8000/docs

## Testing

Backend (from `backend/`, uses `.venv`):

```bash
python -m pytest tests -q   # 338 tests
```

Frontend (from `frontend/`):

```bash
npm test                     # Vitest + React Testing Library
npm run build                # tsc --noEmit + vite build
```

## Notes

- Heuristic + Gemini findings are each stored with severity, category, source, line, code, recommendation, and confidence. Findings carry a stable ID so accept/dismiss feedback upserts and survives re-runs.
- When Gemini is unavailable (no API key or error) a review completes in `gemini_unavailable` status with heuristic counts only.
- Feedback aggregates are reported per severity and category in `GET /dashboard/feedback-summary`.

## Known limitations

- **GitLab PAT provisioning:** GitLab repository/Merge Request integration currently requires a GitLab Personal Access Token to be available to the backend/provider configuration. There is no separate GitLab PAT entry/OAuth UX yet; the current demo uses the configured provider credential rather than supporting multiple independent SCM accounts.

- **GitLab webhook ingestion:** Automatic webhook-triggered review is currently implemented for GitHub. GitLab Merge Requests can be accessed through the provider integration, but GitLab webhook ingestion for automatic MR review is not yet enabled.

- **WebGL bundle:** The cinematic 3D scene produces a relatively large lazy-loaded WebGL chunk. This is intentional for the immersive visualization layer.

- **Testing warnings:** Some test environments may emit non-fatal resource warnings from database handles; these do not currently cause test failures.