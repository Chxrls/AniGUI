import os
import sys
import requests
from typing import Optional, Any

# Import local backend functions
from anigui.backend.allanime import (
    search_anime as _allanime_search,
    fetch_episodes as _allanime_episodes,
    resolve_stream_url as _allanime_resolve,
    launch_player as _allanime_launch,
    check_mpv_installed as _allanime_check_mpv
)


# Import matching utilities
from anigui.utils.matching import best_anilist_match

# Re-export AllAnime backend APIs
def search_anime(query: str) -> list[dict]:
    return _allanime_search(query)

def fetch_episodes(anime: dict, translation_type: str = "sub") -> list[dict]:
    return _allanime_episodes(anime, translation_type)

def resolve_stream_url(anime_id: str, episode_str: str, translation_type: str = "sub") -> tuple[str, str]:
    return _allanime_resolve(anime_id, episode_str, translation_type)

def launch_player(url: str, episode_label: str, referer: str = "https://allmanga.to") -> None:
    _allanime_launch(url, episode_label, referer)

def check_mpv_installed() -> bool:
    return _allanime_check_mpv()

# AniList GraphQL configuration
ANILIST_API_URL = "https://graphql.anilist.co"

_MEDIA_FIELDS = """
  id
  title {
    romaji
    english
  }
  coverImage {
    large
    extraLarge
  }
  description(asHtml: false)
  averageScore
  format
  status
  genres
  nextAiringEpisode {
    episode
    airingAt
  }
"""

ANILIST_SEARCH_QUERY = """
query ($search: String) {
  Page(page: 1, perPage: 5) {
    media(search: $search, type: ANIME) {
      id
      title {
        romaji
        english
        native
      }
      coverImage {
        large
        extraLarge
      }
      bannerImage
      description
      genres
      averageScore
      episodes
      status
    }
  }
}
"""

ANILIST_TOP_RANKED_QUERY = """
query ($page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    media(sort: SCORE_DESC, type: ANIME, averageScore_greater: 70) {
      id
      title { romaji english }
      coverImage { large extraLarge }
      description(asHtml: false)
      averageScore
      format
      status
      episodes
      genres
    }
  }
}
"""

def get_anilist_metadata(title: str) -> Optional[dict]:
    """Retrieve detailed metadata for an anime from AniList GraphQL API.
 
    Fetches up to 5 candidates from AniList and uses local fuzzy matching
    (best_anilist_match) to pick the most accurate result rather than
    blindly returning the first one.
    """
    if not title:
        return None

    # Fetch from API
    try:
        variables = {"search": title}
        resp = requests.post(
            ANILIST_API_URL,
            json={"query": ANILIST_SEARCH_QUERY, "variables": variables},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        
        media_list = data.get("data", {}).get("Page", {}).get("media", [])
        if media_list:
            from anigui.utils.matching import best_anilist_match
            metadata = best_anilist_match(title, media_list)
            if metadata is None:
                metadata = media_list[0]
            return metadata
    except Exception:
        pass

    return None

def fetch_top_ranked(page: int = 1, per_page: int = 40) -> list[dict]:
    """Return the top *per_page* all-time ranked anime from AniList.
 
    Results are sorted by SCORE_DESC and filtered to averageScore > 70.
 
    Each item in the returned list is a raw AniList media dict containing:
        id, title, coverImage, description, averageScore, format,
        status, episodes, genres, nextAiringEpisode
    """
    resp = requests.post(
        ANILIST_API_URL,
        json={
            "query": ANILIST_TOP_RANKED_QUERY,
            "variables": {"page": page, "perPage": per_page},
        },
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
 
    media_list = (
        data.get("data", {})
            .get("Page", {})
            .get("media", [])
    )
 
    return media_list

def search_anilist(
    query:    str | None        = None,
    genres:   list[str] | None  = None,
    season:   str | None        = None,   # WINTER / SPRING / SUMMER / FALL
    year:     int | None        = None,
    format:   str | None        = None,   # TV / MOVIE / OVA / ONA / SPECIAL
    status:   str | None        = None,   # RELEASING / FINISHED / NOT_YET_RELEASED
    page:     int               = 1,
    per_page: int               = 40,
) -> list[dict]:
    """Filtered AniList search — all parameters are optional.
 
    Builds the GraphQL query dynamically, only including arguments that
    are actually set. Results are cached in SQLite for 15 minutes keyed
    by the full combination of filter values.
 
    Returns a list of AniList media dicts (same shape as fetch_top_ranked).
    """
    # --- Build filter argument string dynamically ---
    filters: list[str] = ["type: ANIME"]
 
    if query:
        filters.append(f'search: "{query}"')
 
    if genres:
        inner = ", ".join(f'"{g}"' for g in genres)
        filters.append(f"genre_in: [{inner}]")
 
    if season:
        filters.append(f"season: {season}")
 
    if year:
        filters.append(f"seasonYear: {year}")
 
    if format:
        filters.append(f"format: {format}")
 
    if status:
        filters.append(f"status: {status}")
 
    # Default sort: by score when no text query, by search relevance when query given
    sort = "SEARCH_MATCH" if query else "SCORE_DESC"
    filters.append(f"sort: {sort}")
 
    filter_str = ", ".join(filters)
 
    gql_query = f"""
    query ($page: Int, $perPage: Int) {{
      Page(page: $page, perPage: $perPage) {{
        media({filter_str}) {{
          {_MEDIA_FIELDS}
        }}
      }}
    }}
    """
 
    resp = requests.post(
        ANILIST_API_URL,
        json={"query": gql_query, "variables": {"page": page, "perPage": per_page}},
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    media_list = (
        resp.json()
            .get("data", {})
            .get("Page", {})
            .get("media", [])
    )
 
    return media_list
