"""
views/home.py  —  AniGUI Home View
Implements Miruro-style front-page sections:
  • Media format row (TV Series, Movies, ONA, OVA, Specials)
  • Section tabs (Trending / Popular / Top Rated / Airing Now / Upcoming / Schedule)
  • Genre filter strip (active only for Trending / Popular / Top Rated)

Data source: AniList GraphQL API (https://graphql.anilist.co)
Image cache : ~/.config/anigui/thumbnails/  (same as rest of app)
Worker model: QThread per fetch, signals back to UI thread.
"""

from __future__ import annotations
from anigui.utils.theme import apply_theme

import os
import hashlib
import time
import json
from typing import Callable, Optional

import requests

from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer,
)
from PyQt6.QtGui import QPixmap, QCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QScrollArea, QLabel, QPushButton, QFrame,
    QSizePolicy, QStackedWidget, QApplication, QComboBox,
)

from anigui.backend.db import db
from anigui.backend.api import get_anilist_metadata
from anigui.backend.worker import MetadataWorker, ThumbnailWorker

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ANILIST_URL = "https://graphql.anilist.co"
THUMB_DIR = os.path.expanduser("~/.config/anigui/thumbnails")
os.makedirs(THUMB_DIR, exist_ok=True)

# --- Media format filter (Row 1) ---
FORMATS = ["TV Series", "Movies", "ONA", "OVA", "Specials"]

# AniList GraphQL `format` enum values
FORMAT_MAP = {
    "TV Series": "TV",
    "Movies": "MOVIE",
    "ONA": "ONA",
    "OVA": "OVA",
    "Specials": "SPECIAL",
}

# Which section tabs to show per format
FORMAT_SECTIONS = {
    "TV Series": ["Trending", "Popular", "Top Rated", "Airing Now", "Upcoming", "Schedule"],
    "Movies":    ["Trending", "Popular", "Top Rated"],
    "ONA":       ["Trending", "Popular", "Top Rated", "Airing Now", "Upcoming", "Schedule"],
    "OVA":       ["Trending", "Popular", "Top Rated"],
    "Specials":  ["Trending", "Popular", "Top Rated"],
}

# Sections where the genre filter strip is visible
GENRE_SECTIONS = {"Trending", "Popular", "Top Rated"}

GENRES = [
    "Action", "Adventure", "Comedy", "Drama", "Fantasy",
    "Horror", "Mecha", "Music", "Mystery", "Psychological", "Romance",
    "Sci-Fi", "Slice of Life", "Sports", "Supernatural", "Thriller",
]

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Card sizing — cards will be given a fixed width matching the existing
# widgets/card.py approach (180px) and will reflow dynamically on resize.
CARD_FIXED_W = 180
CARD_MARGIN = 8          # internal content margin
CARD_IMG_W = 164         # 180 - 2*8
CARD_IMG_H = 246         # aspect ratio ~1.5 matching existing card
CARD_SPACING_H = 15
CARD_SPACING_V = 15


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _truncate(text: str, max_len: int) -> str:
    """Truncate text without cutting mid-word-ish; appends '…' if trimmed."""
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


def _anilist_to_app_dict(media: dict) -> dict:
    """Convert an AniList media dict into the format expected by
    AnimeDetailDialog / AnimeDetailWidget.

    NOTE: The 'id' field is intentionally left empty here because AniList
    numeric IDs do not work with the AllAnime streaming backend.  The
    correct AllAnime '_id' is resolved at click time via
    AllAnimeResolveWorker and merged in before the dialog opens.
    """
    title_obj = media.get("title") or {}
    romaji = title_obj.get("romaji") or ""
    english = title_obj.get("english") or ""
    name = english or romaji or "Unknown Title"

    cover = media.get("coverImage") or {}
    cover_url = cover.get("large") or cover.get("medium") or ""

    # Resolve cached thumbnail path
    thumb_local = ""
    if cover_url:
        thumb_local = _cache_path(cover_url)
        if not os.path.exists(thumb_local):
            thumb_local = ""  # not yet downloaded

    score = media.get("averageScore") or 0
    eps = media.get("episodes") or 0
    fmt = media.get("format") or ""
    genres = media.get("genres") or []
    synopsis = media.get("description") or ""
    next_ep = media.get("nextAiringEpisode") or {}

    return {
        # 'id' intentionally omitted — will be filled with AllAnime _id
        "name": name,
        "english_name": english if (english and romaji and english.lower() != romaji.lower()) else "",
        "synopsis": synopsis,
        "genres": genres,
        "score": score,
        "sub_count": eps,
        "dub_count": 0,
        "thumbnail_url_local": thumb_local,
        "thumbnail_url": cover_url,
        "format": fmt,
        "episodes": eps,
        "averageScore": score,
        "status": media.get("status"),
        "nextAiringEpisode": next_ep,
        "coverImage": cover,
        "title": title_obj,
    }


