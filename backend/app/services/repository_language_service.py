"""Language breakdown for a repository.

Source of truth is the provider's language byte census (``/repos/{o}/{r}/languages``),
which is a measured property of the default branch rather than something
inferred. Percentages are exact shares of the total detected bytes, rounded to
one decimal place for display; the underlying byte counts are returned
unrounded so totals always reconcile.

``OTHER_LABEL`` absorbs every language beyond ``DEFAULT_TOP_LANGUAGES`` so the
chart stays legible while ``other_bytes`` preserves the true remainder. When the
provider reports more than one language, the result is marked ``truncated`` so
the UI can say so instead of implying the list is complete.
"""

from __future__ import annotations

from app.schemas.repository_intelligence import LanguageBreakdown, LanguageSlice

DEFAULT_TOP_LANGUAGES = 8
OTHER_LABEL = "Other"


def _round_percent(value: float) -> float:
    return round(value, 1)


def build_language_breakdown(
    languages: dict[str, int] | None,
    *,
    owner: str = "",
    repository: str = "",
    top_n: int = DEFAULT_TOP_LANGUAGES,
    cached: bool = False,
) -> LanguageBreakdown:
    """Convert provider byte counts into an ordered breakdown.

    Languages are ordered by bytes descending, ties broken alphabetically so the
    ordering is stable across requests. Languages beyond ``top_n`` are folded
    into a single ``Other`` slice.
    """
    if not languages:
        return LanguageBreakdown(
            owner=owner,
            repository=repository,
            total_bytes=0,
            languages=[],
            other_bytes=0,
            truncated=False,
            cached=cached,
        )

    positive = {
        name: int(count)
        for name, count in languages.items()
        if isinstance(count, (int, float)) and count > 0
    }
    if not positive:
        return LanguageBreakdown(
            owner=owner,
            repository=repository,
            total_bytes=0,
            languages=[],
            other_bytes=0,
            truncated=False,
            cached=cached,
        )

    total = sum(positive.values())
    ordered = sorted(positive.items(), key=lambda item: (-item[1], item[0]))

    limit = max(1, int(top_n))
    head = ordered[:limit]
    tail = ordered[limit:]

    slices = [
        LanguageSlice(
            name=name,
            bytes=count,
            percent=_round_percent(count / total * 100.0),
        )
        for name, count in head
    ]
    other_bytes = sum(count for _, count in tail)
    if other_bytes > 0:
        slices.append(
            LanguageSlice(
                name=OTHER_LABEL,
                bytes=other_bytes,
                percent=_round_percent(other_bytes / total * 100.0),
            )
        )

    return LanguageBreakdown(
        owner=owner,
        repository=repository,
        total_bytes=total,
        languages=slices,
        other_bytes=other_bytes,
        truncated=bool(tail),
        cached=cached,
    )
