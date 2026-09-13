from __future__ import annotations

from urllib.parse import quote

import httpx

from app.services.scm import ScmAPIError

GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_HEADERS = {"Accept": "application/vnd.github+json"}
GITHUB_DIFF_ACCEPT = "application/vnd.github.v3.diff"
GITHUB_RAW_ACCEPT = "application/vnd.github.raw"

MAX_PER_PAGE = 100

GitHubAPIError = ScmAPIError


def _new_http_client(**kwargs) -> httpx.AsyncClient:
    return httpx.AsyncClient(**kwargs)


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code < 400:
        return

    try:
        payload = resp.json()
        message = payload.get("message") or "GitHub API error"
    except Exception:
        message = "GitHub API error"

    if resp.status_code == 429:
        category = "rate_limit"
    elif resp.status_code in (401, 403):
        category = (
            "rate_limit"
            if resp.headers.get("X-RateLimit-Remaining") == "0"
            else "authentication"
        )
    elif resp.status_code == 404:
        category = "not_found"
    elif resp.status_code >= 500:
        category = "server"
    else:
        category = "unknown"

    raise GitHubAPIError(status_code=resp.status_code, message=message, category=category)


def _has_next_page(link_header: str | None) -> bool:
    return bool(link_header) and 'rel="next"' in link_header


def _to_repository(raw: dict) -> dict:
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "full_name": raw.get("full_name"),
        "private": raw.get("private", False),
        "html_url": raw.get("html_url"),
        "default_branch": raw.get("default_branch"),
        "description": raw.get("description"),
        "owner": (raw.get("owner") or {}).get("login"),
    }


def _to_pull_request(raw: dict) -> dict:
    return {
        "number": raw.get("number"),
        "title": raw.get("title"),
        "state": raw.get("state"),
        "user": (raw.get("user") or {}).get("login"),
        "html_url": raw.get("html_url"),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
        "head": (raw.get("head") or {}).get("ref"),
        "head_sha": (raw.get("head") or {}).get("sha"),
        "base": (raw.get("base") or {}).get("ref"),
    }


def _to_pull_request_file(raw: dict) -> dict:
    return {
        "filename": raw.get("filename"),
        "status": raw.get("status"),
        "additions": raw.get("additions", 0),
        "deletions": raw.get("deletions", 0),
        "changes": raw.get("changes", 0),
        "patch": raw.get("patch"),
    }


class GitHubClient:
    def __init__(self, access_token: str, base_url: str = GITHUB_API_BASE, timeout: float = 15.0):
        self.access_token = access_token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            **GITHUB_API_HEADERS,
        }

    async def _get(self, path: str, params: dict | None = None, accept: str | None = None) -> httpx.Response:
        headers = self._headers()
        if accept:
            headers["Accept"] = accept
        try:
            async with _new_http_client(timeout=self.timeout) as client:
                resp = await client.get(f"{self.base_url}{path}", params=params, headers=headers)
        except httpx.TimeoutException:
            raise GitHubAPIError(status_code=0, message="GitHub request timed out", category="network")
        except httpx.HTTPError:
            raise GitHubAPIError(status_code=0, message="Could not reach the GitHub API", category="network")

        _raise_for_status(resp)
        return resp

    async def get_user(self) -> dict:
        resp = await self._get("/user")
        return resp.json()

    async def get_repository(self, owner: str, repo: str) -> dict:
        resp = await self._get(f"/repos/{owner}/{repo}")
        return _to_repository(resp.json())

    async def list_repositories(self, page: int = 1, per_page: int = 30) -> dict:
        per_page = max(1, min(per_page, MAX_PER_PAGE))
        resp = await self._get(
            "/user/repos",
            params={"page": page, "per_page": per_page, "sort": "updated"},
        )
        return {
            "repositories": [_to_repository(item) for item in resp.json()],
            "page": page,
            "per_page": per_page,
            "has_more": _has_next_page(resp.headers.get("Link")),
        }

    async def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        page: int = 1,
        per_page: int = 30,
    ) -> dict:
        per_page = max(1, min(per_page, MAX_PER_PAGE))
        resp = await self._get(
            f"/repos/{owner}/{repo}/pulls",
            params={"state": state, "page": page, "per_page": per_page},
        )
        return {
            "pull_requests": [_to_pull_request(item) for item in resp.json()],
            "page": page,
            "per_page": per_page,
            "has_more": _has_next_page(resp.headers.get("Link")),
        }

    async def get_pull_request(self, owner: str, repo: str, number: int) -> dict:
        resp = await self._get(f"/repos/{owner}/{repo}/pulls/{number}")
        return _to_pull_request(resp.json())

    async def get_pull_request_files(self, owner: str, repo: str, number: int) -> list[dict]:
        resp = await self._get(f"/repos/{owner}/{repo}/pulls/{number}/files")
        return [_to_pull_request_file(item) for item in resp.json()]

    async def get_pull_request_diff(self, owner: str, repo: str, number: int) -> str:
        resp = await self._get(
            f"/repos/{owner}/{repo}/pulls/{number}",
            accept=GITHUB_DIFF_ACCEPT,
        )
        return resp.text

    async def get_repository_tree(
        self,
        owner: str,
        repo: str,
        ref: str | None = None,
    ) -> dict:
        tree_ref = quote(ref, safe="") if ref else "HEAD"
        resp = await self._get(
            f"/repos/{owner}/{repo}/git/trees/{tree_ref}",
            params={"recursive": "1"},
        )
        return resp.json()

    async def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str | None = None,
    ) -> str:
        encoded = quote(path, safe="/")
        resp = await self._get(
            f"/repos/{owner}/{repo}/contents/{encoded}",
            params={"ref": ref} if ref else None,
            accept=GITHUB_RAW_ACCEPT,
        )
        return resp.text