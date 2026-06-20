"""Miruro video-source backend.

Miruro uses a dual-layer architecture:
  1. Metadata — AniList public GraphQL API (handled by api.py)
  2. Video sources — Encrypted ``/api/secure/pipe`` tunnel

The pipe protocol is: Base64-URL-encode the JSON request, send as ``?e=<encoded>``.
The response is Base64 + Gzip compressed JSON.

This module handles *only* the video-source layer (layer 2).
"""

import base64
import gzip
import json
import logging
from typing import Optional

import requests

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIRURO_PIPE_URL = "https://www.miruro.tv/api/secure/pipe"
MIRURO_REFERER = "https://www.miruro.tv/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": MIRURO_REFERER,
}

# Provider priority order from Miruro's __SSR_CONFIG__.
# Only "native" (non-iframe) providers that return direct M3U8 URLs.
PROVIDER_ORDER: list[str] = [
    "kiwi", "pewe", "bonk", "bee", "ally", "moo", "hop",
]

# Full provider metadata — parsed from __SSR_CONFIG__.
# This is intentionally hardcoded for stability; the SSR config rarely changes.
PROVIDER_CONFIG: dict[str, dict] = {
    "kiwi":  {"sub": True,  "dub": False, "download": True,  "skip_times": False, "thumbnails": False},
    "pewe":  {"sub": True,  "dub": False, "download": False, "skip_times": False, "thumbnails": False},
    "bonk":  {"sub": True,  "dub": True,  "download": True,  "skip_times": True,  "thumbnails": False},
    "bee":   {"sub": False, "dub": True,  "download": False, "skip_times": False, "thumbnails": False},
    "ally":  {"sub": True,  "dub": False, "download": True,  "skip_times": False, "thumbnails": True},
    "moo":   {"sub": True,  "dub": False, "download": True,  "skip_times": False, "thumbnails": False},
    "hop":   {"sub": False, "dub": True,  "download": False, "skip_times": False, "thumbnails": True},
}


# ---------------------------------------------------------------------------
# Pipe encoding / decoding
# ---------------------------------------------------------------------------

def _encode_pipe_request(payload: dict) -> str:
    """Encode a JSON payload into the Base64 format expected by Miruro's pipe."""
    return base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).decode().rstrip("=")


def _decode_pipe_response(encoded_str: str) -> dict:
    """Decode a Base64 + Gzip pipe response into a plain dict."""
    # Pad to a multiple of 4 for valid Base64
    encoded_str += "=" * (4 - len(encoded_str) % 4)
    compressed = base64.urlsafe_b64decode(encoded_str)
    return json.loads(gzip.decompress(compressed).decode("utf-8"))


def _translate_id(encoded_id: str) -> str:
    """Decode a Base64-encoded episode ID back to plain text."""
    try:
        decoded = base64.urlsafe_b64decode(
            encoded_id + "=" * (4 - len(encoded_id) % 4)
        ).decode()
        if ":" in decoded:
            return decoded
        return encoded_id
    except Exception:
        return encoded_id


def _deep_translate(obj):
    """Recursively walk a JSON structure and decode any Base64 'id' fields."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "id" and isinstance(value, str):
                obj[key] = _translate_id(value)
            elif isinstance(value, (dict, list)):
                _deep_translate(value)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                _deep_translate(item)


# ---------------------------------------------------------------------------
# Pipe request helper
# ---------------------------------------------------------------------------

def _pipe_request(path: str, query: dict) -> dict:
    """Send a request through Miruro's secure/pipe and return decoded data."""
    payload = {
        "path": path,
        "method": "GET",
        "query": query,
        "body": None,
        "version": "0.1.0",
    }
    encoded = _encode_pipe_request(payload)
    url = f"{MIRURO_PIPE_URL}?e={encoded}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = _decode_pipe_response(resp.text.strip())
        _deep_translate(data)
        return data
    except requests.RequestException as e:
        log.warning("Miruro pipe request failed: %s", e)
        raise RuntimeError(f"Miruro pipe request failed: {e}") from e
    except (ValueError, json.JSONDecodeError) as e:
        log.warning("Miruro pipe decode failed: %s", e)
        raise RuntimeError(f"Miruro pipe decode failed: {e}") from e


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_available_providers() -> list[dict]:
    """Return the ordered list of provider names and their capabilities."""
    result = []
    for name in PROVIDER_ORDER:
        cfg = PROVIDER_CONFIG.get(name, {})
        result.append({"name": name, **cfg})
    return result


def fetch_episodes(anilist_id: int) -> dict:
    """Fetch the episode list for an anime by its AniList ID.

    Returns the raw decoded episode data from Miruro's pipe, which contains
    a ``providers`` dict keyed by provider name.  Each provider has an
    ``episodes`` dict keyed by category (``sub`` / ``dub``), each containing
    a list of episode dicts with at least ``id`` and ``number`` fields.
    """
    data = _pipe_request("episodes", {"anilistId": anilist_id})
    return data


