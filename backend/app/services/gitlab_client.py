from __future__ import annotations

from urllib.parse import quote

import httpx

from app.services.scm import ScmAPIError

GITLAB_API_BASE = "https://gitlab.com/api/v4"

MAX_PER_PAGE = 100

_STATE_MAP = {
    "open": "opened",
    "closed": "closed",
    "all": "all",
}


def _new_http_client(**kwargs) -> httpx.AsyncClient:
    return httpx.AsyncClient(**kwargs)


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code < 400:
        return

    try:
        payload = resp.json()
        message = payload.get("message") or "GitLab API error"
    except Exception:
        message = "GitLab API error"

    if resp.status_code == 429:
        category = "rate_limit"
    elif resp.status_code in (401, 403):
        category = "authentication"
    elif resp.status_code == 404:
        category = "not_found"
    elif resp.status_code >= 500:
        category = "server"
    else:
        category = "unknown"

    raise ScmAPIError(status_code=resp.status_code, message=message, category=category)


def _to_repository(raw: dict) -> dict:
    namespace = raw.get("namespace") or {}
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "full_name": raw.get("path_with_namespace"),
        "private": (raw.get("visibility") or "public") != "public",
        "html_url": raw.get("web_url"),
        "default_branch": raw.get("default_branch"),
        "description": raw.get("description"),
        "owner": namespace.get("full_path"),
    }


def _to_merge_request(raw: dict) -> dict:
    return {
        "number": raw.get("iid"),
        "title": raw.get("title"),
        "state": raw.get("state"),
        "user": (raw.get("author") or {}).get("username"),
        "html_url": raw.get("web_url"),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
        "head": raw.get("source_branch"),
        "head_sha": raw.get("sha"),
        "base": raw.get("target_branch"),
    }


def _count_diff_lines(diff: str | None) -> tuple[int, int]:
    """Count added/removed lines from a GitLab unified diff payload."""
    if not diff:
        return 0, 0
    additions = 0
    deletions = 0
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1
    return additions, deletions


def _to_merge_request_file(raw: dict) -> dict:
    filename = raw.get("new_path") or raw.get("old_path")
    if raw.get("new_file"):
        status = "added"
    elif raw.get("deleted_file"):
        status = "removed"
    elif raw.get("renamed_file"):
        status = "renamed"
    else:
        status = "modified"
    additions, deletions = _count_diff_lines(raw.get("diff"))
    return {
        "filename": filename,
        "status": status,
        "additions": additions,
        "deletions": deletions,
        "changes": additions + deletions,
        "patch": raw.get("diff"),
    }


class GitLabClient:
    def __init__(self, access_token: str, base_url: str = GITLAB_API_BASE, timeout: float = 15.0):
        self.access_token = access_token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self, accept: str = "application/json") -> dict:
        return {
            "PRIVATE-TOKEN": self.access_token,
            "Accept": accept,
        }

    def _project(self, owner: str, repo: str) -> str:
        return quote(f"{owner}/{repo}", safe="")

    async def _get(self, path: str, params: dict | None = None, raw: bool = False) -> httpx.Response:
        headers = self._headers(accept="text/plain" if raw else "application/json")
        try:
            async with _new_http_client(timeout=self.timeout) as client:
                resp = await client.get(f"{self.base_url}{path}", params=params, headers=headers)
        except httpx.TimeoutException:
            raise ScmAPIError(status_code=0, message="GitLab request timed out", category="network")
        except httpx.HTTPError:
            raise ScmAPIError(status_code=0, message="Could not reach the GitLab API", category="network")

        _raise_for_status(resp)
        return resp

    async def get_user(self) -> dict:
        resp = await self._get("/user")
        return resp.json()

    async def get_repository(self, owner: str, repo: str) -> dict:
        resp = await self._get(f"/projects/{self._project(owner, repo)}")
        return _to_repository(resp.json())

    async def list_repositories(self, page: int = 1, per_page: int = 30) -> dict:
        per_page = max(1, min(per_page, MAX_PER_PAGE))
        resp = await self._get(
            "/projects",
            params={
                "membership": "true",
                "order_by": "last_activity_at",
                "simple": "true",
                "page": page,
                "per_page": per_page,
            },
        )
        return {
            "repositories": [_to_repository(item) for item in resp.json()],
            "page": page,
            "per_page": per_page,
            "has_more": bool(resp.headers.get("X-Next-Page")),
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
        gitlab_state = _STATE_MAP.get(state, "opened")
        resp = await self._get(
            f"/projects/{self._project(owner, repo)}/merge_requests",
            params={"state": gitlab_state, "page": page, "per_page": per_page},
        )
        return {
            "pull_requests": [_to_merge_request(item) for item in resp.json()],
            "page": page,
            "per_page": per_page,
            "has_more": bool(resp.headers.get("X-Next-Page")),
        }

    async def get_pull_request(self, owner: str, repo: str, number: int) -> dict:
        resp = await self._get(f"/projects/{self._project(owner, repo)}/merge_requests/{number}")
        return _to_merge_request(resp.json())

    async def get_pull_request_files(self, owner: str, repo: str, number: int) -> list[dict]:
        resp = await self._get(f"/projects/{self._project(owner, repo)}/merge_requests/{number}/changes")
        return [_to_merge_request_file(item) for item in (resp.json().get("changes") or [])]

    async def get_pull_request_diff(self, owner: str, repo: str, number: int) -> str:
        resp = await self._get(f"/projects/{self._project(owner, repo)}/merge_requests/{number}.diff", raw=True)
        return resp.text

    async def get_repository_tree(
        self,
        owner: str,
        repo: str,
        ref: str | None = None,
    ) -> dict:
        params: dict = {"recursive": "true"}
        if ref:
            params["ref"] = ref
        resp = await self._get(f"/projects/{self._project(owner, repo)}/repository/tree", params=params)
        entries = resp.json()
        return {
            "tree": [
                {
                    "path": item.get("path"),
                    "mode": item.get("mode"),
                    "type": item.get("type"),
                    "sha": item.get("id"),
                    "url": "",
                }
                for item in entries
                if item.get("type") in ("tree", "blob")
            ],
            "truncated": False,
        }

    async def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str | None = None,
    ) -> str:
        encoded = quote(path, safe="")
        params = {"ref": ref} if ref else None
        resp = await self._get(
            f"/projects/{self._project(owner, repo)}/repository/files/{encoded}/raw",
            params=params,
            raw=True,
        )
        return resp.text