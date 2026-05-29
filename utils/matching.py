"""
utils/matching.py  —  AniGUI Title Matching Utilities

Provides local fuzzy title-matching on top of API search results.
Used to pick the best result from AllAnime or AniList rather than
blindly taking results[0], which can return the wrong anime when
titles differ between services.

Only uses the Python standard library (difflib) — no extra deps.
"""

from __future__ import annotations

from difflib import SequenceMatcher


# Minimum similarity ratio to consider a match valid.
# 0.0 = accept anything, 1.0 = exact match only.
# 0.6 works well in practice — catches reasonable fuzzy matches
# while rejecting completely unrelated titles.
MATCH_THRESHOLD = 0.6


def title_similarity(a: str, b: str) -> float:
    """Return a similarity ratio between 0.0 and 1.0 for two title strings.

    Comparison is case-insensitive and strips leading/trailing whitespace.
    Uses difflib.SequenceMatcher which handles partial matches, transposed
    words, and minor typos reasonably well.

    Examples
    --------
    >>> title_similarity("Attack on Titan", "Shingeki no Kyojin")
    0.23...   # low — very different strings
    >>> title_similarity("Sword Art Online", "Sword Art Online II")
    0.85...   # high — one is a substring of the other
    >>> title_similarity("Naruto", "Naruto")
    1.0
    """
    a = a.lower().strip()
    b = b.lower().strip()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def best_allanime_match(query: str, results: list[dict]) -> dict | None:
    """Pick the best AllAnime result for *query* using local fuzzy matching.

    Each AllAnime result dict is expected to have at least:
        "name"         — romaji / primary title
        "english_name" — English title (may be the same as name)

    Returns the highest-scoring result if its score meets MATCH_THRESHOLD,
    otherwise returns None to signal no confident match was found.

    Parameters
    ----------
    query:
        The title string used to search AllAnime (e.g. the AniList romaji
        title when resolving a streaming ID for a default-grid card).
    results:
        Raw list of dicts returned by allanime.search_anime().
    """
    if not results:
        return None

    scored: list[tuple[float, dict]] = []

    for r in results:
        candidates = [
            r.get("name") or "",
            r.get("english_name") or "",
        ]
        # Score against every non-empty title variant, keep the best
        best_score = max(
            (title_similarity(query, c) for c in candidates if c),
            default=0.0,
        )
        scored.append((best_score, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_score, top_result = scored[0]

    return top_result if top_score >= MATCH_THRESHOLD else None


def best_anilist_match(query: str, results: list[dict]) -> dict | None:
    """Pick the best AniList media result for *query* using local fuzzy matching.

    Each AniList result dict is expected to have a nested title object:
        { "title": { "romaji": "...", "english": "...", "native": "..." } }

    Returns the highest-scoring result if its score meets MATCH_THRESHOLD,
    otherwise returns None.

    Parameters
    ----------
    query:
        The title string used to search AniList.
    results:
        List of media dicts from AniList's Page.media array.
    """
    if not results:
        return None

    scored: list[tuple[float, dict]] = []

    for r in results:
        title_obj = r.get("title") or {}
        candidates = [
            title_obj.get("romaji") or "",
            title_obj.get("english") or "",
            title_obj.get("native") or "",
        ]
        best_score = max(
            (title_similarity(query, c) for c in candidates if c),
            default=0.0,
        )
        scored.append((best_score, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_score, top_result = scored[0]

    return top_result if top_score >= MATCH_THRESHOLD else None
