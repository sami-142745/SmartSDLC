"""README analysis for the README Intelligence page.

Everything here is derived mechanically from the README text: no model inference
and no summarization. A repository with no README produces a fully populated
report with ``available=False`` and a human-readable ``reason`` so the UI can
explain the gap instead of rendering an empty page.

What is measured
----------------
* **Structure** — ATX (``#``) and setext (``===``/``---``) headings with their
  level and line number, plus a short preview of the prose that follows.
* **Navigation** — presence of a table of contents and of the conventional
  install/usage/license sections, matched case-insensitively on the heading text.
* **Media and code** — fenced code blocks with their declared language and line
  count, image and link counts, and badge images (Markdown or HTML ``img``).
* **Size** — byte length, line count and word count, with fenced code excluded
  from the word count so a long example block cannot inflate prose metrics.

Detection is intentionally conservative: a heading only matches a conventional
section when its own text matches, so a "Usage" mention buried in a paragraph
does not count as a usage section.
"""

from __future__ import annotations

import re

from app.schemas.repository_intelligence import ReadmeCodeSample, ReadmeIntelligence, ReadmeSection

MAX_SECTIONS = 200
MAX_RAW_CHARS = 200_000
SECTION_PREVIEW_CHARS = 160
_FENCE_RE = re.compile(r"^(?P<fence>```+|~~~+)\s*(?P<language>[A-Za-z0-9+#._-]*)\s*$")
_ATX_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.+?)\s*#*\s*$")
_BADGE_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*(?:badge|shields\.io|badgen)[^)]*\)", re.IGNORECASE)
_HTML_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_HTML_BADGE_HINTS = ("badge", "shields.io", "badgen", "travis", "coveralls")
_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\([^)]*\)")
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'._-]*")
_TOC_HEADING_RE = re.compile(r"table\s+of\s+contents|\bcontents\b|\bindex\b", re.IGNORECASE)
_INSTALL_RE = re.compile(r"\binstall(ation|ing)?\b|\bsetup\b|\bgetting\s+started\b", re.IGNORECASE)
_USAGE_RE = re.compile(r"\busage\b|\bhow\s+to\s+use\b|\bexample", re.IGNORECASE)
_LICENSE_RE = re.compile(r"\blicen[cs]e\b", re.IGNORECASE)


def _normalise_heading(text: str) -> str:
    """Strip inline markdown decoration from a heading for pattern matching."""
    cleaned = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    cleaned = re.sub(r"[`*_~]", "", cleaned)
    return cleaned.strip().strip("#").strip()


def _mask_code_fences(lines: list[str]) -> tuple[list[str | None], list[ReadmeCodeSample]]:
    """Blank out fenced code regions, keeping the surrounding lines indexable.

    Returns a list the same length as ``lines`` where every line inside a fenced
    block (and the fence delimiters themselves) is replaced by ``None``, plus
    one :class:`ReadmeCodeSample` per block.

    Masking rather than deleting is what lets heading line numbers, section
    previews and prose metrics all refer to the *original* document positions:
    previews can therefore quote a fenced command, while the word count still
    measures prose only.
    """
    masked: list[str | None] = []
    samples: list[ReadmeCodeSample] = []

    open_fence: str | None = None
    language: str | None = None
    count = 0

    for line in lines:
        fence = _FENCE_RE.match(line)
        if open_fence is None and fence:
            open_fence = fence.group("fence")[0] * 3
            language = fence.group("language") or None
            count = 0
            masked.append(None)
            continue
        if open_fence is not None:
            if line.strip().startswith(open_fence):
                samples.append(ReadmeCodeSample(language=language, lines=count))
                open_fence = None
                language = None
                count = 0
                masked.append(None)
                continue
            count += 1
            masked.append(None)
            continue
        masked.append(line)

    # An unterminated fence still contributed content; close it out honestly.
    if open_fence is not None:
        samples.append(ReadmeCodeSample(language=language, lines=count))

    return masked, samples


def _is_setext_underline(candidate: str) -> bool:
    """True for a ``===``/``---`` title underline (or a horizontal rule)."""
    return len(candidate) >= 2 and (
        set(candidate) <= {"="} or set(candidate) <= {"-"}
    )


