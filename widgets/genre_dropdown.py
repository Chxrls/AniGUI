"""
widgets/genre_dropdown.py  —  AniGUI Multi-Select Genre Dropdown

A QPushButton that when clicked opens a floating popup panel containing
a scrollable grid of QCheckBox items — one per AniList genre.

Emits `genres_changed(list[str])` whenever the selection changes.

Usage
-----
    dropdown = GenreDropdown(parent=self)
    dropdown.genres_changed.connect(self._on_genres_changed)
    layout.addWidget(dropdown)
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QCheckBox,
    QPushButton, QFrame, QScrollArea, QApplication,
)

from anigui.utils.theme import apply_theme

# Full AniList canonical genre list
ANILIST_GENRES = [
    "Action",       "Adventure",    "Comedy",       "Drama",
    "Ecchi",        "Fantasy",      "Horror",       "Mahou Shoujo",
    "Mecha",        "Music",        "Mystery",      "Psychological",
    "Romance",      "Sci-Fi",       "Slice of Life","Sports",
    "Supernatural", "Thriller",
]

# Number of columns in the checkbox grid
_COLS = 3


class GenreDropdown(QWidget):
    """Multi-select genre dropdown.

    Signals
    -------
    genres_changed : list[str]
        Emitted with the current list of selected genre strings whenever
        a checkbox is toggled.
    """

    genres_changed = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._selected: list[str] = []
        self._popup: QFrame | None = None
        self._checkboxes: dict[str, QCheckBox] = {}

        self._btn = QPushButton("Select Genre ▾", self)
        self._btn.setObjectName("FormatCombo")
        self._btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn.setFixedHeight(32)
        self._btn.setMinimumWidth(150)
        self._btn.clicked.connect(self._toggle_popup)
        self._btn.setStyleSheet(apply_theme("""
            QPushButton#FormatCombo {
                background-color: #1a1a1a;
                color: #888888;
                border: 1px solid #2e2e2e;
                border-radius: 6px;
                padding: 0 10px;
                text-align: left;
                font-size: 13px;
            }
            QPushButton#FormatCombo:hover {
                border-color: #888888;
                color: #e8e8e8;
            }
        """))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._btn)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def selected_genres(self) -> list[str]:
        """Return the current list of selected genre strings."""
        return list(self._selected)

    def clear_selection(self) -> None:
        """Deselect all genres without emitting genres_changed."""
        self._selected.clear()
        for cb in self._checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        self._update_button_label()

    # ------------------------------------------------------------------
    # Popup creation & toggle
    # ------------------------------------------------------------------

    def _toggle_popup(self):
        if self._popup and self._popup.isVisible():
            self._popup.hide()
            return
        self._show_popup()

    def _show_popup(self):
        # Build popup lazily on first open
        if self._popup is None:
            self._build_popup()

        # Position popup below the button, anchored to top-left
        btn_global = self._btn.mapToGlobal(QPoint(0, self._btn.height()))
        self._popup.move(btn_global)
        self._popup.show()
        self._popup.raise_()

    def _build_popup(self):
        # Floating frame — parented to the top-level window so it overlays
        top = self.window()
        self._popup = QFrame(top, Qt.WindowType.Popup)
        self._popup.setObjectName("GenrePopup")
        self._popup.setFrameShape(QFrame.Shape.StyledPanel)
        self._popup.setStyleSheet(apply_theme("""
            QFrame#GenrePopup {
                background-color: #1a1a1a;
                border: 1px solid #2e2e2e;
                border-radius: 8px;
            }
            QCheckBox {
                color: #e8e8e8;
                font-size: 12px;
                padding: 3px 6px;
                spacing: 6px;
            }
            QCheckBox:hover {
                color: #c084fc;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #2e2e2e;
                border-radius: 3px;
                background-color: #242424;
            }
            QCheckBox::indicator:checked {
                background-color: #c084fc;
                border-color: #c084fc;
            }
        """))

        outer = QVBoxLayout(self._popup)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)

        # Clear button at the top
        clear_btn = QPushButton("Clear all", self._popup)
        clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        clear_btn.setFixedHeight(24)
        clear_btn.setStyleSheet(apply_theme("""
            QPushButton {
                background: transparent;
                color: #888888;
                border: none;
                font-size: 11px;
                text-align: left;
                padding-left: 4px;
            }
            QPushButton:hover { color: #c084fc; }
        """))
        clear_btn.clicked.connect(self._on_clear)
        outer.addWidget(clear_btn)

        # Scrollable checkbox grid
        scroll = QScrollArea(self._popup)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setFixedSize(400, 260)
        scroll.setStyleSheet("background: transparent;")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        grid = QGridLayout(inner)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(2)

        for i, genre in enumerate(ANILIST_GENRES):
            cb = QCheckBox(genre, inner)
            cb.setChecked(genre in self._selected)
            cb.toggled.connect(lambda checked, g=genre: self._on_toggle(g, checked))
            grid.addWidget(cb, i // _COLS, i % _COLS)
            self._checkboxes[genre] = cb

        scroll.setWidget(inner)
        outer.addWidget(scroll)

        self._popup.adjustSize()

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    def _on_toggle(self, genre: str, checked: bool):
        if checked and genre not in self._selected:
            self._selected.append(genre)
        elif not checked and genre in self._selected:
            self._selected.remove(genre)
        self._update_button_label()
        self.genres_changed.emit(list(self._selected))

    def _on_clear(self):
        self.clear_selection()
        self.genres_changed.emit([])

    def _update_button_label(self):
        count = len(self._selected)
        if count == 0:
            self._btn.setText("Select Genre ▾")
        elif count == 1:
            self._btn.setText(f"{self._selected[0]} ▾")
        else:
            self._btn.setText(f"{count} Genres ▾")
