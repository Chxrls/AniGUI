import base64
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from urllib.parse import quote
import requests
from Crypto.Cipher import AES

API_BASE = "https://api.allanime.day/api"
ALLANIME_BASE = "allanime.day"

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Origin": "https://youtu-chan.com",
    "Referer": "https://allmanga.to",
    "Accept": "application/json",
}

EPISODE_HASH = "d405d0edd690624b66baba3068e0edc3ac90f1597d898a1ec8db4e5c43c00fec"
AES_KEY_PHRASE = "Xot36i3lK3:v1"
AES_KEY = hashlib.sha256(AES_KEY_PHRASE.encode()).digest()

def check_mpv_installed() -> bool:
    return shutil.which("mpv") is not None

def gql_post(query: str, variables: dict | None = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    headers = {**API_HEADERS, "Content-Type": "application/json"}
    try:
        resp = requests.post(API_BASE, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise RuntimeError(f"GraphQL POST failed: {e}") from e

    if "errors" in data:
        msgs = [err.get("message", "unknown") for err in data["errors"]]
        raise RuntimeError(f"GraphQL errors: {'; '.join(msgs)}")

    return data

def gql_get_persisted(query_hash: str, variables: dict) -> dict:
    vars_json = json.dumps(variables)
    ext_json = json.dumps({
        "persistedQuery": {"version": 1, "sha256Hash": query_hash}
    })
    url = f"{API_BASE}?variables={quote(vars_json)}&extensions={quote(ext_json)}"
    try:
        resp = requests.get(url, headers=API_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise RuntimeError(f"GraphQL GET failed: {e}") from e
    return data

SEARCH_GQL = """
query($search: SearchInput, $limit: Int, $page: Int,
      $translationType: VaildTranslationTypeEnumType,
      $countryOrigin: VaildCountryOriginEnumType) {
  shows(search: $search, limit: $limit, page: $page,
        translationType: $translationType, countryOrigin: $countryOrigin) {
    edges {
      _id
      name
      englishName
      nativeName
      availableEpisodesDetail
      __typename
    }
  }
}
"""

def search_anime(query: str) -> list[dict]:
    variables = {
        "search": {"query": query, "allowAdult": False},
        "limit": 20,
        "page": 1,
        "translationType": "sub",
        "countryOrigin": "ALL",
    }
    data = gql_post(SEARCH_GQL, variables)
    shows = (data.get("data", {})
                 .get("shows", {})
                 .get("edges", []))
    results = []
    for edge in shows:
        name = edge.get("name", "Unknown")
        english_name = edge.get("englishName") or edge.get("nativeName") or name
        ep_detail = edge.get("availableEpisodesDetail", {}) or {}
        sub_eps = ep_detail.get("sub", []) or []
        dub_eps = ep_detail.get("dub", []) or []
        results.append({
            "id": edge.get("_id", ""),
            "name": name,
            "english_name": english_name,
            "sub_count": len(sub_eps),
            "dub_count": len(dub_eps),
            "sub_episodes": sorted(sub_eps, key=lambda x: float(x) if x.replace('.', '', 1).isdigit() else 0),
            "dub_episodes": sorted(dub_eps, key=lambda x: float(x) if x.replace('.', '', 1).isdigit() else 0),
        })
    return results

def fetch_episodes(anime: dict, translation_type: str = "sub") -> list[dict]:
    key = "sub_episodes" if translation_type == "sub" else "dub_episodes"
    ep_strings = anime.get(key, [])
    episodes = []
    for ep_str in ep_strings:
        try:
            ep_num = float(ep_str)
        except (TypeError, ValueError):
            ep_num = 0
        episodes.append({
            "number": ep_num,
            "number_str": ep_str,
        })
    episodes.sort(key=lambda e: e["number"])
    return episodes

def fetch_episode_sources(anime_id: str, episode_str: str, translation_type: str = "sub") -> dict:
    variables = {
        "showId": anime_id,
        "translationType": translation_type,
        "episodeString": episode_str,
    }
    data = gql_get_persisted(EPISODE_HASH, variables)
    return data.get("data", {})

def decrypt_source_blob(b64_blob: str) -> dict:
    try:
        raw = base64.b64decode(b64_blob)
    except Exception as e:
        raise RuntimeError(f"Base64 decode failed: {e}") from e

    if len(raw) < 29:
        raise RuntimeError(f"Blob too short ({len(raw)} bytes), expected >= 29")

    nonce = raw[1:13]
    ciphertext = raw[13:-16]
    initial_counter = nonce + b'\x00\x00\x00\x02'

    try:
        cipher = AES.new(AES_KEY, AES.MODE_CTR, initial_value=initial_counter, nonce=b'')
        plaintext = cipher.decrypt(ciphertext)
    except Exception as e:
        raise RuntimeError(f"AES decryption failed: {e}") from e

    try:
        return json.loads(plaintext.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise RuntimeError(f"Decrypted data is not valid JSON: {e}") from e

HEX_DECODE_MAP = {
    "79": "A", "7a": "B", "7b": "C", "7c": "D", "7d": "E", "7e": "F",
    "7f": "G", "70": "H", "71": "I", "72": "J", "73": "K", "74": "L",
    "75": "M", "76": "N", "77": "O", "68": "P", "69": "Q", "6a": "R",
    "6b": "S", "6c": "T", "6d": "U", "6e": "V", "6f": "W", "60": "X",
    "61": "Y", "62": "Z", "59": "a", "5a": "b", "5b": "c", "5c": "d",
    "5d": "e", "5e": "f", "5f": "g", "50": "h", "51": "i", "52": "j",
    "53": "k", "54": "l", "55": "m", "56": "n", "57": "o", "48": "p",
    "49": "q", "4a": "r", "4b": "s", "4c": "t", "4d": "u", "4e": "v",
    "4f": "w", "40": "x", "41": "y", "42": "z", "08": "0", "09": "1",
    "0a": "2", "0b": "3", "0c": "4", "0d": "5", "0e": "6", "0f": "7",
    "00": "8", "01": "9", "15": "-", "16": ".", "67": "_", "46": "~",
    "02": ":", "17": "/", "07": "?", "1b": "#", "63": "[", "65": "]",
    "78": "@", "19": "!", "1c": "$", "1e": "&", "10": "(", "11": ")",
    "12": "*", "13": "+", "14": ",", "03": ";", "05": "=", "1d": "%",
    "--": "\n",
}

def decode_hex_url(encoded: str) -> str:
    result = []
    i = 0
    while i < len(encoded):
        pair = encoded[i:i+2]
        if pair in HEX_DECODE_MAP:
            result.append(HEX_DECODE_MAP[pair])
            i += 2
        else:
            result.append(pair)
            i += 2
    decoded = "".join(result)
    decoded = decoded.replace("/clock", "/clock.json")
    return decoded

def resolve_stream_url(anime_id: str, episode_str: str, translation_type: str = "sub") -> str:
    source_data = fetch_episode_sources(anime_id, episode_str, translation_type)
    if not source_data:
        raise RuntimeError("No episode data returned from API.")

    top_blob = source_data.get("tobeparsed")
    if not top_blob:
        raise RuntimeError("No encrypted data found for this episode.")

    try:
        decrypted = decrypt_source_blob(top_blob)
    except RuntimeError as e:
        raise RuntimeError(f"Decryption failed: {e}") from e

    episode = decrypted.get("episode", decrypted) if isinstance(decrypted, dict) else {}
    source_urls = episode.get("sourceUrls", [])
    if not source_urls:
        raise RuntimeError("No source URLs found in decrypted episode data.")

    source_urls.sort(key=lambda s: float(s.get("priority", 0)), reverse=True)
    errors = []

    for source in source_urls:
        source_url = source.get("sourceUrl", "")
        source_name = source.get("sourceName", "?")
        source_type = source.get("type", "")

        if source_type == "player" and source_url.startswith("http"):
            return source_url

        if source_url.startswith("--"):
            decoded = decode_hex_url(source_url)
            if decoded.startswith("/"):
                embed_url = f"https://{ALLANIME_BASE}{decoded}"
            else:
                embed_url = decoded
            try:
                stream = _fetch_embed_stream(embed_url)
                if stream:
                    return stream
            except Exception as e:
                errors.append(f"  {source_name}: embed fetch failed - {e}")
                continue

        if source_url.startswith("http") and ("m3u8" in source_url or ".mp4" in source_url):
            return source_url

    detail = "\n".join(errors) if errors else "No directly playable URLs found."
    raise RuntimeError(f"Could not resolve a playable URL.\n{detail}")

def _fetch_embed_stream(embed_url: str) -> str | None:
    import re
    try:
        resp = requests.get(embed_url, headers={
            "User-Agent": API_HEADERS["User-Agent"],
            "Referer": "https://allmanga.to",
        }, timeout=10)
        resp.raise_for_status()
        text = resp.text

        try:
            data = resp.json()
            if isinstance(data, dict):
                for link in data.get("links", []):
                    if isinstance(link, dict):
                        u = link.get("link") or link.get("src") or link.get("url")
                        if u and u.startswith("http"):
                            return u
                for key in ("link", "url", "file", "src"):
                    if key in data and isinstance(data[key], str) and data[key].startswith("http"):
                        return data[key]
        except (json.JSONDecodeError, ValueError):
            pass

        patterns = [
            r'"(https?://[^"]*\.m3u8[^"]*)"',
            r'"(https?://[^"]*\.mp4[^"]*)"',
            r"'(https?://[^']*\.m3u8[^']*)'",
            r"'(https?://[^']*\.mp4[^']*)'",
            r'"link"\s*:\s*"(https?://[^"]*)"',
            r'"file"\s*:\s*"(https?://[^"]*)"',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
    except requests.RequestException:
        pass
    return None

def launch_player(url: str, episode_label: str) -> None:
    cmd = [
        "mpv",
        "--no-terminal",
        url,
        "--http-header-fields=Referer: https://allmanga.to",
        f"--title={episode_label}",
    ]
    try:
        kwargs = {"start_new_session": True}
        if platform.system() == "Windows":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs["startupinfo"] = si

        subprocess.Popen(cmd, **kwargs)
    except FileNotFoundError:
        raise RuntimeError("mpv not found. Is it installed and on PATH?")
    except OSError as e:
        raise RuntimeError(f"Failed to launch mpv: {e}")
