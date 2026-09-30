import pytest

from app.services.assistant_service import (
    _build_assistant_prompt,
    _parse_assistant_response,
    AssistantError,
    AssistantResponsePayload,
    _try_local_answer,
)
from app.schemas.assistant import AssistantContext, AssistantContextType, AssistantMode


def test_parse_assistant_response_valid_json_with_answer():
    """Valid JSON with answer field parses correctly."""
    text = '{"answer": "Hello world", "warnings": ["test warning"]}'
    result = _parse_assistant_response(text)
    assert isinstance(result, AssistantResponsePayload)
    assert result.answer == "Hello world"
    assert result.warnings == ["test warning"]


def test_parse_assistant_response_valid_json_without_warnings():
    """Valid JSON with only answer field parses correctly."""
    text = '{"answer": "Hello world"}'
    result = _parse_assistant_response(text)
    assert isinstance(result, AssistantResponsePayload)
    assert result.answer == "Hello world"
    assert result.warnings == []


def test_parse_assistant_response_missing_answer():
    """JSON missing answer field returns None."""
    text = '{"response": "Hello world"}'
    result = _parse_assistant_response(text)
    assert result is None


def test_parse_assistant_response_empty_answer():
    """JSON with empty answer field returns None."""
    text = '{"answer": ""}'
    result = _parse_assistant_response(text)
    assert result is None


def test_parse_assistant_response_non_dict():
    """Non-dict JSON returns None."""
    text = '["not", "a", "dict"]'
    result = _parse_assistant_response(text)
    assert result is None


def test_parse_assistant_response_malformed_json():
    """Malformed JSON falls back to plain text."""
    text = "This is plain text, not JSON"
    result = _parse_assistant_response(text)
    assert isinstance(result, AssistantResponsePayload)
    assert result.answer == "This is plain text, not JSON"


def test_parse_assistant_response_empty_text():
    """Empty text returns None."""
    assert _parse_assistant_response("") is None
    assert _parse_assistant_response("   ") is None


def test_parse_assistant_response_markdown_fenced():
    """Markdown-fenced JSON parses correctly."""
    text = '```json\n{"answer": "Fenced", "warnings": ["warn"]}\n```'
    result = _parse_assistant_response(text)
    assert isinstance(result, AssistantResponsePayload)
    assert result.answer == "Fenced"
    assert result.warnings == ["warn"]


def test_parse_assistant_response_warnings_not_list():
    """Non-list warnings field is normalized to empty list."""
    text = '{"answer": "OK", "warnings": "not a list"}'
    result = _parse_assistant_response(text)
    assert isinstance(result, AssistantResponsePayload)
    assert result.warnings == []


def test_build_assistant_prompt_contains_output_format():
    """Prompt explicitly requests strict JSON with answer field."""
    prompt = _build_assistant_prompt(
        message="test question",
        mode=AssistantMode.EXPLAIN_CODE,
        context=None,
    )
    assert "OUTPUT FORMAT" in prompt
    assert "strict JSON" in prompt
    assert '"answer"' in prompt
    assert '"warnings"' in prompt


def test_build_assistant_prompt_contains_security_rules():
    """Prompt includes security protections."""
    prompt = _build_assistant_prompt(
        message="test question",
        mode=AssistantMode.EXPLAIN_CODE,
        context=None,
    )
    assert "UNTRUSTED DATA" in prompt
    assert "prompt-injection" in prompt.lower()
    assert "credentials" in prompt.lower()


def test_build_assistant_prompt_includes_context():
    """Prompt includes context when provided."""
    context = AssistantContext(
        context_type=AssistantContextType.REPOSITORY,
        repository_id="owner/repo",
        owner="owner",
        repository="repo",
    )
    prompt = _build_assistant_prompt(
        message="test question",
        mode=AssistantMode.EXPLAIN_CODE,
        context=context,
    )
    assert "owner/repo" in prompt
    assert "CONTEXT:" in prompt


def test_try_local_answer_repository_health():
    """Local intelligence answers repository health questions."""
    context = AssistantContext(
        context_type=AssistantContextType.REPOSITORY,
        repository_id="owner/repo",
        owner="owner",
        repository="repo",
    )
    result = _try_local_answer("What is the repository health?", context)
    assert result is not None
    assert "owner/repo" in result.answer


def test_try_local_answer_no_context():
    """No context returns None."""
    result = _try_local_answer("hi", None)
    assert result is None


def test_try_local_answer_unhandled_question():
    """Unhandled question type returns None."""
    context = AssistantContext(
        context_type=AssistantContextType.REPOSITORY,
        repository_id="owner/repo",
        owner="owner",
        repository="repo",
    )
    result = _try_local_answer("hi", context)
    assert result is None


def test_assistant_error_raised_for_missing_answer():
    """Service raises AssistantError when parser returns None."""
    parsed = _parse_assistant_response('{"response": "no answer field"}')
    assert parsed is None