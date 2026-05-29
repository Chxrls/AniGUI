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


def clean_search_query(query: str) -> str:
    """Strip special characters that break AllAnime's search API.

    AllAnime's search engine returns 0 results when the query contains
    apostrophes, curly quotes, or other punctuation that isn't part of the
    actual title text (e.g. AniList uses "Gintama'" for Season 2).

    This function removes those characters to produce a safer search query
    while preserving semicolons (needed for titles like "Steins;Gate").
    """
    import re
    # Remove apostrophes, curly quotes, and other problematic punctuation
    cleaned = re.sub(r"[''`\"°]", "", query)
    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def best_allanime_match(
    query: str,
    results: list[dict],
    expected_episodes: int = 0,
    alt_titles: list[str] | None = None,
) -> dict | None:
    """Pick the best AllAnime result for *query* using local fuzzy matching.

    Each AllAnime result dict is expected to have at least:
        "name"         — romaji / primary title
        "english_name" — English title (may be the same as name)
        "sub_count"    — number of sub episodes (used for tiebreaker)

    Returns the highest-scoring result if its score meets MATCH_THRESHOLD,
    otherwise returns None to signal no confident match was found.

    Parameters
    ----------
    query:
        The primary title string used to search AllAnime.
    results:
        Raw list of dicts returned by allanime.search_anime().
    expected_episodes:
        If > 0, episode count from AniList metadata.  Used as a tiebreaker
        when multiple results have similar title scores.
    alt_titles:
        Additional title variants to score against (e.g. the English title
        when *query* is the romaji title).  Each non-empty variant is scored
        independently and the best score across all variants wins.
    """
    if not results:
        return None

    # Build the full list of query variants to score against
    queries = [query] + [t for t in (alt_titles or []) if t]

    scored: list[tuple[float, dict]] = []

    for r in results:
        candidates = [
            r.get("name") or "",
            r.get("english_name") or "",
        ]

        # Score against every (query-variant × result-title) pair
        best_title_score = 0.0
        for q in queries:
            for c in candidates:
                if not c:
                    continue
                sim = title_similarity(q, c)
                best_title_score = max(best_title_score, sim)

        # Episode-count tiebreaker bonus
        ep_bonus = 0.0
        if expected_episodes > 0:
            result_eps = r.get("sub_count", 0)
            if result_eps > 0 and result_eps == expected_episodes:
                ep_bonus = 0.1        # strong bonus for exact match
            elif result_eps > 0 and abs(result_eps - expected_episodes) <= 2:
                ep_bonus = 0.05       # small bonus for close match

        scored.append((best_title_score + ep_bonus, r))

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
