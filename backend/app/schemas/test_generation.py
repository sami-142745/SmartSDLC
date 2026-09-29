"""Contracts for the Test Generation Engine.

The engine proposes tests for public code that the repository's own test suite
never references. It is deliberately split the same way the security engine is:
a deterministic pass decides *what* is untested and *whether* a proposed test is
allowed to exist, and a model is used only to write prose-shaped content — here,
the body of a test function — which is then re-parsed, screened and redacted
before it can be shown to anyone.

Nothing in this module describes a change to a repository. Generated tests are a
preview: a target list with candidate files, held in SmartSDLC. Writing them to
the repository is a separate, explicit action that this release does not perform,
so the contracts below have no field through which a write could be requested.

A target is a measured fact — "no test file references ``normalise_path``" — not
a claim that the code is defective. Absence of a reference is weaker evidence
than a failing test, and a symbol can legitimately be exercised indirectly; the
contracts carry the evidence so a reviewer can judge it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: Test frameworks whose idioms the generator can write. ``unknown`` is a real
#: answer, not a placeholder: a repository with no recognisable runner gets the
#: project's dominant convention guessed from its test file names, and if that is
#: still unknown, the deterministic scaffold is used and labelled as such.
TestFramework = Literal["pytest", "unittest", "jest", "vitest", "unknown"]

#: Languages the deterministic symbol finder parses structurally.
TestLanguage = Literal["python", "javascript", "typescript"]

#: Symbol kinds considered worth a test target.
SymbolKind = Literal["function", "method", "class"]

#: Why a symbol was selected. Each is an observation about test files, not about
#: the quality of the code.
TargetReason = Literal[
    "no_test_reference",
    "reference_outside_test_paths",
    "no_test_suite",
    "tested_only_by_name_match",
]

#: Where a file's content came from. ``deterministic`` content is generated
#: locally and contains no model output; it is a scaffold with no assertions.
GenerationSource = Literal["gemini", "deterministic"]

#: Validation findings for one generated file. Codes are stable because the
#: frontend switches on them.
ValidationCode = Literal[
    "syntax_error",
    "forbidden_import",
    "forbidden_call",
    "secret_redacted",
    "empty",
    "too_long",
    "too_many_tests",
    "placeholder",
    "no_test_detected",
]

#: Directory names that hold tests. Matched case-insensitively on any path
#: segment, because the conventions below are widespread and a repository using
#: ``spec/`` or ``__tests__/`` is following the same intent as ``tests/``.
TEST_DIRECTORIES = frozenset(
    {"test", "tests", "spec", "specs", "__tests__", "e2e", "it", "testing", "test_suite", "testsuites"}
)

#: File name stems that mark a test file, used when a repository keeps its tests
#: outside a conventionally named directory (``src/foo.spec.ts``).
TEST_FILE_STEMS = frozenset({"test", "tests", "spec"})

#: Default number of untested symbols to propose tests for.
DEFAULT_MAX_TARGETS = 20

#: Hard ceiling on returned targets, whatever the caller asks for. Generation
#: cost is per target, so an unbounded list is both slow and unreadable.
MAX_TARGETS = 60

#: Hard ceiling on generated files in one response.
MAX_GENERATED_FILES = 12

#: Hard ceiling on test functions in one generated file.
MAX_TESTS_PER_FILE = 12

#: Hard ceiling on the size of one generated file. A model asked for a small test
#: file that returns a megabyte has gone wrong, and a browser should not be asked
#: to render it.
MAX_CONTENT_CHARS = 20_000

#: Prompt source content is truncated to this many characters per target file.
#: Generation is a preview aid, not a substitute for reading the repository.
MAX_SOURCE_CHARS = 12_000

METHODOLOGY = (
    "No model is used to decide what to test. Public symbols are extracted from "
    "repository source with a structural parser (Python ast; export declarations "
    "for JavaScript and TypeScript), and every test file in the tree is tokenised "
    "to find which symbol names it references. A symbol with no reference in any "
    "test file becomes a target, and its priority is a fixed function of measured "
    "facts. A model is used only to write the body of a proposed test, and every "
    "proposed file is re-parsed, screened for imports and calls that would read "
    "or write outside the process, truncated and redacted before it is shown. "
    "Generated tests are a preview and are never written to the repository."
)


class UntestedSymbol(BaseModel):
    """A public symbol and the evidence that no test references it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    qualified_name: str
    kind: SymbolKind
    file: str
    line: int
    signature: str
    has_docstring: bool = False
    branch_score: int = 0
    referenced_in: list[str] = Field(default_factory=list, max_length=50)


class TestTarget(BaseModel):
    """One proposed test target, with its priority and evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    qualified_name: str
    kind: SymbolKind
    file: str
    line: int
    signature: str
    reason: TargetReason
    evidence: str
    priority: int = Field(ge=0, le=100)
    test_names: list[str] = Field(default_factory=list, max_length=8)


class ValidationIssue(BaseModel):
    """One finding from screening a generated file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ValidationCode
    detail: str
    line: int | None = None


class GeneratedTestFile(BaseModel):
    """One proposed test file, held for review. Never written anywhere."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    language: TestLanguage
    framework: TestFramework
    content: str
    source: GenerationSource
    model: str | None = None
    test_names: list[str] = Field(default_factory=list, max_length=MAX_TESTS_PER_FILE)
    covers: list[str] = Field(default_factory=list, max_length=20)
    usable: bool = True
    validation: list[ValidationIssue] = Field(default_factory=list, max_length=20)


class TestGenerationSummary(BaseModel):
    """Aggregate counts for one generation run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    framework: TestFramework = "unknown"
    source_files_scanned: int = 0
    public_symbols: int = 0
    existing_test_files: int = 0
    untested_symbols: int = 0
    targets: int = 0
    generated_files: int = 0
    generated_tests: int = 0
    rejected_files: int = 0
    methodology: str = METHODOLOGY


class TestGeneration(BaseModel):
    """A preview of proposed tests for one repository at one ref."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repository_id: str
    owner: str
    repository: str
    full_name: str
    provider: str
    ref: str | None = None
    commit_sha: str | None = None
    generated_at: str
    duration_ms: int = 0
    framework: TestFramework = "unknown"
    test_directories: list[str] = Field(default_factory=list, max_length=20)
    existing_test_files: list[str] = Field(default_factory=list, max_length=500)
    targets: list[TestTarget] = Field(default_factory=list, max_length=MAX_TARGETS)
    files: list[GeneratedTestFile] = Field(default_factory=list, max_length=MAX_GENERATED_FILES)
    summary: TestGenerationSummary = Field(default_factory=TestGenerationSummary)
    model: str | None = None
    unavailable_reason: str | None = None
    errors: list[str] = Field(default_factory=list, max_length=20)
    truncated: bool = False
