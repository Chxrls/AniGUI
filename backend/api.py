import os
import sys
import json
import hashlib
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

# Import local db cache
from anigui.backend.db import db

# Re-export AllAnime backend APIs
def search_anime(query: str) -> list[dict]:
    return _allanime_search(query)

def fetch_episodes(anime: dict, translation_type: str = "sub") -> list[dict]:
    return _allanime_episodes(anime, translation_type)

def resolve_stream_url(anime_id: str, episode_str: str, translation_type: str = "sub") -> str:
    return _allanime_resolve(anime_id, episode_str, translation_type)

def launch_player(url: str, episode_label: str) -> None:
    _allanime_launch(url, episode_label)

def check_mpv_installed() -> bool:
    return _allanime_check_mpv()

# AniList GraphQL configuration
ANILIST_API_URL = "https://graphql.anilist.co"

ANILIST_SEARCH_QUERY = """
query ($search: String) {
  Page(page: 1, perPage: 1) {
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
    }
  }
}
"""

def get_anilist_metadata(title: str) -> Optional[dict]:
    """Retrieve detailed metadata for an anime from AniList GraphQL API.

    Uses title as query. Caches GraphQL responses in SQLite database.
    """
    if not title:
        return None

    # Compute a cache key based on the normalized title
    normalized_title = title.strip().lower()
    cache_key = f"anilist_meta:{hashlib.sha256(normalized_title.encode('utf-8')).hexdigest()}"

    # Check database cache first
    cached_val = db.get_cached(cache_key)
    if cached_val:
        try:
            return json.loads(cached_val)
        except Exception:
            pass

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
            metadata = media_list[0]
            # Save in cache for 24 hours (86400 seconds)
            db.set_cached(cache_key, json.dumps(metadata), ttl_seconds=86400)
            return metadata
    except Exception:
        # Silently fail, returns None or uses default placeholders
        pass

    return None