# ---------------------------------------------------------------------------
# AniList GraphQL helpers
# ---------------------------------------------------------------------------

_MEDIA_FIELDS = """
  id
  title { romaji english }
  coverImage { large medium }
  description(asHtml: false)
  averageScore
  format
  status
  episodes
  genres
  nextAiringEpisode { episode airingAt }
"""

_AIRING_FIELDS = """
  id
  episode
  airingAt
  media {
    id
    title { romaji english }
    coverImage { large medium }
    description(asHtml: false)
    genres
    format
    episodes
    averageScore
    status
    nextAiringEpisode { episode airingAt }
  }
"""


def _gql(query: str, variables: dict) -> dict:
    resp = requests.post(
        ANILIST_URL,
        json={"query": query, "variables": variables},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _genre_gql_list(genres: list[str] | None) -> str:
    """Format a Python genre list into valid GraphQL list syntax."""
    if not genres:
        return ""
    inner = ", ".join(f'"{g}"' for g in genres)
    return f', genre_in: [{inner}]'


def _format_gql(anime_format: str | None) -> str:
    """Format filter clause for AniList GraphQL."""
    if not anime_format:
        return ""
    return f', format: {anime_format}'


def fetch_trending(genres: list[str] | None = None, anime_format: str | None = None,
                   page: int = 1, per_page: int = 40) -> list[dict]:
    genre_filter = _genre_gql_list(genres)
    format_filter = _format_gql(anime_format)
    q = f"""
    query($page: Int, $perPage: Int) {{
      Page(page: $page, perPage: $perPage) {{
        media(sort: TRENDING_DESC, type: ANIME{format_filter}{genre_filter}) {{
          {_MEDIA_FIELDS}
        }}
      }}
    }}
    """
    data = _gql(q, {"page": page, "perPage": per_page})
    return data["data"]["Page"]["media"]


def fetch_popular(genres: list[str] | None = None, anime_format: str | None = None,
                  page: int = 1, per_page: int = 40) -> list[dict]:
    genre_filter = _genre_gql_list(genres)
    format_filter = _format_gql(anime_format)
    q = f"""
    query($page: Int, $perPage: Int) {{
      Page(page: $page, perPage: $perPage) {{
        media(sort: POPULARITY_DESC, type: ANIME{format_filter}{genre_filter}) {{
          {_MEDIA_FIELDS}
        }}
      }}
    }}
    """
    data = _gql(q, {"page": page, "perPage": per_page})
    return data["data"]["Page"]["media"]


def fetch_top_rated(genres: list[str] | None = None, anime_format: str | None = None,
                    page: int = 1, per_page: int = 40) -> list[dict]:
    genre_filter = _genre_gql_list(genres)
    format_filter = _format_gql(anime_format)
    q = f"""
    query($page: Int, $perPage: Int) {{
      Page(page: $page, perPage: $perPage) {{
        media(sort: SCORE_DESC, type: ANIME, averageScore_greater: 70{format_filter}{genre_filter}) {{
          {_MEDIA_FIELDS}
        }}
      }}
    }}
    """
    data = _gql(q, {"page": page, "perPage": per_page})
    return data["data"]["Page"]["media"]


def fetch_airing(anime_format: str | None = None,
                 page: int = 1, per_page: int = 40) -> list[dict]:
    format_filter = _format_gql(anime_format)
    q = f"""
    query($page: Int, $perPage: Int) {{
      Page(page: $page, perPage: $perPage) {{
        media(status: RELEASING, sort: TRENDING_DESC, type: ANIME{format_filter}) {{
          {_MEDIA_FIELDS}
        }}
      }}
    }}
    """
    data = _gql(q, {"page": page, "perPage": per_page})
    return data["data"]["Page"]["media"]


def fetch_upcoming(anime_format: str | None = None,
                   page: int = 1, per_page: int = 40) -> list[dict]:
    format_filter = _format_gql(anime_format)
    q = f"""
    query($page: Int, $perPage: Int) {{
      Page(page: $page, perPage: $perPage) {{
        media(status: NOT_YET_RELEASED, sort: POPULARITY_DESC, type: ANIME{format_filter}) {{
          {_MEDIA_FIELDS}
        }}
      }}
    }}
    """
    data = _gql(q, {"page": page, "perPage": per_page})
    return data["data"]["Page"]["media"]


def fetch_schedule(day_offset: int = 0) -> list[dict]:
    """
    day_offset: 0 = Monday … 6 = Sunday of current ISO week.
    Returns AiringSchedule entries sorted by airingAt.
    """
    now = time.time()
    # Find Monday 00:00 UTC of current week
    day_of_week = int(time.strftime("%u", time.gmtime(now))) - 1  # 0=Mon
    week_monday = now - day_of_week * 86400 - (now % 86400)
    week_start = int(week_monday + day_offset * 86400)
    week_end   = week_start + 86400

    q = f"""
    query($page: Int, $perPage: Int, $start: Int, $end: Int) {{
      Page(page: $page, perPage: $perPage) {{
        airingSchedules(
          airingAt_greater: $start,
          airingAt_lesser: $end,
          sort: TIME
        ) {{
          {_AIRING_FIELDS}
        }}
      }}
    }}
    """
    data = _gql(q, {"page": 1, "perPage": 50, "start": week_start, "end": week_end})
    return data["data"]["Page"]["airingSchedules"]


# ---------------------------------------------------------------------------
# Image loading helpers
# ---------------------------------------------------------------------------

def _cache_path(url: str) -> str:
    name = hashlib.md5(url.encode()).hexdigest() + ".jpg"
    return os.path.join(THUMB_DIR, name)


def load_image(url: str) -> Optional[QPixmap]:
    if not url:
        return None
    path = _cache_path(url)
    if os.path.exists(path):
        pm = QPixmap(path)
        return pm if not pm.isNull() else None
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
        pm = QPixmap(path)
        return pm if not pm.isNull() else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Worker threads
# ---------------------------------------------------------------------------

class SectionWorker(QThread):
    """Fetches a section's anime list in background."""
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, section: str, genres: list[str] | None = None,
                 anime_format: str | None = None):
        super().__init__()
        self.section      = section
        self.genres        = genres
        self.anime_format  = anime_format

    def run(self):
        try:
            if self.section == "Trending":
                results = fetch_trending(self.genres, self.anime_format)
            elif self.section == "Popular":
                results = fetch_popular(self.genres, self.anime_format)
            elif self.section == "Top Rated":
                results = fetch_top_rated(self.genres, self.anime_format)
            elif self.section == "Airing Now":
                results = fetch_airing(self.anime_format)
            elif self.section == "Upcoming":
                results = fetch_upcoming(self.anime_format)
            else:
                results = []
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class ScheduleWorker(QThread):
    """Fetches schedule for a specific day-of-week offset (0=Mon … 6=Sun)."""
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, day_offset: int):
        super().__init__()
        self.day_offset = day_offset

    def run(self):
        try:
            results = fetch_schedule(self.day_offset)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class ImageWorker(QThread):
    """Downloads a single cover image and emits the QPixmap."""
    finished = pyqtSignal(int, QPixmap)   # (card_index, pixmap)

    def __init__(self, index: int, url: str):
        super().__init__()
        self.index = index
        self.url   = url

    def run(self):
        pm = load_image(self.url)
        if pm:
            self.finished.emit(self.index, pm)


