"""Test Generation orchestration.

Separates the deterministic target discovery in
:mod:`app.services.test_target_parser` and the model call in
:mod:`app.services.test_generator` from the outside world. It owns:

1. **Target selection.** Source and test files are chosen from the provider tree
   by path, before any download, so a large repository costs a bounded number of
   requests. Test files are read because they define what "referenced" means;
   source files are read because they define what could be untested.
2. **Bounded concurrency and partial failure.** Reads run under a semaphore; a
   file that cannot be read is recorded and skipped rather than failing the run.
   Model calls run under a smaller semaphore, because a rate limit costs the whole
   run while a missing file costs one symbol.
3. **Caching.** Results live in the shared ``repository_analysis`` collection
   under the ``test_generation`` analysis kind, so no new persistence layer is
   introduced.

It never mutates provider state. There is no code path here that writes a file to
a repository, and the SCM clients expose no write method, so a generated suite
cannot leave SmartSDLC except as something a person copies out of the page.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable

from app.schemas.test_generation import (
    DEFAULT_MAX_TARGETS,
    MAX_GENERATED_FILES,
    MAX_TARGETS,
    MAX_TESTS_PER_FILE,
    TestGeneration,
    TestGenerationSummary,
    TestTarget,
)
from app.services import repository_analysis_repository, security_repository, test_target_parser
from app.services.repository_paths import normalise_path
from app.services.scm import ScmAPIError, ScmProvider, get_scm_client
from app.services.test_generator import generate_test_file
from app.services.test_target_parser import RepositoryFile, find_test_targets

logger = logging.getLogger(__name__)

#: Concurrent file reads, matching the other engines so a user running several
#: analyses stays inside provider rate limits.
MAX_CONCURRENT_FETCHES = 8

#: Concurrent model calls. Deliberately lower than the read limit: a provider
#: rate limit on file reads degrades one analysis, a model rate limit fails every
#: generation at once and costs money to retry.
MAX_CONCURRENT_GENERATIONS = 3

#: Source files read to look for untested public symbols.
DEFAULT_MAX_SOURCE_FILES = 200

#: Test files read. Every test file matters to the "is this referenced" question,
#: so a repository whose tests live outside a conventional directory still gets a
#: correct answer; this cap only bounds pathological trees.
DEFAULT_MAX_TEST_FILES = 300

#: Hard ceiling on either category, so a client cannot ask the server to read an
#: entire monorepo.
HARD_MAX_FILES = 2000

MAX_ERRORS_REPORTED = 20

CACHE_KIND = "test_generation"

#: Path prefixes whose source files are most representative of the project.
_SOURCE_PRIORITY_PREFIXES = (
    "src/",
    "app/",
    "backend/",
    "frontend/",
    "lib/",
    "core/",
    "server/",
    "packages/",
    "internal/",
)

#: Test directory to place generated files in, in preference order, when the
#: repository already has one. Never invented: a generated file that lands in a
#: directory the project's runner does not collect is worse than no file.
_TEST_ROOT_PREFERENCE = ("tests", "test", "spec", "__tests__", "src")


class TestGenerationError(Exception):
    """Raised when generation cannot start at all."""

    # Stops pytest trying to collect this exception as a test class, which
    # otherwise emits a collection warning from every module importing it.
    __test__ = False


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client(provider: ScmProvider, token: str):
    return get_scm_client(provider.value, token)


def _supports(client: Any, method: str) -> bool:
    return callable(getattr(client, method, None))


def _tree_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        tree = payload.get("tree")
        if isinstance(tree, list):
            return [item for item in tree if isinstance(item, dict)]
    return []


def _commit_sha(payload: Any) -> str | None:
    if isinstance(payload, dict):
        sha = payload.get("sha")
        if isinstance(sha, str) and sha:
            return sha
    return None


def _source_priority(path: str) -> tuple[int, str]:
    priority = 0 if path.startswith(_SOURCE_PRIORITY_PREFIXES) else 1
    return (priority, path)


def select_files(
    tree_entries: Iterable[dict[str, Any]],
    *,
    max_source_files: int = DEFAULT_MAX_SOURCE_FILES,
    max_test_files: int = DEFAULT_MAX_TEST_FILES,
) -> tuple[list[str], list[str], int, int, bool]:
    """Choose which files to read.

    Returns ``(source_paths, test_paths, source_count, test_count,
    truncated)``. Selection is deterministic: candidates are ordered by a fixed
    priority then by path, so two runs over one tree read the same files.
    """
    source_candidates: list[str] = []
    test_candidates: list[str] = []

    for entry in tree_entries or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") not in (None, "blob"):
            continue
        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            continue
        path = normalise_path(raw_path)
        if not path:
            continue
        if test_target_parser.is_test_path(path):
            test_candidates.append(path)
        elif test_target_parser.is_source_path(path):
            source_candidates.append(path)

    source_limit = max(1, min(int(max_source_files or DEFAULT_MAX_SOURCE_FILES), HARD_MAX_FILES))
    test_limit = max(1, min(int(max_test_files or DEFAULT_MAX_TEST_FILES), HARD_MAX_FILES))

    truncated = len(source_candidates) > source_limit or len(test_candidates) > test_limit

    return (
        sorted(source_candidates, key=_source_priority)[:source_limit],
        sorted(test_candidates)[:test_limit],
        len(source_candidates),
        len(test_candidates),
        truncated,
    )


def _test_root(test_directories: Iterable[str]) -> str:
    """Where a generated file should go, based on where the tests already are.

    Returns an empty string when the repository has no recognisable test
    directory, which means the file is placed next to its source instead of in a
    directory the runner would never collect.
    """
    seen = {name.lower() for name in test_directories}
    for candidate in _TEST_ROOT_PREFERENCE:
        if candidate in seen:
            return candidate
    return ""


def proposed_test_path(
    source_path: str,
    *,
    test_directories: Iterable[str] = (),
    ambiguous: bool = False,
    existing_paths: Iterable[str] = (),
) -> str:
    """Deterministic path for the test file covering ``source_path``.

    Two ways a proposal could be wrong, both handled here rather than by the
    caller:

    * **It would overwrite a real test file.** ``app/other/util.py`` proposes
      ``tests/test_util.py``, which may already exist. A preview that claims a
      path the repository already uses is worse than no preview, so a taken path
      is moved to the directory-qualified form.
    * **Two sources propose the same path.** ``a/utils.py`` and ``b/utils.py``
      both want ``tests/test_utils.py``. The directory-qualified form separates
      them, and a numeric suffix separates what that cannot.

    The result is stable for one repository: the same tree always produces the
    same paths, so two previews can be compared.
    """
    clean = normalise_path(source_path)
    directory, _, name = clean.rpartition("/")
    stem, dot, extension = name.rpartition(".")
    if not dot:
        stem, extension = name, ""
    stem = stem or name
    root = _test_root(test_directories)
    taken = set(existing_paths or ())

    if extension == "py":
        # ``test_helpers.py`` is already a test file's name; the prefix is
        # removed so the proposal is ``test_helpers.py`` and not
        # ``test_test_helpers.py``.
        base = stem.removeprefix("test_") or stem
        filename = f"test_{base}.py"
    else:
        filename = f"{stem}.test.{extension}" if extension else f"{stem}.test.js"

    flat = f"{root}/{filename}" if root else normalise_path(f"{directory}/{filename}")

    def qualified() -> str:
        # Mirror the source directory, so unique stems stay flat and colliding
        # ones stay distinct. ``src``/``app``/``lib`` are dropped as noise.
        parts = [part for part in directory.split("/") if part not in ("src", "app", "lib")]
        if root:
            return normalise_path("/".join([root, *parts, filename]))
        return normalise_path("/".join([*parts, filename])) if parts else flat

    if not ambiguous and flat not in taken:
        return flat

    candidate = qualified()
    if candidate == flat:
        # No directory information to qualify with; fall back to a suffix.
        candidate = flat
    suffix = 2
    while candidate in taken:
        head, dot2, ext = candidate.rpartition(".")
        candidate = f"{head}_{suffix}.{ext}" if dot2 else f"{candidate}_{suffix}"
        suffix += 1
    return candidate


def _group_targets(targets: Iterable[TestTarget]) -> dict[str, list[TestTarget]]:
    """Group targets by the file they belong to, preserving priority order."""
    grouped: dict[str, list[TestTarget]] = {}
    for target in targets:
        grouped.setdefault(target.file, []).append(target)
    return grouped


def _ambiguous_stems(targets: Iterable[TestTarget]) -> set[str]:
    """Source files whose stem appears more than once among the targets.

    Measured only over the targets, not the whole tree: a collision with a file
    that generated no target cannot overwrite anything.
    """
    counts = Counter(
        target.file.rsplit("/", 1)[-1].rsplit(".", 1)[0] for target in targets
    )
    return {target.file for target in targets if counts[target.file.rsplit("/", 1)[-1].rsplit(".", 1)[0]] > 1}


async def _fetch(
    client: Any, owner: str, repository: str, path: str, ref: str | None
) -> tuple[str, str | None, str | None]:
    try:
        content = await client.get_file_content(owner, repository, path, ref=ref)
    except ScmAPIError as error:
        if error.category == "not_found":
            return path, None, None
        return path, None, f"{path}: {error.category}"
    except Exception as exc:  # noqa: BLE001 - one bad file must not fail a run
        return path, None, f"{path}: {type(exc).__name__}"
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8")
        except UnicodeDecodeError:
            return path, None, f"{path}: not valid UTF-8"
    if not isinstance(content, str):
        return path, None, f"{path}: unreadable content"
    return path, content, None


async def generate_tests_for_repository(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repository: str,
    *,
    ref: str | None = None,
    max_files: int | None = None,
    max_targets: int = DEFAULT_MAX_TARGETS,
    refresh: bool = False,
    use_cache: bool = True,
) -> TestGeneration:
    """Find untested public symbols and propose tests for the highest ranked.

    ``max_targets`` is clamped to the schema ceiling: each target can cost a
    model call, so an unbounded request is neither fast nor reviewable.
    """
    if use_cache and not refresh:
        cached = await _read_cache(user_id, owner, repository)
        if cached is not None:
            try:
                return TestGeneration.model_validate(cached)
            except Exception:
                logger.warning("Discarding an unreadable cached test generation", exc_info=True)

    client = _client(provider, token)
    if not _supports(client, "get_repository_tree"):
        raise TestGenerationError("This provider does not expose a repository tree.")
    if not _supports(client, "get_file_content"):
        raise TestGenerationError("This provider does not expose repository file content.")

    started = time.perf_counter()
    try:
        tree_payload = await client.get_repository_tree(owner, repository, ref=ref)
    except ScmAPIError as error:
        raise TestGenerationError(f"Could not read the repository tree: {error.category}") from error
    except Exception as exc:  # noqa: BLE001
        raise TestGenerationError("Could not read the repository tree.") from exc

    entries = _tree_entries(tree_payload)
    if not entries:
        raise TestGenerationError("The repository tree is empty or unreadable.")

    limit = max_files if max_files is not None else DEFAULT_MAX_SOURCE_FILES
    source_paths, test_paths, source_count, test_count, truncated = select_files(
        entries,
        max_source_files=limit,
        max_test_files=limit,
    )

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def guarded(path: str) -> tuple[str, str | None, str | None]:
        async with semaphore:
            return await _fetch(client, owner, repository, path, ref)

    source_results, test_results = await asyncio.gather(
        asyncio.gather(*(guarded(path) for path in source_paths)),
        asyncio.gather(*(guarded(path) for path in test_paths)),
    )

    errors: list[str] = []
    materials: list[RepositoryFile] = []
    source_content: dict[str, str] = {}

    for path, content, error in source_results:
        if error:
            if len(errors) < MAX_ERRORS_REPORTED:
                errors.append(error)
            continue
        if content is None:
            continue
        materials.append(RepositoryFile(path=path, content=content))
        source_content[path] = content

    for path, content, error in test_results:
        if error:
            if len(errors) < MAX_ERRORS_REPORTED:
                errors.append(error)
            continue
        if content is None:
            continue
        materials.append(RepositoryFile(path=path, content=content))

    limit_targets = max(1, min(int(max_targets), MAX_TARGETS)) if max_targets else 1
    selection = find_test_targets(materials, max_targets=limit_targets)
    errors.extend(selection.errors[: max(0, MAX_ERRORS_REPORTED - len(errors))])
    errors = errors[:MAX_ERRORS_REPORTED]

    targets = list(selection.targets)
    truncated = truncated or selection.truncated

    generated_files = []
    unavailable_reason: str | None = None
    generation_semaphore = asyncio.Semaphore(MAX_CONCURRENT_GENERATIONS)
    ambiguous = _ambiguous_stems(targets)
    grouped = _group_targets(targets)
    # Paths already occupied by the repository's own tests: a proposal that
    # collides with a real file would misrepresent itself in the preview.
    used_paths: set[str] = set(selection.test_files)

    # Paths are assigned before any coroutine starts, so the proposal for a given
    # source file is the same on every run regardless of completion order.
    # Ranked by the best priority the parser assigned, so the most valuable
    # untested behaviour is what survives the cap -- not whichever file happens
    # to declare the most symbols.
    ordered = sorted(
        grouped.items(),
        key=lambda item: (-max(target.priority for target in item[1]), item[0]),
    )
    if len(ordered) > MAX_GENERATED_FILES:
        # Cut before generating. Truncating afterwards would still pay for a
        # model call per discarded file and then throw the answer away.
        ordered = ordered[:MAX_GENERATED_FILES]
        truncated = True

    plan: list[tuple[str, str, list[TestTarget]]] = []
    for file_path, file_targets in ordered:
        target_path = proposed_test_path(
            file_path,
            test_directories=selection.test_directories,
            ambiguous=file_path in ambiguous,
            existing_paths=used_paths,
        )
        used_paths.add(target_path)
        plan.append((target_path, file_path, file_targets))

    async def generate_one(target_path: str, file_path: str, file_targets: list[TestTarget]):
        language = test_target_parser.language_for_path(file_path) or "python"
        async with generation_semaphore:
            return await generate_test_file(
                path=target_path,
                language=language,
                framework=selection.framework,
                targets=file_targets[:MAX_TESTS_PER_FILE],
                source=source_content.get(file_path, ""),
            )

    if plan:
        results = await asyncio.gather(
            *(generate_one(target_path, file_path, file_targets) for target_path, file_path, file_targets in plan)
        )
        for outcome in results:
            generated_files.append(outcome.file)
            if outcome.unavailable_reason and not unavailable_reason:
                unavailable_reason = outcome.unavailable_reason

    generated_files.sort(key=lambda item: item.path)
    generated_files = generated_files[:MAX_GENERATED_FILES]

    model_used = any(item.source == "gemini" for item in generated_files)
    rejected = sum(1 for item in generated_files if not item.usable)

    report = TestGeneration(
        repository_id=security_repository.repository_id_for(owner, repository),
        owner=owner,
        repository=repository,
        full_name=f"{owner}/{repository}",
        provider=provider.value,
        ref=ref,
        commit_sha=_commit_sha(tree_payload),
        generated_at=_utcnow_iso(),
        duration_ms=int((time.perf_counter() - started) * 1000),
        framework=selection.framework,
        test_directories=list(selection.test_directories),
        existing_test_files=list(selection.test_files),
        targets=targets,
        files=generated_files,
        summary=TestGenerationSummary(
            framework=selection.framework,
            source_files_scanned=source_count,
            public_symbols=selection.public_symbols,
            existing_test_files=test_count,
            untested_symbols=selection.untested_symbols,
            targets=len(targets),
            generated_files=len(generated_files),
            generated_tests=sum(len(item.test_names) for item in generated_files),
            rejected_files=rejected,
        ),
        model=generated_files[0].model if model_used and generated_files else None,
        unavailable_reason=unavailable_reason,
        errors=errors,
        truncated=truncated,
    )

    await _write_cache(user_id, owner, repository, report)
    logger.info(
        "Test generation for %s/%s: %d/%d public symbols unreferenced, %d files proposed (%s)",
        owner,
        repository,
        selection.untested_symbols,
        selection.public_symbols,
        len(generated_files),
        "model" if model_used else "scaffold",
    )
    return report


async def _read_cache(user_id: int, owner: str, repository: str) -> dict[str, Any] | None:
    try:
        entry = await repository_analysis_repository.get_cached(
            user_id, owner, repository, CACHE_KIND
        )
    except Exception:
        logger.warning("Test generation cache read failed", exc_info=True)
        return None
    if not entry:
        return None
    payload = entry.get("payload")
    return payload if isinstance(payload, dict) else None


async def _write_cache(
    user_id: int, owner: str, repository: str, report: TestGeneration
) -> None:
    try:
        await repository_analysis_repository.set_cached(
            user_id, owner, repository, CACHE_KIND, report.model_dump(mode="json")
        )
    except Exception:
        logger.warning("Test generation cache write failed", exc_info=True)


async def get_test_generation(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repository: str,
    *,
    ref: str | None = None,
    max_files: int | None = None,
    max_targets: int = DEFAULT_MAX_TARGETS,
    refresh: bool = False,
) -> TestGeneration:
    """Public entry point used by the router."""
    return await generate_tests_for_repository(
        user_id,
        token,
        provider,
        owner,
        repository,
        ref=ref,
        max_files=max_files,
        max_targets=max_targets,
        refresh=refresh,
    )


async def invalidate(user_id: int, owner: str, repository: str) -> int:
    return await repository_analysis_repository.invalidate(user_id, owner, repository)


async def validate_generated_test(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repository: str,
    *,
    file_path: str,
    language: str,
    framework: str,
    targets: list[TestTarget],
    source: str,
    refresh: bool = False,
) -> tuple[GeneratedTestFile, str | None]:
    """Validate a generated test file without caching the result.

    Used for ad-hoc validation of user-modified generated tests.
    """
    client = _client(provider, token)
    if not _supports(client, "get_file_content"):
        raise TestGenerationError("This provider does not expose repository file content.")

    # Re-validate using the existing validation logic
    from app.services.test_generator import (
        render_python_file,
        render_js_file,
        validate_content,
        deterministic_scaffold,
        target_import_lines,
    )

    # Build the test file content for validation
    if language == "python":
        content = render_python_file(
            framework=framework,
            targets=targets,
            cases=[],
            placeholder=False,
            test_path=file_path,
        )
    else:
        content = render_js_file(
            framework=framework,
            targets=targets,
            cases=[],
            placeholder=False,
            test_path=file_path,
        )

    # The actual content should be provided by the caller for validation
    # This is a simplified validation - the real validation happens in generate_test_file
    # For now, return a validation result based on the provided content
    screened, issues, usable = validate_content(
        content=source,  # Use the provided source content for validation
        language=language,
        source="gemini" if source else "deterministic",
    )

    validated_file = GeneratedTestFile(
        path=file_path,
        language=language,
        framework=framework,
        content=screened,
        source="gemini" if source else "deterministic",
        model=None,
        test_names=[],
        covers=[t.qualified_name for t in targets],
        usable=usable,
        validation=issues,
    )

    return validated_file, None


async def regenerate_single_test_file(
    user_id: int,
    token: str,
    provider: ScmProvider,
    owner: str,
    repository: str,
    *,
    file_path: str,
    language: str,
    framework: str,
    targets: list[TestTarget],
    source_content: str,
    refresh: bool = False,
) -> GeneratedTestFile:
    """Regenerate a single test file for the given targets.

    Used when a user wants to regenerate one specific file from the proposal.
    """
    from app.services.test_generator import generate_test_file

    result = await generate_test_file(
        path=file_path,
        language=language,
        framework=framework,
        targets=targets,
        source=source_content,
    )

    if result.unavailable_reason:
        # Return the scaffold as a fallback
        return result.file

    return result.file
