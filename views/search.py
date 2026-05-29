"""
views/search.py  —  AniGUI Search View
 
On first open, displays the top 40 all-time ranked anime from AniList
as a default grid (same data source as HomeView's "Top Rated" section).
 
When the user types, the grid switches to AllAnime search results.
Clearing the search input returns to the default top-ranked grid.
 
Card click behaviour differs by result source:
  • Default (AniList)  — rich metadata already present; AllAnime ID is
                         resolved at click time via AllAnimeResolveWorker,
                         same pattern as HomeView.
  • Search  (AllAnime) — AllAnime ID already present; metadata is fetched
                         lazily by AnimeCard as usual.
"""

from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QScrollArea, QGridLayout, QLabel, QApplication
from PyQt6.QtCore import Qt, QTimer, QThreadPool, QThread, pyqtSignal
from PyQt6.QtGui import QCursor
from anigui.backend.worker import SearchWorker, DefaultResultsWorker
from anigui.backend.allanime import search_anime as _allanime_search
from anigui.widgets.card import AnimeCard
from anigui.utils.theme import apply_theme
from anigui.utils.matching import best_anilist_match

class _AllAnimeResolveWorker(QThread):
    """Searches AllAnime by title and returns the best-matching result dict."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, title: str):
        super().__init__()
        self.title = title

    def run(self):
        try:
            results = _allanime_search(self.title)
            match = best_anilist_match(self.title, results)
            self.finished.emit(match if match else {})
        except Exception as e:
            self.error.emit(str(e))

class SearchView(QWidget):
    """View allowing user to search for anime on AllAnime.

    Uses a debounced QTimer to start searches after typing stops.
    """

    _MODE_DEFAULT = "default"  # Shows top-ranked anime from AniList
    _MODE_SEARCH  = "search"   # Shows search results from AllAnime

    def __init__(self, on_card_clicked, parent=None):
        super().__init__(parent)
        self.on_card_clicked = on_card_clicked
        self._cards: list[AnimeCard] = []
        self._default_cache: list[dict] = []  # Cache for default top-ranked results
        self._current_mode: str = self._MODE_DEFAULT
        self.resolve_worker: _AllAnimeResolveWorker | None = None
        
        # Debounce timer
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._perform_search)
        
        # Root Layout
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)
        
        # Search Bar Header
        search_bar_layout = QHBoxLayout()
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search anime by name...")
        self.search_input.setObjectName("SearchInput")
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.returnPressed.connect(self._perform_search_immediately)
        search_bar_layout.addWidget(self.search_input)
        root.addLayout(search_bar_layout)
        
        # Status Label (Loading/Error/No Results)
        self.status_label = QLabel("", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setObjectName("SearchStatus")
        self.status_label.hide()
        root.addWidget(self.status_label)
        
        # Scroll Area for the grid
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_area.setObjectName("ViewScrollArea")
        
        # Container widget for grid
        self.grid_container = QWidget()
        self.grid_container.setObjectName("GridContainer")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setHorizontalSpacing(15)
        self.grid_layout.setVerticalSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.grid_container)
        root.addWidget(self.scroll_area)

        # Load default grid after window shows
        QTimer.singleShot(0, self._load_default)

    # ------------------------------------------------------------------
    # Default grid — top 40 ranked (AniList)
    # ------------------------------------------------------------------
 
    def _load_default(self):
        """Populate the grid with top-ranked anime.
        Uses in-memory cache on repeat calls so no extra network hit."""
        if self._default_cache:
            self._render_default(self._default_cache)
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
        self._render_default(media_list)
 
    def _render_default(self, media_list: list[dict]):
        """Render AniList media dicts as AnimeCards."""
        self._current_mode = self._MODE_DEFAULT
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
                # No AllAnime 'id' yet — filled in at click time
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
            card.clicked.connect(self._handle_default_card_click)
            self._cards.append(card)
 
        self._rearrange_grid()
 
    def _handle_default_card_click(self, anime_data: dict):
        """Resolve AllAnime streaming ID then open the detail dialog."""
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
 
        if self.resolve_worker and self.resolve_worker.isRunning():
            self.resolve_worker.quit()
 
        title_obj    = anime_data.get("title") or {}
        search_title = (
            title_obj.get("romaji")
            or title_obj.get("english")
            or anime_data.get("name")
            or "Unknown"
        )
 
        self.resolve_worker = _AllAnimeResolveWorker(search_title)
 
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
 
        def _on_error(_err: str):
            QApplication.restoreOverrideCursor()
            self.on_card_clicked(dict(anime_data))
 
        self.resolve_worker.finished.connect(_on_resolved)
        self.resolve_worker.error.connect(_on_error)
        self.resolve_worker.start()


    def _on_text_changed(self, text: str):
        """Handle text changes in the search input. Resets to default grid if input is cleared."""
        if not text.strip():
            self.timer.stop()
            if self._current_mode != self._MODE_DEFAULT:
                self._load_default()
            return
        # Reset 500ms debounce timer on keystroke
        self.timer.start(500)

    def _perform_search_immediately(self):
        self.timer.stop()
        self._perform_search()

    def _perform_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
            
        self._current_mode = self._MODE_SEARCH
        self._show_status("Loading...")
        
        worker = SearchWorker(query)
        worker.signals.finished.connect(self._on_search_finished)
        worker.signals.error.connect(lambda e: self._show_status(f"Error: {e}"))
        QThreadPool.globalInstance().start(worker)

    def _on_search_finished(self, results: list[dict]):
        if not results:
            self._show_status("No results found.")
            return
        
        # Clear existing grid contents and render new results
        self.status_label.hide()
        self.scroll_area.show()
        self._clear_grid()
        self._cards.clear()
        
        # Render cards
        for item in results:
            card = AnimeCard(item, self)
            card.clicked.connect(self.on_card_clicked)
            self._cards.append(card)
            
        self._rearrange_grid()

    def _show_status(self, msg: str):
        self._clear_grid()
        self._cards.clear()
        self.scroll_area.hide()
        self.status_label.setText(msg)
        self.status_label.show()

    def _clear_grid(self):
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

    def _rearrange_grid(self):
        if not self._cards:
            return
            
        width = self.scroll_area.width()
        cols = max(1, width // 200)
        
        for i, card in enumerate(self._cards):
            self.grid_layout.addWidget(card, i // cols, i % cols)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rearrange_grid()

    @property
    def cards(self) -> list[AnimeCard]:
        return self._cards