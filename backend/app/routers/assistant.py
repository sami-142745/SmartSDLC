"""HTTP surface for the AI Developer Assistant.

The assistant is context-aware and uses local intelligence first, falling
back to Gemini only when language reasoning is actually needed.

Authentication
--------------
Every route requires a signed-in user (``get_current_user``).

Route registration
------------------
Mounted twice by :mod:`app.main`: at the root, matching every other router here,
and under ``/api``, matching the documented public contract.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantCodeActionRequest,
    AssistantCodeActionResponse,
    AssistantConversation,
    AssistantConversationListResponse,
    AssistantMode,
)
from app.services import assistant_service
from app.services.assistant_service import AssistantError
from app.services.security import get_current_user

router = APIRouter()

BASE = "/assistant"


@router.post(f"{BASE}/{{owner}}/{{repo}}/chat", response_model=AssistantChatResponse)
async def chat(
    owner: str,
    repo: str,
    body: AssistantChatRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> AssistantChatResponse:
    """Send a message to the AI Developer Assistant.

    The assistant first tries to answer deterministically from loaded data.
    If that fails, it falls back to Gemini with bounded context.
    """
    try:
        return await assistant_service.chat(
            user["github_id"],
            body,
            conversation_id=body.conversation_id,
        )
    except AssistantError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(f"{BASE}/{{owner}}/{{repo}}/code-action", response_model=AssistantCodeActionResponse)
async def code_action(
    owner: str,
    repo: str,
    body: AssistantCodeActionRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> AssistantCodeActionResponse:
    """Perform a code action (explain, refactor, generate tests, suggest fix).

    Returns the original code, generated code, explanation, and diff.
    """
    try:
        return await assistant_service.perform_code_action(
            user["github_id"],
            body,
        )
    except AssistantError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get(f"{BASE}/{{owner}}/{{repo}}/conversations", response_model=AssistantConversationListResponse)
async def list_conversations(
    owner: str,
    repo: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: dict[str, Any] = Depends(get_current_user),
) -> AssistantConversationListResponse:
    """List conversations for a repository."""
    data = await assistant_service.list_conversations(
        user["github_id"],
        page=page,
        per_page=per_page,
    )
    return AssistantConversationListResponse(**data)


@router.get(f"{BASE}/{{owner}}/{{repo}}/conversations/{{conversation_id}}", response_model=AssistantConversation)
async def get_conversation(
    owner: str,
    repo: str,
    conversation_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> AssistantConversation:
    """Get a conversation by ID."""
    conversation = await assistant_service.get_conversation(
        user["github_id"],
        conversation_id,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation
