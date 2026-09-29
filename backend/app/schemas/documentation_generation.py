"""Contracts for the AI Documentation Generation system.

Scope
-----
This module defines the contracts for generating repository documentation from
deterministic SmartSDLC analysis. It is separate from the existing
PR-scoped documentation in :mod:`app.schemas.documentation_intelligence` and
:mod:`app.services.documentation_service`.

Design principles
-----------------
1. **Bounded context** - Only facts from deterministic analyses are supplied to the
   model. The model never receives raw repository content beyond small, curated
   excerpts.
2. **Structured output** - The model produces structured sections, not a single
   Markdown blob, so the UI can offer section-level regeneration.
3. **Deterministic integration** - Architecture, supply chain, security and
   repository intelligence are fused into a single context object. The model
   must not be asked to re-derive what SmartSDLC already computes.
4. **Section granularity** - Documents are composed of sections so individual
   sections can be regenerated without touching the rest.
5. **Honesty** - When evidence is unavailable the generated text states that
   explicitly rather than inventing.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class DocumentType(str, Enum):
    """Supported documentation types."""

    README = "README"
    API_DOCUMENTATION = "API_DOCUMENTATION"
    ARCHITECTURE = "ARCHITECTURE"
    SETUP_GUIDE = "SETUP_GUIDE"
    DEVELOPMENT_GUIDE = "DEVELOPMENT_GUIDE"
    CONTRIBUTING_GUIDE = "CONTRIBUTING_GUIDE"
    SECURITY_GUIDE = "SECURITY_GUIDE"


DOCUMENT_TYPES = tuple(DocumentType)

# Human-readable labels for UI
DOCUMENT_TYPE_LABELS: dict[DocumentType, str] = {
    DocumentType.README: "README",
    DocumentType.API_DOCUMENTATION: "API Documentation",
    DocumentType.ARCHITECTURE: "Architecture",
    DocumentType.SETUP_GUIDE: "Setup Guide",
    DocumentType.DEVELOPMENT_GUIDE: "Development Guide",
    DocumentType.CONTRIBUTING_GUIDE: "Contributing Guide",
    DocumentType.SECURITY_GUIDE: "Security Guide",
}

# Default section names for each document type. These are the sections the
# model is asked to produce. The UI uses the same list for navigation and
# section-level regeneration.
DOCUMENT_TYPE_SECTIONS: dict[DocumentType, tuple[str, ...]] = {
    DocumentType.README: (
        "overview",
        "features",
        "architecture",
        "tech_stack",
        "repository_structure",
        "installation",
        "configuration",
        "running_locally",
        "testing",
        "deployment",
        "contributing",
    ),
    DocumentType.API_DOCUMENTATION: (
        "overview",
        "authentication",
        "endpoints",
        "error_handling",
        "rate_limits",
        "versioning",
    ),
    DocumentType.ARCHITECTURE: (
        "overview",
        "modules",
        "layers",
        "dependencies",
        "structural_issues",
        "hotspots",
        "design_decisions",
    ),
    DocumentType.SETUP_GUIDE: (
        "prerequisites",
        "installation",
        "configuration",
        "environment_variables",
        "running_locally",
        "docker",
        "troubleshooting",
    ),
    DocumentType.DEVELOPMENT_GUIDE: (
        "project_structure",
        "development_commands",
        "testing",
        "building",
        "linting",
        "debugging",
        "contribution_workflow",
    ),
    DocumentType.CONTRIBUTING_GUIDE: (
        "getting_started",
        "code_style",
        "commit_conventions",
        "pull_request_process",
        "testing_requirements",
        "review_guidelines",
    ),
    DocumentType.SECURITY_GUIDE: (
        "threat_model",
        "authentication",
        "authorization",
        "data_protection",
        "secure_development",
        "incident_response",
        "known_findings",
    ),
}


class DocumentStatus(str, Enum):
    """Lifecycle status of a generated document."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETE = "complete"
    FAILED = "failed"


class SectionStatus(str, Enum):
    """Lifecycle status of a document section."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETE = "complete"
    FAILED = "failed"
    STALE = "stale"  # Document was regenerated but this section was not


class GenerationMode(str, Enum):
    """How a document or section was produced."""

    FULL = "full"  # Full document generation
    SECTION = "section"  # Single section regeneration
    IMPROVE = "improve"  # Section improvement with feedback


# ---------------------------------------------------------------------------
# Core Models
# ---------------------------------------------------------------------------

class DocumentationSection(BaseModel):
    """One section within a generated document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    markdown: str = Field(default="", max_length=50000)
    status: SectionStatus = SectionStatus.PENDING
    warnings: list[str] = Field(default_factory=list)
    generated_at: Optional[datetime] = None
    model: Optional[str] = None
    generation_mode: GenerationMode = GenerationMode.FULL


class DocumentationDocument(BaseModel):
    """A complete generated document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str = Field(min_length=1, max_length=100)
    repository_id: str = Field(min_length=1, max_length=100)
    document_type: DocumentType
    title: str = Field(min_length=1, max_length=300)
    sections: tuple[DocumentationSection, ...] = Field(default_factory=tuple)
    status: DocumentStatus = DocumentStatus.PENDING
    generated_at: Optional[datetime] = None
    model: Optional[str] = None
    version: int = 1
    warnings: list[str] = Field(default_factory=list)
    source_context: Optional["DocumentationContext"] = None
    cached: bool = False

    @property
    def full_markdown(self) -> str:
        """Concatenate all sections into a single Markdown document."""
        parts = [f"# {self.title}\n"]
        for section in self.sections:
            if section.markdown.strip():
                parts.append(f"## {section.title}\n\n{section.markdown}\n")
        return "\n".join(parts)


class DocumentationContext(BaseModel):
    """Bounded context supplied to the model for documentation generation.

    This is assembled from deterministic SmartSDLC analyses. It contains no
    raw repository files beyond small, curated excerpts.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Repository identity
    owner: str
    repository: str
    repository_id: str
    description: Optional[str] = None
    default_branch: Optional[str] = None
    languages: tuple[str, ...] = Field(default_factory=tuple)
    stars: int = 0
    forks: int = 0

    # Repository structure
    important_directories: tuple[str, ...] = Field(default_factory=tuple)
    important_files: tuple[str, ...] = Field(default_factory=tuple)
    entry_points: tuple[str, ...] = Field(default_factory=tuple)

    # Architecture intelligence (Phase 6)
    architecture_summary: Optional[dict[str, Any]] = None
    architecture_modules: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    architecture_layers: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    architecture_issues: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    architecture_hotspots: tuple[dict[str, Any], ...] = Field(default_factory=tuple)

    # Supply chain intelligence (Phase 5)
    supply_chain_summary: Optional[dict[str, Any]] = None
    supply_chain_manifests: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    supply_chain_dependencies: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    supply_chain_licenses: tuple[dict[str, Any], ...] = Field(default_factory=tuple)

    # Security intelligence (Phase 3)
    security_summary: Optional[dict[str, Any]] = None
    security_findings: tuple[dict[str, Any], ...] = Field(default_factory=tuple)

    # Existing documentation
    readme_content: Optional[str] = None
    documentation_files: tuple[dict[str, Any], ...] = Field(default_factory=tuple)

    # Source excerpts (small, curated)
    source_excerpts: tuple[dict[str, str], ...] = Field(default_factory=tuple)

    # Methodology statement for transparency
    methodology: str = (
        "This documentation was generated from deterministic SmartSDLC analyses: "
        "Architecture Intelligence (module detection, dependency graph, layer inference), "
        "Supply Chain Intelligence (manifest parsing, license classification, pinning analysis), "
        "Security Intelligence (vulnerability scanning, secret detection), and "
        "Repository Intelligence (language detection, README parsing). "
        "The AI model received only this structured context and small, curated source excerpts. "
        "No raw repository content was sent to the model. When evidence was unavailable, "
        "the model was instructed to state that explicitly."
    )


class DocumentationGenerationRequest(BaseModel):
    """Request to generate or regenerate documentation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_type: DocumentType
    mode: GenerationMode = GenerationMode.FULL
    section_name: Optional[str] = None  # Required when mode=SECTION or IMPROVE
    feedback: Optional[str] = None  # For mode=IMPROVE
    refresh: bool = False  # Bypass cache
    max_source_excerpts: int = 5
    max_excerpt_chars: int = 2000


class DocumentationGenerationResponse(BaseModel):
    """Response from a generation request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document: DocumentationDocument
    generation_time_ms: int
    cached: bool
    warnings: list[str] = Field(default_factory=list)


class DocumentationListResponse(BaseModel):
    """List of generated documents for a repository."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repository_id: str
    documents: tuple[DocumentationDocument, ...] = Field(default_factory=tuple)
    total: int = 0


# ---------------------------------------------------------------------------
# Section regeneration request/response
# ---------------------------------------------------------------------------

class SectionRegenerationRequest(BaseModel):
    """Request to regenerate a single section."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_type: DocumentType
    section_name: str
    mode: GenerationMode = GenerationMode.SECTION
    feedback: Optional[str] = None
    refresh: bool = False
    max_source_excerpts: int = 3
    max_excerpt_chars: int = 1500


class SectionRegenerationResponse(BaseModel):
    """Response from section regeneration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section: DocumentationSection
    document: DocumentationDocument  # Updated document with regenerated section
    generation_time_ms: int
    cached: bool
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Markdown validation
# ---------------------------------------------------------------------------

class MarkdownValidationResult(BaseModel):
    """Result of Markdown validation/normalization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    is_valid: bool
    normalized_markdown: str
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

# Context limits to stay within model context windows
MAX_CONTEXT_MODULES = 30
MAX_CONTEXT_DEPENDENCIES = 25
MAX_CONTEXT_ISSUES = 15
MAX_CONTEXT_SOURCE_EXCERPTS = 8
MAX_EXCERPT_CHARS = 2500

# Output limits
MAX_SECTION_MARKDOWN_CHARS = 50000
MAX_DOCUMENT_MARKDOWN_CHARS = 200000

# Cache TTL (6 hours - documentation changes less frequently than analyses)
DOCUMENTATION_CACHE_TTL_SECONDS = 21600