"""Contracts for the AI Developer Assistant.

The assistant is context-aware: it receives only relevant SmartSDLC data,
never an entire repository. It supports multiple modes (explain code,
explain finding, explain architecture, etc.) and can perform code actions
(explain, refactor, generate tests, suggest fix).

Security:
- Repository content is untrusted input
- Secrets are never sent to the model
- Prompt injection from repository content is prevented
- The system prompt always takes priority over repository text
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AssistantMode(str, Enum):
    """Supported assistant modes."""

    EXPLAIN_CODE = "explain_code"
    EXPLAIN_FINDING = "explain_finding"
    EXPLAIN_ARCHITECTURE = "explain_architecture"
    EXPLAIN_REPOSITORY = "explain_repository"
    EXPLAIN_AI_REVIEW = "explain_ai_review"
    EXPLAIN_SECURITY = "explain_security"
    EXPLAIN_DEPENDENCY = "explain_dependency"
    DEBUG_ERROR = "debug_error"
    REFACTOR_CODE = "refactor_code"
    GENERATE_TESTS = "generate_tests"
    EXPLAIN_DOCUMENTATION = "explain_documentation"
    EXPLAIN_WORKFLOW = "explain_workflow"


ASSISTANT_MODES = tuple(AssistantMode)

# Human-readable labels for UI
ASSISTANT_MODE_LABELS: dict[AssistantMode, str] = {
    AssistantMode.EXPLAIN_CODE: "Explain Code",
    AssistantMode.EXPLAIN_FINDING: "Explain Finding",
    AssistantMode.EXPLAIN_ARCHITECTURE: "Explain Architecture",
    AssistantMode.EXPLAIN_REPOSITORY: "Explain Repository",
    AssistantMode.EXPLAIN_AI_REVIEW: "Explain AI Review",
    AssistantMode.EXPLAIN_SECURITY: "Explain Security Issue",
    AssistantMode.EXPLAIN_DEPENDENCY: "Explain Dependency Risk",
    AssistantMode.DEBUG_ERROR: "Debug Error",
    AssistantMode.REFACTOR_CODE: "Refactor Code",
    AssistantMode.GENERATE_TESTS: "Generate Tests",
    AssistantMode.EXPLAIN_DOCUMENTATION: "Explain Documentation",
    AssistantMode.EXPLAIN_WORKFLOW: "Explain Workflow Failure",
}


class AssistantContextType(str, Enum):
    """Types of context that can be attached to a conversation."""

    REPOSITORY = "repository"
    FILE = "file"
    CODE = "code"
    ARCHITECTURE_NODE = "architecture_node"
    SECURITY_FINDING = "security_finding"
    AI_REVIEW_FINDING = "ai_review_finding"
    DEPENDENCY = "dependency"
    WORKFLOW_EVENT = "workflow_event"
    DOCUMENTATION = "documentation"
    TEST_RESULT = "test_result"


class AssistantMessageRole(str, Enum):
    """Role of a message in the conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AssistantCodeActionType(str, Enum):
    """Types of code actions the assistant can perform."""

    EXPLAIN = "explain"
    REFACTOR = "refactor"
    GENERATE_TESTS = "generate_tests"
    SUGGEST_FIX = "suggest_fix"


# ---------------------------------------------------------------------------
# Context Models
# ---------------------------------------------------------------------------