class AllAnimeResolveWorker(QThread):
    """Searches AllAnime by title to resolve the correct streaming ID,
    episode lists, and sub/dub counts.

    Uses fuzzy matching with episode-count tiebreaker and fallback
    English-title search to handle franchise titles correctly.
    """
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, title: str, alt_title: str = "",
                 expected_episodes: int = 0):
        super().__init__()
        self.title = title
        self.alt_title = alt_title
        self.expected_episodes = expected_episodes

    def run(self):
        try:
            from anigui.backend.api import search_anime
            from anigui.utils.matching import best_allanime_match, clean_search_query

            alt_titles = [self.alt_title] if self.alt_title else []

            # First attempt — search with primary title (cleaned)
            clean_title = clean_search_query(self.title)
            results = search_anime(clean_title)
            match = best_allanime_match(
                self.title, results,
                expected_episodes=self.expected_episodes,
                alt_titles=alt_titles,
            )

            # Fallback — retry with English title if primary search failed
            if not match and self.alt_title:
                clean_alt = clean_search_query(self.alt_title)
                if clean_alt.lower() != clean_title.lower():
                    results2 = search_anime(clean_alt)
                    match = best_allanime_match(
                        self.alt_title, results2,
                        expected_episodes=self.expected_episodes,
                        alt_titles=[self.title],
                    )

            if match:
                self.finished.emit(match)
            else:
                self.error.emit(f"No AllAnime match found for '{self.title}'.")
        except Exception as e:
            self.error.emit(str(e))


# ---------------------------------------------------------------------------
# AnimeCard widget — responsive like widgets/card.py & bookmarks view
# ---------------------------------------------------------------------------

