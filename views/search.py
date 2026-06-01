"""
views/search.py  —  AniGUI Search View
 
Default state   : top 40 ranked anime from AniList (no query, no filters)
With filters    : AniList filtered search via search_anilist()
With text only  : AllAnime text search via SearchWorker (original behaviour)
With text+filter: AniList filtered search with query string
 
Filter bar (visible always):
  Genre    — multi-select GenreDropdown
  Season   — QComboBox  (Winter / Spring / Summer / Fall)
  Year     — QComboBox  (2000 → current year)
  Format   — QComboBox  (TV / Movie / OVA / ONA / Special)
  Status   — QComboBox  (Releasing / Finished / Not Yet Released)
  [ Clear Filters ] button
 
Card click:
  AniList-sourced cards  → _AllAnimeResolveWorker merges streaming ID
  AllAnime-sourced cards → ID already present, opens detail directly
"""


from __future__ import annotations
import datetime
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QScrollArea, QGridLayout, QLabel, QApplication, QComboBox, QPushButton, QFrame
from PyQt6.QtCore import Qt, QTimer, QThreadPool, QThread, pyqtSignal
from PyQt6.QtGui import QCursor
from anigui.backend.worker import SearchWorker, DefaultResultsWorker, FilteredSearchWorker
from anigui.backend.allanime import search_anime as _allanime_search
from anigui.widgets.card import AnimeCard
from anigui.widgets.genre_dropdown import GenreDropdown
from anigui.utils.theme import apply_theme
from anigui.utils.matching import best_allanime_match

# Filter option map

SEASON_OPTIONS  = {"Any Season": None, "Winter": "WINTER", "Spring": "SPRING",
                   "Summer": "SUMMER", "Fall": "FALL"}
FORMAT_OPTIONS  = {"Any Format": None, "TV Series": "TV", "Movie": "MOVIE",
                   "OVA": "OVA", "ONA": "ONA", "Special": "SPECIAL"}
STATUS_OPTIONS  = {"Any Status": None, "Releasing": "RELEASING",
                   "Finished": "FINISHED", "Not Yet Released": "NOT_YET_RELEASED"}
 
_CURRENT_YEAR = datetime.datetime.now().year
YEAR_OPTIONS   = {"Any Year": None, **{str(y): y for y in range(_CURRENT_YEAR, 1999, -1)}}

class _AllAnimeResolveWorker(QThread):
    """Searches AllAnime by title and returns the best-matching result dict.

    Supports fallback search: if the primary (romaji) title returns no
    confident match, retries with the alt (English) title.  Passes episode
    count context to the matcher so franchise entries can be disambiguated.
    """
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, title: str):
        super().__init__()
        self.title = title

    def run(self):
        try:
            results = _allanime_search(self.title)
            match = best_allanime_match(self.title, results)

            self.finished.emit(match if match else {})
        except Exception as e:
            self.error.emit(str(e))