def fetch_episode_list(anilist_id: int, translation_type: str = "sub") -> list[dict]:
    """Fetch a flat, sorted list of episodes for the given translation type.

    This is a convenience wrapper around ``fetch_episodes()`` that picks the
    best provider and returns a simple list compatible with the existing
    ``api.fetch_episodes()`` contract:

        [{"number": 1.0, "number_str": "1"}, ...]

    The ``provider`` field is added to each episode dict so the resolver
    knows where to fetch the stream from.
    """
    raw = fetch_episodes(anilist_id)
    providers = raw.get("providers", {})

    # Determine which category key to look for
    category = "sub" if translation_type == "sub" else "dub"

    # Walk providers in priority order, return first one with episodes
    for provider_name in PROVIDER_ORDER:
        provider_data = providers.get(provider_name)
        if not isinstance(provider_data, dict):
            continue

        episodes_map = provider_data.get("episodes", {})
        if isinstance(episodes_map, list):
            episodes_map = {"sub": episodes_map}

        ep_list = episodes_map.get(category, [])
        if not ep_list:
            continue

        result = []
        for ep in ep_list:
            if not isinstance(ep, dict):
                continue
            ep_num = ep.get("number", 0)
            try:
                ep_num_float = float(ep_num)
            except (TypeError, ValueError):
                ep_num_float = 0
            result.append({
                "number": ep_num_float,
                "number_str": str(ep_num),
                "miruro_id": ep.get("id", ""),
                "provider": provider_name,
            })

        result.sort(key=lambda e: e["number"])
        return result

    return []


def resolve_stream_url(
    anilist_id: int,
    episode_str: str,
    translation_type: str = "sub",
    provider: Optional[str] = None,
    progress_callback: Optional[callable] = None,
) -> tuple[str, str]:
    """Resolve a playable M3U8/MP4 stream URL for an episode.

    Parameters
    ----------
    anilist_id : int
        The AniList media ID.
    episode_str : str
        The episode number as a string (e.g., "1", "12.5").
    translation_type : str
        "sub" or "dub".
    provider : str or None
        Specific provider name to use, or None for auto-select.
    progress_callback : callable or None
        Optional callback for progress messages.

    Returns
    -------
    tuple[str, str]
        (stream_url, referer)
    """
    raw = fetch_episodes(anilist_id)
    providers = raw.get("providers", {})
    category = "sub" if translation_type == "sub" else "dub"

    # Build the list of providers to try
    if provider and provider in providers:
        provider_names = [provider]
    else:
        provider_names = PROVIDER_ORDER

    errors = []
    attempt = 0

    for prov_name in provider_names:
        prov_data = providers.get(prov_name)
        if not isinstance(prov_data, dict):
            continue

        episodes_map = prov_data.get("episodes", {})
        if isinstance(episodes_map, list):
            episodes_map = {"sub": episodes_map}

        ep_list = episodes_map.get(category, [])
        if not ep_list:
            continue

        # Find the matching episode
        target_ep = None
        for ep in ep_list:
            if not isinstance(ep, dict):
                continue
            if str(ep.get("number", "")) == episode_str:
                target_ep = ep
                break

        if not target_ep:
            continue

        episode_id = target_ep.get("id", "")
        if not episode_id:
            continue

        attempt += 1
        if progress_callback:
            progress_callback(f"Trying provider {prov_name} ({attempt}/{len(provider_names)})...")

        try:
            stream_result = _resolve_episode_stream(anilist_id, episode_id, prov_name, category)
            if stream_result:
                url, referer = stream_result
                return url, referer or MIRURO_REFERER
        except Exception as e:
            errors.append(f"  {prov_name}: {e}")
            continue

    detail = "\n".join(errors) if errors else "No providers had this episode."
    raise RuntimeError(f"Miruro: Could not resolve stream URL.\n{detail}")


def _resolve_episode_stream(
    anilist_id: int,
    episode_id: str,
    provider: str,
    category: str,
) -> Optional[tuple[str, Optional[str]]]:
    """Resolve the actual M3U8 stream URL and its required referer.

    Tries several pipe path formats that Miruro's backend may expect.
    """
    prefix = episode_id.split(":")[0] if ":" in episode_id else episode_id

    enc_id = base64.urlsafe_b64encode(episode_id.encode()).decode().rstrip('=')
    
    path_queries = [
        ("sources", {
            "episodeId": enc_id,
            "provider": provider,
            "category": category,
            "anilistId": anilist_id,
        })
    ]

    for path, query in path_queries:
        try:
            data = _pipe_request(path, query)
        except RuntimeError:
            continue

        if not isinstance(data, dict):
            continue

        result = _extract_stream_url(data)
        if result:
            return result

    return None


def _extract_stream_url(data: dict) -> Optional[tuple[str, Optional[str]]]:
    """Extract a playable stream URL and referer from a Miruro pipe response."""
    for key in ("sources", "streams"):
        items = data.get(key, [])
        if isinstance(items, list):
            for src in items:
                if isinstance(src, dict):
                    url = src.get("url") or src.get("file") or src.get("link")
                    if url and isinstance(url, str) and url.startswith("http"):
                        return url, src.get("referer")

    for key in ("url", "link", "file", "source"):
        val = data.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val, data.get("referer")

    nested = data.get("data", {})
    if isinstance(nested, dict):
        for src in nested.get("sources", []) + nested.get("streams", []):
            if isinstance(src, dict):
                url = src.get("url") or src.get("file")
                if url and isinstance(url, str) and url.startswith("http"):
                    return url, src.get("referer")

    stream = data.get("stream")
    if isinstance(stream, str) and stream.startswith("http"):
        return stream, data.get("referer")
    if isinstance(stream, dict):
        stream_result = _extract_stream_url(stream)
        if stream_result:
            return stream_result

    return None