class AnimeCard(QFrame):
    """Card widget matching the existing card.py style:
    - Fixed width 180px, no fixed height (grows with content)
    - Cover image 164×246px
    - Title with word-wrap, max 2 lines (~40px)
    - Metadata line
    """
    def __init__(self, anime: dict, on_click: Callable[[dict], None], parent=None):
        super().__init__(parent)
        self.anime    = anime
        self.on_click = on_click

        self.setObjectName("AnimeCard")
        self.setFixedWidth(CARD_FIXED_W)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(CARD_MARGIN, CARD_MARGIN, CARD_MARGIN, CARD_MARGIN)
        layout.setSpacing(6)

        # Cover image — matches widgets/card.py dimensions
        self.cover_label = QLabel(self)
        self.cover_label.setFixedSize(CARD_IMG_W, CARD_IMG_H)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setObjectName("CardCover")
        self.cover_label.setStyleSheet(apply_theme(
            "background-color: #242424; color: #888888;"
        ))

        title_text = (anime.get("title") or {}).get("english") or \
                     (anime.get("title") or {}).get("romaji") or "Unknown"
        self.cover_label.setText(_truncate(title_text, 20))
        self.cover_label.setWordWrap(True)

        # Status badge — overlay on the cover image
        status_raw = anime.get("status") or ""
        STATUS_DISPLAY = {
            "RELEASING": ("Airing", "#16a34a", "#dcfce7"),
            "FINISHED": ("Finished", "#64748b", "#e2e8f0"),
            "NOT_YET_RELEASED": ("Upcoming", "#d97706", "#fef3c7"),
            "CANCELLED": ("Cancelled", "#dc2626", "#fee2e2"),
            "HIATUS": ("Hiatus", "#9333ea", "#f3e8ff"),
        }
        if status_raw in STATUS_DISPLAY:
            display_text, bg_color, text_color = STATUS_DISPLAY[status_raw]
            self.status_badge = QLabel(display_text, self.cover_label)
            self.status_badge.setObjectName("CardStatusBadge")
            self.status_badge.setStyleSheet(
                f"QLabel#CardStatusBadge {{ background-color: {bg_color}; color: {text_color}; "
                f"font-size: 9px; font-weight: bold; padding: 2px 6px; "
                f"border-radius: 3px; }}"
            )
            self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.status_badge.adjustSize()
            self.status_badge.move(4, 4)

        # Title label — word-wrap, max 2 lines height
        title_label = QLabel(_truncate(title_text, 28))
        title_label.setObjectName("CardTitle")
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        title_label.setMaximumHeight(40)

        # Metadata: score + format + episode count
        score   = anime.get("averageScore") or 0
        fmt     = anime.get("format") or ""
        eps     = anime.get("episodes")
        ep_text = f"{eps} eps" if eps else "? eps"
        meta_text = f"★ {score/10:.1f}  •  {fmt}  •  {ep_text}" if score else f"{fmt}  •  {ep_text}"

        meta_label = QLabel(meta_text.strip(" •"))
        meta_label.setObjectName("CardMetadata")

        layout.addWidget(self.cover_label)
        layout.addWidget(title_label)
        layout.addWidget(meta_label)

    def set_cover(self, pixmap: QPixmap):
        scaled = pixmap.scaled(
            self.cover_label.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.cover_label.setText("")
        self.cover_label.setPixmap(scaled)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_click(self.anime)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Schedule row widget
# ---------------------------------------------------------------------------

class ScheduleRow(QFrame):
    def __init__(self, entry: dict, on_click: Callable[[dict], None], parent=None):
        super().__init__(parent)
        self.setObjectName("AnimeCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.setFixedHeight(56)

        media   = entry.get("media") or {}
        episode = entry.get("episode", "?")
        airing  = entry.get("airingAt", 0)

        title_text = (media.get("title") or {}).get("english") or \
                     (media.get("title") or {}).get("romaji") or "Unknown"

        # Format airing time in local time
        try:
            airing_str = time.strftime("%H:%M", time.localtime(airing))
        except Exception:
            airing_str = "--:--"

        hl = QHBoxLayout(self)
        hl.setContentsMargins(12, 6, 12, 6)
        hl.setSpacing(12)

        time_lbl = QLabel(airing_str)
        time_lbl.setObjectName("CardMetadata")
        time_lbl.setFixedWidth(44)
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(apply_theme("color: #2e2e2e;"))

        title_lbl = QLabel(_truncate(title_text, 55))
        title_lbl.setObjectName("CardTitle")
        title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        ep_lbl = QLabel(f"EP {episode}")
        ep_lbl.setObjectName("CardMetadata")
        ep_lbl.setFixedWidth(48)
        ep_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        hl.addWidget(time_lbl)
        hl.addWidget(sep)
        hl.addWidget(title_lbl)
        hl.addWidget(ep_lbl)

        self._media   = media
        self._on_click = on_click

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click(self._media)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Continue Watching widgets
# ---------------------------------------------------------------------------

class ContinueWatchingCard(QFrame):
    """Compact horizontal card for 'Continue Watching' row."""
    def __init__(self, entry: dict, on_click: Callable[[dict], None], parent=None):
        super().__init__(parent)
        self.entry = entry
        self.on_click = on_click
        self.anime_data = None

        self.setObjectName("AnimeCard")
        self.setFixedWidth(240)
        self.setFixedHeight(80)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        hl = QHBoxLayout(self)
        hl.setContentsMargins(8, 8, 8, 8)
        hl.setSpacing(10)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(45, 64)
        self.cover_label.setObjectName("CardCover")
        self.cover_label.setStyleSheet(apply_theme("background-color: #242424;"))
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(self.cover_label)

        info_vl = QVBoxLayout()
        info_vl.setSpacing(2)
        
        self.title_lbl = QLabel(_truncate(entry["anime_title"], 40))
        self.title_lbl.setObjectName("CardTitle")
        self.title_lbl.setWordWrap(True)
        
        self.ep_lbl = QLabel(f"Episode {entry['episode_str']}")
        self.ep_lbl.setObjectName("CardMetadata")
        
        info_vl.addWidget(self.title_lbl)
        info_vl.addWidget(self.ep_lbl)
        info_vl.addStretch()
        hl.addLayout(info_vl)

        # Async metadata fetch
        self._load_meta()

    def _load_meta(self):
        from PyQt6.QtCore import QThreadPool
        worker = MetadataWorker(self.entry["anime_title"])
        worker.signals.finished.connect(self._on_meta_loaded)
        QThreadPool.globalInstance().start(worker)

    def _on_meta_loaded(self, meta: dict):
        if not meta:
            return
        self.anime_data = meta
        # Preserve the AllAnime ID from watch history so the detail view
        # uses the correct anime instead of doing a lossy title re-search.
        if self.entry.get("anime_id"):
            self.anime_data["_allanime_id"] = self.entry["anime_id"]
        cover_url = (meta.get("coverImage") or {}).get("large") or (meta.get("coverImage") or {}).get("medium")
        if cover_url:
            from PyQt6.QtCore import QThreadPool
            worker = ThumbnailWorker(cover_url)
            worker.signals.finished.connect(self._on_image_loaded)
            QThreadPool.globalInstance().start(worker)

    def _on_image_loaded(self, path: str):
        if path and os.path.exists(path):
            pm = QPixmap(path)
            if not pm.isNull():
                self.cover_label.setPixmap(pm.scaled(self.cover_label.size(), 
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
                    Qt.TransformationMode.SmoothTransformation))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.anime_data:
            self.on_click(self.anime_data)
        super().mousePressEvent(event)


class ContinueWatchingRow(QWidget):
    def __init__(self, on_click: Callable[[dict], None], parent=None):
        super().__init__(parent)
        self.on_click = on_click
        self.hide() # Hidden by default
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 10)
        vl.setSpacing(8)

        self.title_lbl = QLabel("Continue Watching")
        self.title_lbl.setObjectName("ViewTitle")
        self.title_lbl.setStyleSheet(apply_theme("font-size: 16px;"))
        vl.addWidget(self.title_lbl)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFixedHeight(100)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setStyleSheet(apply_theme("QScrollArea { border: none; background: transparent; }"))

        self.container = QWidget()
        self.container.setObjectName("GridContainer")
        self.hl = QHBoxLayout(self.container)
        self.hl.setContentsMargins(0, 0, 0, 0)
        self.hl.setSpacing(10)
        self.hl.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.scroll.setWidget(self.container)
        vl.addWidget(self.scroll)

    def refresh(self):
        # Clear
        while self.hl.count():
            item = self.hl.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        history = db.get_recent_unique_watch_history(6)
        if not history:
            self.hide()
            return

        for entry in history:
            card = ContinueWatchingCard(entry, self.on_click, self.container)
            self.hl.addWidget(card)
        
        self.show()


# ---------------------------------------------------------------------------
# Reusable pill-button row (format tabs, section tabs, genre filters)
# ---------------------------------------------------------------------------

class PillRow(QWidget):
    def __init__(self, labels: list[str], on_select: Callable[[str], None],
                 accent: str = "#c084fc", parent=None, cols: int = 0):
        super().__init__(parent)
        self.on_select = on_select
        self.accent    = accent
        self._btns: dict[str, QPushButton] = {}
        self._active: str | None = None

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QGridLayout(self) if cols > 0 else QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        for i, label in enumerate(labels):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFixedHeight(28)
            btn.setMinimumWidth(60)
            if cols > 0:
                btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            else:
                btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda checked, l=label: self._clicked(l))
            self._style_btn(btn, False)
            if cols > 0:
                layout.addWidget(btn, i // cols, i % cols)
            else:
                layout.addWidget(btn)
            self._btns[label] = btn

        if cols <= 0:
            layout.addStretch()
        else:
            for c in range(cols):
                layout.setColumnStretch(c, 1)

    def _style_btn(self, btn: QPushButton, active: bool):
        if active:
            btn.setStyleSheet(apply_theme(
                f"QPushButton {{ background-color: {self.accent}; color: #0f0f0f; "
                f"border: none; border-radius: 14px; padding: 0 12px; font-weight: bold; }}"
            ))
        else:
            btn.setStyleSheet(apply_theme(
                "QPushButton { background-color: #242424; color: #888888; "
                "border: 1px solid #2e2e2e; border-radius: 14px; padding: 0 12px; }"
                "QPushButton:hover { color: #e8e8e8; border-color: #888888; }"
            ))

    def _clicked(self, label: str):
        if self._active == label:
            # Deselect (toggle off — used by genre pills)
            self._set_active(None)
            self.on_select(None)
        else:
            self._set_active(label)
            self.on_select(label)

    def _set_active(self, label: str | None):
        if self._active and self._active in self._btns:
            self._btns[self._active].setChecked(False)
            self._style_btn(self._btns[self._active], False)
        self._active = label
        if label and label in self._btns:
            self._btns[label].setChecked(True)
            self._style_btn(self._btns[label], True)

    def set_active(self, label: str):
        self._set_active(label)

    def active(self) -> str | None:
        return self._active


# ---------------------------------------------------------------------------
# Scrollable grid panel for anime cards — responsive reflow on resize
# ---------------------------------------------------------------------------

class CardGrid(QScrollArea):
    def __init__(self, on_click: Callable[[dict], None], parent=None):
        super().__init__(parent)
        self.on_click   = on_click
        self._workers:  list[ImageWorker] = []
        self._cards:    list[AnimeCard]   = []
        self._media_list: list[dict] = []

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setObjectName("CardGridScroll")
        self.setStyleSheet(apply_theme("QScrollArea { background: transparent; border: none; }"))

        self._container = QWidget()
        self._container.setObjectName("GridContainer")
        self._grid = QGridLayout(self._container)
        self._grid.setHorizontalSpacing(CARD_SPACING_H)
        self._grid.setVerticalSpacing(CARD_SPACING_V)
        self._grid.setContentsMargins(10, 10, 10, 16)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setWidget(self._container)

    def populate(self, media_list: list[dict]):
        # Clear previous cards and workers
        for w in self._workers:
            w.quit()
        self._workers.clear()
        self._cards.clear()
        self._media_list = media_list

        self._clear_grid()

        for i, anime in enumerate(media_list):
            card = AnimeCard(anime, self.on_click, self._container)
            self._cards.append(card)

            # Async image fetch
            cover_url = (anime.get("coverImage") or {}).get("large") or \
                        (anime.get("coverImage") or {}).get("medium") or ""
            if cover_url:
                worker = ImageWorker(i, cover_url)
                worker.finished.connect(self._on_image)
                self._workers.append(worker)
                worker.start()

        self._rearrange_grid()

    def _on_image(self, index: int, pixmap: QPixmap):
        if index < len(self._cards):
            self._cards[index].set_cover(pixmap)

    def show_status(self, msg: str):
        self._clear_grid()
        self._cards.clear()
        lbl = QLabel(msg)
        lbl.setObjectName("LoadingLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grid.addWidget(lbl, 0, 0)

    def _clear_grid(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _rearrange_grid(self):
        """Reflow cards into a dynamic number of columns based on scroll area width."""
        if not self._cards:
            return

        width = self.viewport().width()
        cols = max(1, width // (CARD_FIXED_W + CARD_SPACING_H))

        for i, card in enumerate(self._cards):
            row = i // cols
            col = i % cols
            self._grid.addWidget(card, row, col)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rearrange_grid()


# ---------------------------------------------------------------------------
# Schedule panel
# ---------------------------------------------------------------------------

class SchedulePanel(QWidget):
    def __init__(self, on_click: Callable[[dict], None], parent=None):
        super().__init__(parent)
        self.on_click = on_click
        self._worker: ScheduleWorker | None = None

        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(8)

        # Day picker
        today_offset = (int(time.strftime("%u")) - 1) % 7   # 0=Mon
        self._day_row = PillRow(DAYS, self._on_day_select, parent=self)
        self._day_row.set_active(DAYS[today_offset])
        vl.addWidget(self._day_row)

        # List area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setObjectName("CardGridScroll")
        self._scroll.setStyleSheet(apply_theme("QScrollArea { background: transparent; border: none; }"))

        self._list_widget = QWidget()
        self._list_widget.setObjectName("GridContainer")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 16)
        self._list_layout.setSpacing(6)
        self._scroll.setWidget(self._list_widget)
        vl.addWidget(self._scroll)

        # Load initial day
        self._load_day(today_offset)

    def _on_day_select(self, day_name: str | None):
        if day_name is None:
            return
        offset = DAYS.index(day_name)
        self._load_day(offset)

    def _load_day(self, offset: int):
        self._clear_list()
        self._set_status("Loading schedule…")

        if self._worker and self._worker.isRunning():
            self._worker.quit()

        self._worker = ScheduleWorker(offset)
        self._worker.finished.connect(self._on_schedule)
        self._worker.error.connect(lambda e: self._set_status(f"Error: {e}"))
        self._worker.start()

    def _on_schedule(self, entries: list[dict]):
        self._clear_list()
        if not entries:
            self._set_status("No scheduled airings found for this day.")
            return
        for entry in sorted(entries, key=lambda x: x.get("airingAt", 0)):
            row = ScheduleRow(entry, self.on_click, self._list_widget)
            self._list_layout.addWidget(row)
        self._list_layout.addStretch()

    def _set_status(self, msg: str):
        self._clear_list()
        lbl = QLabel(msg)
        lbl.setObjectName("LoadingLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._list_layout.addWidget(lbl)

    def _clear_list(self):
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


# ---------------------------------------------------------------------------
# HomeView — top-level widget
# ---------------------------------------------------------------------------

class HomeView(QWidget):
    """
    Drop-in replacement for the original HomeView.
    Signature preserved: HomeView(on_card_clicked=..., parent=...)
    """

    def __init__(self, on_card_clicked: Callable[[dict], None], parent=None):
        super().__init__(parent)
        self.on_card_clicked = on_card_clicked
        self._section_worker: SectionWorker | None = None
        self._active_format   = "TV Series"
        self._active_section  = "Trending"
        self._active_genre: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # --- Unified Control Bar (Dropdown + Tabs) ---
        self._control_bar = QHBoxLayout()
        self._control_bar.setContentsMargins(0, 0, 0, 0)
        self._control_bar.setSpacing(6)
        self._control_bar.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        # --- Row 1: Media format dropdown ---
        # Added a horizontal layout so the dropdown menu does not stretch to the whole screen
        self._format_layout = QHBoxLayout()
        self._format_layout.setContentsMargins(0, 0, 0, 0)
        # Instantiate the ComboBox
        self._format_combo = QComboBox()
        self._format_combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._format_combo.setObjectName("FormatCombo")
        self._format_combo.addItems(FORMATS)
        self._format_combo.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # Connect the Event Listener (Signal -> Slot)
        self._format_combo.currentTextChanged.connect(self._on_format_select)
        # Add to the UI Tree
        self._format_layout.addWidget(self._format_combo)
        self._control_bar.addLayout(self._format_layout)

        # --- Row 2: Section tabs (rebuilt dynamically when format changes) ---
        self._section_container = QWidget(self)
        self._section_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._section_layout = QHBoxLayout(self._section_container)
        self._section_layout.setContentsMargins(0, 0, 0, 0) 
        self._section_tabs: PillRow | None = None
        self._build_section_tabs(FORMAT_SECTIONS["TV Series"])
        self._control_bar.addWidget(self._section_container)

        # push to the left
        self._control_bar.addStretch()
        root.addLayout(self._control_bar)

        # --- row 2 ---
        self._genre_pills = PillRow(GENRES, self._on_genre_select, accent="#a855f7", parent=self, cols=8)
        self._genre_pills.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._genre_pills)

        # Continue-watching row (hidden when empty)
        self._continue_watching = ContinueWatchingRow(on_click=self._handle_card_click, parent=self)
        root.addWidget(self._continue_watching)


        # --- Content stack: card grid vs schedule panel ---
        self._stack = QStackedWidget(self)

        self._card_grid = CardGrid(on_click=self._handle_card_click, parent=self)
        self._schedule  = SchedulePanel(on_click=self._handle_card_click, parent=self)

        self._stack.addWidget(self._card_grid)   # index 0
        self._stack.addWidget(self._schedule)    # index 1

        root.addWidget(self._stack)

        # Load default section on first show
        QTimer.singleShot(0, self._initial_load)

    def _initial_load(self):
        self.refresh_continue_watching()
        self._load_section("Trending")

    def refresh_continue_watching(self):
        self._continue_watching.refresh()

    # ------------------------------------------------------------------
    # Section tab management
    # ------------------------------------------------------------------

    def _build_section_tabs(self, sections: list[str]):
        """Destroy the old section PillRow and create a new one with the
        given list of section labels."""
        if self._section_tabs is not None:
            self._section_layout.removeWidget(self._section_tabs)
            self._section_tabs.deleteLater()

        self._section_tabs = PillRow(
            sections,
            self._on_section_select,
            accent="#c084fc",
            parent=self._section_container,
        )
        self._section_tabs.set_active(sections[0])
        self._section_layout.addWidget(self._section_tabs)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _handle_card_click(self, anime_raw: dict):
        """Resolve the AllAnime streaming ID for this anime, then open
        the detail dialog with merged AniList + AllAnime data."""
        app_dict = _anilist_to_app_dict(anime_raw)

        # If we already have an AllAnime ID (e.g., from Continue Watching
        # watch history), use it directly instead of doing a title-based
        # re-search that may resolve to the wrong anime in a franchise.
        existing_allanime_id = anime_raw.get("_allanime_id")
        if existing_allanime_id:
            app_dict["id"] = existing_allanime_id
            self.on_card_clicked(app_dict)
            return

        # Prefer romaji title for AllAnime search (AllAnime indexes by romaji)
        title_obj = anime_raw.get("title") or {}
        romaji = title_obj.get("romaji") or ""
        english = title_obj.get("english") or ""
        search_title = romaji or english or app_dict.get("name") or "Unknown"
        alt_title = english if (english and english.lower() != search_title.lower()) else ""
        expected_eps = app_dict.get("sub_count", 0) or anime_raw.get("episodes", 0) or 0

        # Show busy cursor while resolving
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))

        # Kill previous resolver if still running
        if hasattr(self, '_resolve_worker') and self._resolve_worker and self._resolve_worker.isRunning():
            self._resolve_worker.quit()

        self._resolve_worker = AllAnimeResolveWorker(
            search_title, alt_title=alt_title, expected_episodes=expected_eps
        )

        def on_resolved(allanime_match: dict):
            QApplication.restoreOverrideCursor()
            app_dict["id"] = allanime_match.get("id", "")
            app_dict["sub_count"] = allanime_match.get("sub_count", app_dict.get("sub_count", 0))
            app_dict["dub_count"] = allanime_match.get("dub_count", 0)
            if "sub_episodes" in allanime_match:
                app_dict["sub_episodes"] = allanime_match["sub_episodes"]
            if "dub_episodes" in allanime_match:
                app_dict["dub_episodes"] = allanime_match["dub_episodes"]
            self.on_card_clicked(app_dict)

        def on_error(err: str):
            QApplication.restoreOverrideCursor()
            app_dict["id"] = ""
            self.on_card_clicked(app_dict)

        self._resolve_worker.finished.connect(on_resolved)
        self._resolve_worker.error.connect(on_error)
        self._resolve_worker.start()

    def _on_format_select(self, fmt: str | None):
        """Handle format (Row 1) change — rebuild section tabs, reset
        genre, and reload data."""
        if not fmt or fmt == self._active_format:
            if self._active_format:
                self._format_tabs.set_active(self._active_format)
            return

        self._active_format = fmt
        self._active_genre  = None
        self._genre_pills._set_active(None)

        # Rebuild section tabs for this format
        available = FORMAT_SECTIONS.get(fmt, FORMATS)
        self._build_section_tabs(available)
        self._active_section = available[0]

        # Show genre strip only if current section supports it
        self._genre_pills.setVisible(self._active_section in GENRE_SECTIONS)

        # Show card grid (not schedule)
        self._stack.setCurrentIndex(0)
        self._load_section(self._active_section)

    def _on_section_select(self, section: str | None):
        if not section or section == self._active_section:
            if self._active_section:
                self._section_tabs.set_active(self._active_section)
            return

        self._active_section = section
        self._active_genre   = None
        self._genre_pills._set_active(None)

        # Show/hide genre strip — only visible for Trending/Popular/Top Rated
        self._genre_pills.setVisible(section in GENRE_SECTIONS)

        if section == "Schedule":
            self._stack.setCurrentIndex(1)
        else:
            self._stack.setCurrentIndex(0)
            self._load_section(section)

    def _on_genre_select(self, genre: str | None):
        if genre == self._active_genre:
            return
        self._active_genre = genre
        self._load_section(self._active_section)

    def _load_section(self, section: str):
        self._card_grid.show_status(f"Loading {section}…")

        if self._section_worker and self._section_worker.isRunning():
            self._section_worker.quit()

        genres = [self._active_genre] if self._active_genre else None
        anime_format = FORMAT_MAP.get(self._active_format)
        self._section_worker = SectionWorker(section, genres, anime_format)
        self._section_worker.finished.connect(self._on_section_loaded)
        self._section_worker.error.connect(
            lambda e: self._card_grid.show_status(f"Error loading {section}: {e}")
        )
        self._section_worker.start()

    def _on_section_loaded(self, media_list: list[dict]):
        if not media_list:
            self._card_grid.show_status("No results found.")
            return
        self._card_grid.populate(media_list)

    # ------------------------------------------------------------------
    # Dynamic layout — keep dropdown aligned with genre column on resize
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_dropdown_width()

    def _sync_dropdown_width(self):
        """Dynamically match the dropdown width to the first genre column
        so the control bar stays aligned with the genre grid below."""
        btns = list(self._genre_pills._btns.values())
        if not btns or btns[0].width() <= 0:
            return
        target_total = btns[0].width()
        # QSS width = content area; subtract padding (10+10) and border (1+1)
        css_w = max(30, target_total - 22)
        if getattr(self, '_last_combo_css_w', None) != css_w:
            self._last_combo_css_w = css_w
            self._format_combo.setStyleSheet(
                f"min-width: {css_w}px; max-width: {css_w}px;"
            )
