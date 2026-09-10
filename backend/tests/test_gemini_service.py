import json

import pytest

from app.services.gemini_service import (
    GeminiUnavailable,
    _parse_json,
    _strip_markdown_fences,
    build_review_prompt,
    review_code,
)


SAMPLE_CONTEXT = {
    "repository": "octocat/Hello-World",
    "pull_request_number": 12,
    "pull_request_title": "Fix bug",
    "diff": "```diff\n+password = 'hunter2'\n```",
    "heuristic_findings": [
        {"id": "h-abc", "title": "Hardcoded credential", "severity": "low", "file": "config.py"}
    ],
}


def test_strip_markdown_fences_plain_json():
    assert _strip_markdown_fences('{"findings": []}') == '{"findings": []}'


def test_strip_markdown_fences_fenced():
    text = '```json\n{"findings": []}\n```'
    assert _strip_markdown_fences(text) == '{"findings": []}'


def test_strip_markdown_fences_fenced_no_lang():
    text = '```\n{"findings": []}\n```'
    assert _strip_markdown_fences(text) == '{"findings": []}'


def test_parse_json_valid():
    result = _parse_json('{"findings": [{"title": "test"}]}')
    assert result["findings"][0]["title"] == "test"


def test_parse_json_fenced():
    result = _parse_json('```json\n{"findings": []}\n```')
    assert result["findings"] == []


def test_build_review_prompt_contains_repository():
    prompt = build_review_prompt(SAMPLE_CONTEXT)
    assert "octocat/Hello-World" in prompt


def test_build_review_prompt_contains_pr_number():
    prompt = build_review_prompt(SAMPLE_CONTEXT)
    assert "#12" in prompt


def test_build_review_prompt_contains_diff():
    prompt = build_review_prompt(SAMPLE_CONTEXT)
    assert "password" in prompt


def test_build_review_prompt_contains_heuristic():
    prompt = build_review_prompt(SAMPLE_CONTEXT)
    assert "Hardcoded credential" in prompt


def test_build_review_prompt_includes_security_rules():
    prompt = build_review_prompt(SAMPLE_CONTEXT)
    assert "UNTRUSTED INPUT" in prompt


@pytest.mark.asyncio
async def test_review_code_missing_api_key(monkeypatch):
    monkeypatch.setattr("app.services.gemini_service.settings.GEMINI_API_KEY", "change_me")
    with pytest.raises(GeminiUnavailable):
        await review_code(SAMPLE_CONTEXT)


class FakeResponse:
    def __init__(self, text: str):
        self.text = text


def _fake_generate(model, prompt, generation_config):
    return FakeResponse(json.dumps({"findings": []}))


@pytest.mark.asyncio
async def test_review_code_empty_findings(monkeypatch):
    monkeypatch.setattr("app.services.gemini_service.settings.GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.services.gemini_service._generate_content_sync", _fake_generate)
    result = await review_code(SAMPLE_CONTEXT)
    assert result == []


def _fake_generate_with_finding(model, prompt, generation_config):
    payload = {
        "findings": [
            {
                "title": "SQL injection risk",
                "description": "User input in query",
                "severity": "high",
                "category": "security",
                "file": "db.py",
                "line": 15,
                "code": 'execute(f"SELECT * FROM users WHERE id={user_id}")',
                "recommendation": "Use parameterized query",
                "confidence": 0.8,
            }
        ]
    }
    return FakeResponse(json.dumps(payload))


@pytest.mark.asyncio
async def test_review_code_returns_structured_findings(monkeypatch):
    monkeypatch.setattr("app.services.gemini_service.settings.GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.services.gemini_service._generate_content_sync", _fake_generate_with_finding)
    result = await review_code(SAMPLE_CONTEXT)
    assert len(result) == 1
    assert result[0]["title"] == "SQL injection risk"
    assert result[0]["severity"] == "high"
    assert result[0]["category"] == "security"
    assert result[0]["source"] == "gemini"
    assert "g-" in result[0]["id"]


def _fake_generate_malformed(model, prompt, generation_config):
    return FakeResponse("NOT JSON AT ALL")


@pytest.mark.asyncio
async def test_review_code_malformed_json_returns_empty(monkeypatch):
    monkeypatch.setattr("app.services.gemini_service.settings.GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.services.gemini_service._generate_content_sync", _fake_generate_malformed)
    with pytest.raises(GeminiUnavailable):
        await review_code(SAMPLE_CONTEXT)


def _fake_generate_list(model, prompt, generation_config):
    payload = [
        {"title": "Bug", "description": "Off by one", "severity": "medium", "category": "bug"},
        {"title": "Not a dict", "severity": "low"},
    ]
    return FakeResponse(json.dumps(payload))


@pytest.mark.asyncio
async def test_review_code_drops_invalid_items(monkeypatch):
    monkeypatch.setattr("app.services.gemini_service.settings.GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.services.gemini_service._generate_content_sync", _fake_generate_list)
    result = await review_code(SAMPLE_CONTEXT)
    assert len(result) == 2
    assert result[0]["title"] == "Bug"
    assert result[1]["title"] == "Not a dict"