class SearchView(QWidget):
    """View allowing user to search for anime on AllAnime.

    Uses a debounced QTimer to start searches after typing stops.
    """

    _MODE_DEFAULT = "default"  # Shows top-ranked anime from AniList
    _MODE_SEARCH  = "search"   # Shows search results from AllAnime
    _MODE_FILTERED = "filtered" # Shows AniList results matching filters + query

    def __init__(self, on_card_clicked, parent=None):
        super().__init__(parent)
        self.on_card_clicked = on_card_clicked
 
        self._cards:         list[AnimeCard] = []
        self._default_cache: list[dict]      = []
        self._current_mode:  str             = self._MODE_DEFAULT
        self._resolve_worker: _AllAnimeResolveWorker | None = None
 
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_debounce_fire)
 
        # Root layout
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
 
        # Search bar
        search_row = QHBoxLayout()
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search anime by name…")
        self.search_input.setObjectName("SearchInput")
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.returnPressed.connect(self._on_return_pressed)
        search_row.addWidget(self.search_input)
        root.addLayout(search_row)
 
        # Filter bar
        self.filter_bar = self._build_filter_bar()
        root.addWidget(self.filter_bar)
 
        # Divider
        divider = QFrame(self)
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(apply_theme("color: #2e2e2e;"))
        root.addWidget(divider)
 
        # Status label
        self.status_label = QLabel("", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setObjectName("SearchStatus")
        self.status_label.hide()
        root.addWidget(self.status_label)
 
        # Results grid
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_area.setObjectName("ViewScrollArea")
 
        self.grid_container = QWidget()
        self.grid_container.setObjectName("GridContainer")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setHorizontalSpacing(15)
        self.grid_layout.setVerticalSpacing(15)
        self.grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
 
        self.scroll_area.setWidget(self.grid_container)
        root.addWidget(self.scroll_area)
 
        QTimer.singleShot(0, self._load_default)
 
    # Filter bar builder
    def _build_filter_bar(self) -> QWidget:
        bar = QWidget(self)
        bar.setObjectName("SearchFilterBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
 
        # Genre multi-select
        self._genre_dropdown = GenreDropdown(bar)
        self._genre_dropdown.genres_changed.connect(self._on_filter_changed)
        layout.addWidget(self._genre_dropdown)
 
        # Season
        self._season_combo = self._make_combo(list(SEASON_OPTIONS.keys()), bar)
        layout.addWidget(self._season_combo)
 
        # Year
        self._year_combo = self._make_combo(list(YEAR_OPTIONS.keys()), bar)
        layout.addWidget(self._year_combo)
 
        # Format
        self._format_combo = self._make_combo(list(FORMAT_OPTIONS.keys()), bar)
        layout.addWidget(self._format_combo)
 
        # Status
        self._status_combo = self._make_combo(list(STATUS_OPTIONS.keys()), bar)
        layout.addWidget(self._status_combo)
 
        # Clear filters button
        self._clear_btn = QPushButton("Clear Filters", bar)
        self._clear_btn.setObjectName("BookmarkButton")
        self._clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._clear_btn.setFixedHeight(32)
        self._clear_btn.clicked.connect(self._on_clear_filters)
        layout.addWidget(self._clear_btn)
 
        layout.addStretch()
        return bar
 
    def _make_combo(self, items: list[str], parent: QWidget) -> QComboBox:
        cb = QComboBox(parent)
        cb.setObjectName("FormatCombo")
        cb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cb.setFixedHeight(32)
        cb.setMinimumWidth(130)
        cb.addItems(items)
        cb.currentTextChanged.connect(self._on_filter_changed)
        return cb
 
    # Filter state helpers
    def _active_filters(self) -> dict:
        """Return a dict of currently set filter values (None = not set)."""
        return {
            "genres": self._genre_dropdown.selected_genres() or None,
            "season": SEASON_OPTIONS[self._season_combo.currentText()],
            "year":   YEAR_OPTIONS[self._year_combo.currentText()],
            "format": FORMAT_OPTIONS[self._format_combo.currentText()],
            "status": STATUS_OPTIONS[self._status_combo.currentText()],
        }
 
    def _has_active_filters(self) -> bool:
        f = self._active_filters()
        return any(v is not None for v in f.values())
 
    def _clear_filter_controls(self, silent: bool = True):
        """Reset all filter controls to their default 'Any' state."""
        widgets = [
            self._season_combo, self._year_combo,
            self._format_combo, self._status_combo,
        ]
        for w in widgets:
            if silent:
                w.blockSignals(True)
            w.setCurrentIndex(0)
            if silent:
                w.blockSignals(False)
        self._genre_dropdown.clear_selection()
    
    # Search bar events
    def _on_text_changed(self, text: str):
        if not text.strip() and not self._has_active_filters():
            self._timer.stop()
            if self._current_mode != self._MODE_DEFAULT:
                self._load_default()
            return
        self._timer.start(500)
 
    def _on_return_pressed(self):
        self._timer.stop()
        self._on_debounce_fire()
 
    def _on_debounce_fire(self):
        """Decide which worker to use based on query + filter state."""
        query   = self.search_input.text().strip()
        filters = self._active_filters()
        has_filters = any(v is not None for v in filters.values())
 
        if not query and not has_filters:
            self._load_default()
            return
 
        if has_filters:
            # AniList filtered search (with or without text query)
            self._run_filtered_search(query or None, filters)
        else:
            # Text-only: use AllAnime search (original behaviour)
            self._run_allanime_search(query)
 
    # Filter events
    def _on_filter_changed(self, *_):
        """Any filter dropdown changed — debounce then re-fetch."""
        self._timer.start(300)
 
    def _on_clear_filters(self):
        self._clear_filter_controls(silent=True)
        query = self.search_input.text().strip()
        if query:
            self._run_allanime_search(query)
        else:
            self._load_default()

    # Default grid — top 40 ranked (AniList)
    def _load_default(self):
        if self._default_cache:
            self._render_anilist_cards(self._default_cache)
            self._current_mode = self._MODE_DEFAULT
            return
        self._show_status("Loading top ranked anime…")
        worker = DefaultResultsWorker(per_page=40)
        worker.signals.finished.connect(self._on_default_loaded)
        worker.signals.error.connect(
            lambda e: self._show_status(f"Failed to load defaults: {e}")
        )
        QThreadPool.globalInstance().start(worker)
 
    def _on_default_loaded(self, media_list: list[dict]):
        self._default_cache = media_list
        self._current_mode  = self._MODE_DEFAULT
        self._render_anilist_cards(media_list)
 
    # Filtered search (AniList)
    def _run_filtered_search(self, query: str | None, filters: dict):
        self._current_mode = self._MODE_FILTERED
        self._show_status("Loading…")
        worker = FilteredSearchWorker(
            query=query,
            genres=filters.get("genres"),
            season=filters.get("season"),
            year=filters.get("year"),
            fmt=filters.get("format"),
            status=filters.get("status"),
        )
        worker.signals.finished.connect(self._on_filtered_results)
        worker.signals.error.connect(lambda e: self._show_status(f"Error: {e}"))
        QThreadPool.globalInstance().start(worker)
 
    def _on_filtered_results(self, media_list: list[dict]):
        if not media_list:
            self._show_status("No results found for the selected filters.")
            return
        self._render_anilist_cards(media_list)
 
    # AllAnime text search (no filters active) 
    def _run_allanime_search(self, query: str):
        self._current_mode = self._MODE_SEARCH
        self._show_status("Loading…")
        worker = SearchWorker(query)
        worker.signals.finished.connect(self._on_allanime_results)
        worker.signals.error.connect(lambda e: self._show_status(f"Error: {e}"))
        QThreadPool.globalInstance().start(worker)
 
    def _on_allanime_results(self, results: list[dict]):
        if not results:
            self._show_status("No results found.")
            return
        self.status_label.hide()
        self.scroll_area.show()
        self._clear_grid()
        self._cards.clear()
        for item in results:
            card = AnimeCard(item, self)
            card.clicked.connect(self.on_card_clicked)  # AllAnime ID already present
            self._cards.append(card)
        self._rearrange_grid()
 
    # AniList card rendering + click handling 
    def _render_anilist_cards(self, media_list: list[dict]):
        """Render AniList media dicts as AnimeCards."""
        self.status_label.hide()
        self.scroll_area.show()
        self._clear_grid()
        self._cards.clear()
 
        for media in media_list:
            title_obj = media.get("title") or {}
            romaji    = title_obj.get("romaji") or ""
            english   = title_obj.get("english") or ""
            name      = english or romaji or "Unknown Title"
            cover     = media.get("coverImage") or {}
            cover_url = cover.get("extraLarge") or cover.get("large") or ""
 
            anime_dict = {
                "name":           name,
                "english_name":   english if (english and english.lower() != romaji.lower()) else "",
                "synopsis":       media.get("description") or "",
                "genres":         media.get("genres") or [],
                "score":          media.get("averageScore") or 0,
                "sub_count":      media.get("episodes") or 0,
                "dub_count":      0,
                "thumbnail_url":  cover_url,
                "format":         media.get("format") or "",
                "status":         media.get("status") or "",
                "coverImage":     cover,
                "title":          title_obj,
                "_anilist_media": media,
            }
 
            card = AnimeCard(anime_dict, self)
            card.clicked.connect(self._handle_anilist_card_click)
            self._cards.append(card)
 
        self._rearrange_grid()
 
    def _handle_anilist_card_click(self, anime_data: dict):
        """Resolve AllAnime streaming ID then open detail dialog."""
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
 
        if self._resolve_worker and self._resolve_worker.isRunning():
            self._resolve_worker.quit()
 
        title_obj    = anime_data.get("title") or {}
        search_title = (
            title_obj.get("romaji")
            or title_obj.get("english")
            or anime_data.get("name")
            or "Unknown"
        )
 
        self._resolve_worker = _AllAnimeResolveWorker(search_title)
 
        def _on_resolved(match: dict):
            QApplication.restoreOverrideCursor()
            merged = dict(anime_data)
            merged["id"]        = match.get("id", "")
            merged["sub_count"] = match.get("sub_count", anime_data.get("sub_count", 0))
            merged["dub_count"] = match.get("dub_count", 0)
            if "sub_episodes" in match:
                merged["sub_episodes"] = match["sub_episodes"]
            if "dub_episodes" in match:
                merged["dub_episodes"] = match["dub_episodes"]
            self.on_card_clicked(merged)
 
        def _on_error(_: str):
            QApplication.restoreOverrideCursor()
            self.on_card_clicked(dict(anime_data))
 
        self._resolve_worker.finished.connect(_on_resolved)
        self._resolve_worker.error.connect(_on_error)
        self._resolve_worker.start()
 
    # Shared helpers
    def _show_status(self, msg: str):
        self._clear_grid()
        self._cards.clear()
        self.scroll_area.hide()
        self.status_label.setText(msg)
        self.status_label.show()
 
    def _clear_grid(self):
        for i in reversed(range(self.grid_layout.count())):
            w = self.grid_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
 
    def _rearrange_grid(self):
        if not self._cards:
            return
        cols = max(1, self.scroll_area.width() // 200)
        for i, card in enumerate(self._cards):
            self.grid_layout.addWidget(card, i // cols, i % cols)
 
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rearrange_grid()
 
    @property
    def cards(self) -> list[AnimeCard]:
        return self._cards