class AssistantContext(BaseModel):
    """Context attached to a conversation."""

    model_config = ConfigDict(extra="forbid")

    context_type: AssistantContextType
    repository_id: str
    owner: str
    repository: str
    ref: Optional[str] = None
    commit_sha: Optional[str] = None

    # File-specific context
    file_path: Optional[str] = None
    file_content: Optional[str] = None  # Redacted
    file_language: Optional[str] = None

    # Code-specific context
    code_snippet: Optional[str] = None  # Redacted
    code_start_line: Optional[int] = None
    code_end_line: Optional[int] = None

    # Finding-specific context
    finding_id: Optional[str] = None
    finding_title: Optional[str] = None
    finding_description: Optional[str] = None
    finding_severity: Optional[str] = None
    finding_category: Optional[str] = None
    finding_file: Optional[str] = None
    finding_line: Optional[int] = None
    finding_code: Optional[str] = None  # Redacted
    finding_recommendation: Optional[str] = None

    # Architecture-specific context
    architecture_node_id: Optional[str] = None
    architecture_node_name: Optional[str] = None
    architecture_node_kind: Optional[str] = None
    architecture_node_path: Optional[str] = None
    architecture_evidence: Optional[str] = None

    # Dependency-specific context
    dependency_name: Optional[str] = None
    dependency_version: Optional[str] = None
    dependency_ecosystem: Optional[str] = None
    dependency_risks: list[str] = Field(default_factory=list)
    dependency_license: Optional[str] = None

    # Workflow-specific context
    workflow_event_id: Optional[str] = None
    workflow_event_type: Optional[str] = None
    workflow_event_status: Optional[str] = None
    workflow_event_error: Optional[str] = None

    # Documentation-specific context
    documentation_type: Optional[str] = None
    documentation_title: Optional[str] = None
    documentation_content: Optional[str] = None  # Redacted

    # Test-specific context
    test_file_path: Optional[str] = None
    test_content: Optional[str] = None  # Redacted
    test_validation_status: Optional[str] = None
    test_execution_status: Optional[str] = None

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Message Models
# ---------------------------------------------------------------------------


class AssistantMessage(BaseModel):
    """One message in the conversation."""

    model_config = ConfigDict(extra="forbid")

    message_id: str
    role: AssistantMessageRole
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    mode: Optional[AssistantMode] = None
    context_type: Optional[AssistantContextType] = None
    cached: bool = False  # True if answered locally without LLM
    model: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class AssistantChatRequest(BaseModel):
    """Request to send a message to the assistant."""

    model_config = ConfigDict(extra="forbid")

    message: str
    mode: AssistantMode = AssistantMode.EXPLAIN_CODE
    context: Optional[AssistantContext] = None
    conversation_id: Optional[str] = None
    refresh: bool = False


class AssistantChatResponse(BaseModel):
    """Response from the assistant."""

    model_config = ConfigDict(extra="forbid")

    message: AssistantMessage
    conversation_id: str
    cached: bool
    model: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class AssistantCodeActionRequest(BaseModel):
    """Request to perform a code action."""

    model_config = ConfigDict(extra="forbid")

    action_type: AssistantCodeActionType
    context: AssistantContext
    instruction: Optional[str] = None
    conversation_id: Optional[str] = None


class AssistantCodeActionResponse(BaseModel):
    """Response from a code action."""

    model_config = ConfigDict(extra="forbid")

    action_type: AssistantCodeActionType
    original_code: str
    generated_code: str
    explanation: str
    diff: str  # Unified diff format
    model: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class AssistantConversation(BaseModel):
    """A conversation with the assistant."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    owner: str
    repository: str
    messages: list[AssistantMessage] = Field(default_factory=list)
    context: Optional[AssistantContext] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AssistantConversationListResponse(BaseModel):
    """List of conversations for a repository."""

    model_config = ConfigDict(extra="forbid")

    items: list[AssistantConversation] = Field(default_factory=list)
    page: int = 1
    per_page: int = 20
    total: int = 0
    total_pages: int = 0


# ---------------------------------------------------------------------------
# Local Intelligence Models
# ---------------------------------------------------------------------------


class LocalAnswer(BaseModel):
    """A deterministic answer computed without LLM."""

    model_config = ConfigDict(extra="forbid")

    question: str
    answer: str
    context_type: AssistantContextType
    data_source: str  # e.g., "dashboard", "security", "architecture"
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# Configuration Constants
# ---------------------------------------------------------------------------

# Maximum context size (characters) to send to the model
MAX_CONTEXT_CHARS = 8000

# Maximum code snippet size
MAX_CODE_CHARS = 4000

# Maximum conversation history to include
MAX_CONVERSATION_HISTORY = 10

# Cache TTL for assistant responses (1 hour)
ASSISTANT_CACHE_TTL_SECONDS = 3600

# Maximum messages per conversation
MAX_MESSAGES_PER_CONVERSATION = 100