def _iter_headings(masked: list[str | None]):
    """Yield ``(level, text, line_number)`` for ATX and setext headings.

    ``masked`` is the output of :func:`_mask_code_fences`, so code regions are
    ``None``. Because indices are preserved, the yielded ``line_number`` is the
    1-based line in the original document. Setext underlines require a
    non-masked line above them, so a ``===`` inside a code block is ignored.
    """
    for index, line in enumerate(masked, start=1):
        if line is None:
            continue
        atx = _ATX_RE.match(line)
        if atx:
            yield len(atx.group("hashes")), atx.group("text").strip(), index
            continue
        if index < 2:
            continue
        previous = masked[index - 2]
        if previous is None or not previous.strip():
            continue
        if set(line) <= {"="} and line.strip():
            yield 1, previous.strip(), index
            continue
        if set(line) <= {"-"} and line.strip():
            yield 2, previous.strip(), index


def build_readme_intelligence(
    content: str | None,
    *,
    owner: str = "",
    repository: str = "",
    path: str | None = "README.md",
    reason: str | None = None,
    cached: bool = False,
) -> ReadmeIntelligence:
    """Analyze README text into the README Intelligence report.

    ``content`` of ``None`` (or blank) means the repository has no README; the
    returned report has ``available=False`` and every metric at zero.
    """
    if content is None or not content.strip():
        return ReadmeIntelligence(
            owner=owner,
            repository=repository,
            path=path,
            available=False,
            reason=reason or "This repository has no README.",
            raw=None,
            cached=cached,
        )

    raw = content
    truncated = False
    if len(raw) > MAX_RAW_CHARS:
        raw = raw[:MAX_RAW_CHARS]
        truncated = True

    lines = raw.splitlines()
    masked, code_samples = _mask_code_fences(lines)

    sections: list[ReadmeSection] = []
    for order, (level, text, line_number) in enumerate(_iter_headings(masked)):
        if order >= MAX_SECTIONS:
            break
        preview_parts: list[str] = []
        budget = 0
        for follower in lines[line_number:]:
            candidate = follower.strip()
            if not candidate:
                if preview_parts:
                    break
                continue
            # Stop at the next section so a preview never bleeds into its
            # sibling. Fenced code belonging to *this* section is included,
            # because an install command is the most useful thing to preview.
            if _ATX_RE.match(candidate) or _is_setext_underline(candidate):
                break
            preview_parts.append(candidate)
            budget += len(candidate)
            if budget > SECTION_PREVIEW_CHARS:
                break
        preview = " ".join(preview_parts)
        if len(preview) > SECTION_PREVIEW_CHARS:
            preview = preview[: SECTION_PREVIEW_CHARS - 1].rstrip() + "…"
        sections.append(
            ReadmeSection(
                heading=text,
                level=level,
                line=line_number,
                preview=preview,
            )
        )

    heading_texts = [_normalise_heading(section.heading) for section in sections]
    has_toc = any(_TOC_HEADING_RE.search(text) for text in heading_texts)
    has_install = any(_INSTALL_RE.search(text) for text in heading_texts)
    has_usage = any(_USAGE_RE.search(text) for text in heading_texts)
    has_license = any(_LICENSE_RE.search(text) for text in heading_texts)

    badge_count = len(_BADGE_IMAGE_RE.findall(raw)) + len(
        [tag for tag in _HTML_IMG_RE.findall(raw) if any(hint in tag.lower() for hint in _HTML_BADGE_HINTS)]
    )

    prose = "\n".join(line for line in masked if line is not None)
    word_count = len(_WORD_RE.findall(prose))

    return ReadmeIntelligence(
        owner=owner,
        repository=repository,
        path=path,
        available=True,
        reason=(
            "README truncated for display." if truncated else None
        ),
        raw=raw,
        size_bytes=len(content.encode("utf-8")),
        line_count=len(lines),
        word_count=word_count,
        sections=sections,
        has_badges=badge_count > 0,
        badge_count=badge_count,
        has_toc=has_toc,
        has_install_section=has_install,
        has_usage_section=has_usage,
        has_license_section=has_license,
        code_blocks=len(code_samples),
        languages_used=sorted({sample.language for sample in code_samples if sample.language}),
        images=len(_MARKDOWN_IMAGE_RE.findall(raw)) + len(_HTML_IMG_RE.findall(raw)),
        links=len(_MARKDOWN_LINK_RE.findall(raw)),
        cached=cached,
    )
