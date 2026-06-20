from anigui.utils.theme import apply_theme
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QGridLayout,
    QLabel, QMenu, QPushButton, QStackedWidget, QLineEdit,
    QFrame, QInputDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QCursor
from anigui.backend.db import db
from anigui.widgets.card import AnimeCard
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Tab bar widget — pill-style toggle buttons
# ---------------------------------------------------------------------------

class BookmarkTabBar(QWidget):
    """Horizontal row of pill-style tab buttons."""

    def __init__(self, labels: list[str], on_select, parent=None):
        super().__init__(parent)
        self.on_select = on_select
        self._btns: dict[str, QPushButton] = {}
        self._active: str | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        for label in labels:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFixedHeight(32)
            btn.setObjectName("BookmarkTabBtn")
            btn.clicked.connect(lambda checked, l=label: self._clicked(l))
            self._style_btn(btn, False)
            layout.addWidget(btn)
            self._btns[label] = btn

        layout.addStretch()

    def _style_btn(self, btn: QPushButton, active: bool):
        if active:
            btn.setStyleSheet(apply_theme(
                "QPushButton { background-color: #c084fc; color: #0f0f0f; "
                "border: none; border-radius: 16px; padding: 0 18px; "
                "font-weight: bold; font-size: 13px; }"
            ))
        else:
            btn.setStyleSheet(apply_theme(
                "QPushButton { background-color: #242424; color: #888888; "
                "border: 1px solid #2e2e2e; border-radius: 16px; padding: 0 18px; "
                "font-size: 13px; }"
                "QPushButton:hover { color: #e8e8e8; border-color: #888888; }"
            ))

    def _clicked(self, label: str):
        self.set_active(label)
        self.on_select(label)

    def set_active(self, label: str):
        if self._active and self._active in self._btns:
            self._btns[self._active].setChecked(False)
            self._style_btn(self._btns[self._active], False)
        self._active = label
        if label in self._btns:
            self._btns[label].setChecked(True)
            self._style_btn(self._btns[label], True)


# ---------------------------------------------------------------------------
# Folder sidebar widget — used inside the Bookmarked tab
# ---------------------------------------------------------------------------

class FolderSidebar(QWidget):
    """Vertical list of folder buttons for filtering bookmarks."""

    def __init__(self, on_folder_select, parent=None):
        super().__init__(parent)
        self.on_folder_select = on_folder_select
        self._active_folder_id = None  # None = "All"
        self._btns: list[tuple[int | None, QPushButton]] = []

        self.setFixedWidth(180)
        self.setObjectName("FolderSidebar")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(4)

        header = QLabel("Folders")
        header.setObjectName("FolderSidebarHeader")
        header.setStyleSheet(apply_theme(
            "color: #888888; font-size: 11px; font-weight: bold; "
            "text-transform: uppercase; padding: 4px 8px; border: none;"
        ))
        self._layout.addWidget(header)
        self._layout.addStretch()

    def refresh(self):
        # Remove old buttons (keep header + stretch)
        while self._layout.count() > 2:
            item = self._layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        self._btns.clear()

        # "All" button
        all_btn = self._make_btn("All Bookmarks", None)
        self._layout.insertWidget(1, all_btn)
        self._btns.append((None, all_btn))

        # Folder buttons
        folders = db.get_bookmark_folders()
        for i, folder in enumerate(folders):
            btn = self._make_btn(f"📁  {folder['name']}", folder["id"])
            self._layout.insertWidget(2 + i, btn)
            self._btns.append((folder["id"], btn))

        self._update_styles()

    def _make_btn(self, text: str, folder_id: int | None) -> QPushButton:
        btn = QPushButton(text)
        btn.setFlat(True)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setFixedHeight(34)
        btn.setObjectName("FolderBtn")
        btn.clicked.connect(lambda: self._on_click(folder_id))
        return btn

    def _on_click(self, folder_id: int | None):
        self._active_folder_id = folder_id
        self._update_styles()
        self.on_folder_select(folder_id)

    def _update_styles(self):
        for fid, btn in self._btns:
            is_active = (fid == self._active_folder_id)
            if is_active:
                btn.setStyleSheet(apply_theme(
                    "QPushButton { text-align: left; padding-left: 10px; "
                    "color: #c084fc; background-color: #242424; "
                    "border: none; border-left: 2px solid #c084fc; "
                    "border-radius: 0; font-size: 12px; font-weight: bold; }"
                ))
            else:
                btn.setStyleSheet(apply_theme(
                    "QPushButton { text-align: left; padding-left: 12px; "
                    "color: #888888; background: transparent; "
                    "border: none; border-radius: 0; font-size: 12px; }"
                    "QPushButton:hover { color: #e8e8e8; background-color: #1a1a1a; }"
                ))


# ---------------------------------------------------------------------------
# History entry row widget
# ---------------------------------------------------------------------------

class HistoryEntryRow(QFrame):
    """Single row in the watch history list."""

    def __init__(self, entry: dict, on_click, on_remove, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.on_click = on_click
        self.on_remove = on_remove

        self.setObjectName("HistoryEntryRow")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(56)
        self.setStyleSheet(apply_theme(
            "QFrame#HistoryEntryRow { background-color: #1a1a1a; "
            "border: 1px solid #2e2e2e; border-radius: 6px; }"
            "QFrame#HistoryEntryRow:hover { border-color: #c084fc; }"
        ))

        hl = QHBoxLayout(self)
        hl.setContentsMargins(14, 8, 14, 8)
        hl.setSpacing(12)

        # Episode badge
        ep_str = entry.get("episode_str", "?")
        ep_badge = QLabel(f"EP {ep_str}")
        ep_badge.setObjectName("HistoryEpBadge")
        ep_badge.setFixedWidth(60)
        ep_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ep_badge.setStyleSheet(apply_theme(
            "QLabel { background-color: #242424; color: #c084fc; "
            "border-radius: 4px; padding: 2px 6px; font-size: 11px; "
            "font-weight: bold; border: none; }"
        ))
        hl.addWidget(ep_badge)

        # Vertical separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(apply_theme("color: #2e2e2e;"))
        hl.addWidget(sep)

        # Anime title
        title = entry.get("anime_title", "Unknown")
        title_label = QLabel(title if len(title) <= 60 else title[:57] + "…")
        title_label.setObjectName("HistoryTitle")
        title_label.setStyleSheet(apply_theme(
            "QLabel { color: #e8e8e8; font-size: 13px; font-weight: 500; border: none; }"
        ))
        hl.addWidget(title_label, stretch=1)

        # Translation type badge
        trans_type = entry.get("translation_type", "sub").upper()
        type_label = QLabel(trans_type)
        type_label.setObjectName("HistoryTransType")
        type_label.setFixedWidth(40)
        type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        type_color = "#16a34a" if trans_type == "SUB" else "#3b82f6"
        type_label.setStyleSheet(apply_theme(
            f"QLabel {{ background-color: {type_color}; color: white; "
            f"border-radius: 4px; padding: 2px 4px; font-size: 10px; "
            f"font-weight: bold; border: none; }}"
        ))
        hl.addWidget(type_label)

        # Timestamp
        watched_at = entry.get("watched_at", "")
        time_text = self._format_time(watched_at)
        time_label = QLabel(time_text)
        time_label.setObjectName("HistoryTime")
        time_label.setFixedWidth(80)
        time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        time_label.setStyleSheet(apply_theme(
            "QLabel { color: #888888; font-size: 11px; border: none; }"
        ))
        hl.addWidget(time_label)

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _format_time(self, timestamp_str: str) -> str:
        """Format the watched_at timestamp into a human-readable relative time."""
        if not timestamp_str:
            return ""
        try:
            dt = datetime.fromisoformat(timestamp_str)
            now = datetime.now()
            diff = now - dt
            if diff.days == 0:
                hours = diff.seconds // 3600
                if hours == 0:
                    minutes = diff.seconds // 60
                    return f"{max(1, minutes)}m ago"
                return f"{hours}h ago"
            elif diff.days == 1:
                return "Yesterday"
            elif diff.days < 7:
                return f"{diff.days}d ago"
            else:
                return dt.strftime("%b %d")
        except (ValueError, TypeError):
            return ""

    def _show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        menu.setObjectName("ContextMenu")
        action_remove = menu.addAction("Remove from history")
        global_pos = self.mapToGlobal(pos)
        selected = menu.exec(global_pos)
        if selected == action_remove:
            self.on_remove(self.entry.get("id"))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_click(self.entry)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Date header for history grouping
# ---------------------------------------------------------------------------

class DateHeader(QLabel):
    """Styled date group header for the history list."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("HistoryDateHeader")
        self.setStyleSheet(apply_theme(
            "QLabel { color: #c084fc; font-size: 13px; font-weight: bold; "
            "padding: 8px 4px 4px 4px; border: none; }"
        ))


# ---------------------------------------------------------------------------
# Folder row widget — for the Create Folder management tab
# ---------------------------------------------------------------------------

class FolderRow(QFrame):
    """Row representing a single folder with rename/delete actions."""

    def __init__(self, folder: dict, on_rename, on_delete, parent=None):
        super().__init__(parent)
        self.folder = folder
        self.on_rename = on_rename
        self.on_delete = on_delete

        self.setObjectName("FolderRow")
        self.setFixedHeight(48)
        self.setStyleSheet(apply_theme(
            "QFrame#FolderRow { background-color: #1a1a1a; "
            "border: 1px solid #2e2e2e; border-radius: 6px; }"
        ))

        hl = QHBoxLayout(self)
        hl.setContentsMargins(14, 8, 8, 8)
        hl.setSpacing(10)

        # Folder icon + name
        name_label = QLabel(f"📁  {folder['name']}")
        name_label.setStyleSheet(apply_theme(
            "QLabel { color: #e8e8e8; font-size: 13px; border: none; }"
        ))
        hl.addWidget(name_label, stretch=1)

        # Item count
        items = db.get_bookmarks_in_folder(folder["id"])
        count_label = QLabel(f"{len(items)} items")
        count_label.setStyleSheet(apply_theme(
            "QLabel { color: #888888; font-size: 11px; border: none; }"
        ))
        hl.addWidget(count_label)

        # Rename button
        rename_btn = QPushButton("Rename")
        rename_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        rename_btn.setObjectName("FolderActionBtn")
        rename_btn.setFixedSize(70, 28)
        rename_btn.setStyleSheet(apply_theme(
            "QPushButton { background-color: #242424; color: #e8e8e8; "
            "border: 1px solid #2e2e2e; border-radius: 4px; font-size: 11px; }"
            "QPushButton:hover { border-color: #c084fc; }"
        ))
        rename_btn.clicked.connect(lambda: self.on_rename(folder))
        hl.addWidget(rename_btn)

        # Delete button
        delete_btn = QPushButton("Delete")
        delete_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        delete_btn.setObjectName("FolderActionBtn")
        delete_btn.setFixedSize(70, 28)
        delete_btn.setStyleSheet(apply_theme(
            "QPushButton { background-color: #242424; color: #dc2626; "
            "border: 1px solid #2e2e2e; border-radius: 4px; font-size: 11px; }"
            "QPushButton:hover { border-color: #dc2626; }"
        ))
        delete_btn.clicked.connect(lambda: self.on_delete(folder))
        hl.addWidget(delete_btn)


# ===========================================================================
# Main BookmarksView
# ===========================================================================

class BookmarksView(QWidget):
    """View rendering bookmarked anime from the local SQLite database.

    Features three tabs:
    - Bookmarked: Grid of bookmarked anime with folder filtering
    - History: Chronological watch history with date grouping
    - Create Folder: Manage bookmark folders/groups
    """

    TAB_BOOKMARKED = "Bookmarked"
    TAB_HISTORY = "History"
    TAB_FOLDERS = "Create Folder"

    def __init__(self, on_card_clicked, parent=None):
        super().__init__(parent)
        self.on_card_clicked = on_card_clicked
        self.cards = []
        self._active_folder_id = None  # None = show all

        # Root layout
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # --- Top bar: Tab bar + separator + Folder filter buttons ---
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(6)

        # Tab buttons (Bookmarked / History / Create Folder)
        self.tab_bar = BookmarkTabBar(
            [self.TAB_BOOKMARKED, self.TAB_HISTORY, self.TAB_FOLDERS],
            self._on_tab_changed
        )
        top_bar.addWidget(self.tab_bar)

        # Vertical separator between tabs and folder filters
        self._folder_separator = QFrame()
        self._folder_separator.setFrameShape(QFrame.Shape.VLine)
        self._folder_separator.setFixedHeight(28)
        self._folder_separator.setStyleSheet(apply_theme("color: #444444;"))
        top_bar.addWidget(self._folder_separator)

        # Folder filter scroll area (horizontal, inline with tabs)
        self._folder_filter_scroll = QScrollArea()
        self._folder_filter_scroll.setWidgetResizable(True)
        self._folder_filter_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._folder_filter_scroll.setFixedHeight(38)
        self._folder_filter_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._folder_filter_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._folder_filter_scroll.setStyleSheet(apply_theme("background: transparent; border: none;"))

        self._folder_filter_container = QWidget()
        self._folder_filter_layout = QHBoxLayout(self._folder_filter_container)
        self._folder_filter_layout.setContentsMargins(0, 0, 0, 0)
        self._folder_filter_layout.setSpacing(6)
        self._folder_filter_layout.addStretch()

        self._folder_filter_scroll.setWidget(self._folder_filter_container)
        top_bar.addWidget(self._folder_filter_scroll, stretch=1)

        root.addLayout(top_bar)

        # --- Content stack ---
        self.stack = QStackedWidget(self)
        root.addWidget(self.stack)

        # ====== Tab 0: Bookmarked ======
        self._build_bookmarked_tab()

        # ====== Tab 1: History ======
        self._build_history_tab()

        # ====== Tab 2: Create Folder ======
        self._build_folders_tab()

        # Default to Bookmarked tab
        self.tab_bar.set_active(self.TAB_BOOKMARKED)
        self.stack.setCurrentIndex(0)

        # Initial load
        self.refresh()

    # ------------------------------------------------------------------
    # Tab 0: Bookmarked
    # ------------------------------------------------------------------

    def _build_bookmarked_tab(self):
        tab = QWidget()
        hl = QHBoxLayout(tab)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(10)

        # Left: Detail panel
        self.left_container = QWidget()
        left_vl = QVBoxLayout(self.left_container)
        left_vl.setContentsMargins(0, 0, 0, 0)
        left_vl.setSpacing(8)

        # Detail panel (no sidebar — folders are now in the top bar)
        self.detail_container = QWidget()
        self.detail_container.setObjectName("BookmarksLeftPanel")
        self.detail_container.setMinimumWidth(220)
        self.detail_container.setStyleSheet(apply_theme("""
            QWidget#BookmarksLeftPanel {
                background-color: #1a1a1a;
                border: 1px solid #2e2e2e;
                border-radius: 8px;
            }
        """))
        self.detail_layout = QVBoxLayout(self.detail_container)
        self.detail_layout.setContentsMargins(10, 10, 10, 10)

        self.placeholder_label = QLabel("Select a bookmark to view details.")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet(apply_theme("color: #888888; font-size: 14px; border: none;"))
        self.detail_layout.addWidget(self.placeholder_label)
        self.current_detail = None

        left_vl.addWidget(self.detail_container, stretch=1)
        hl.addWidget(self.left_container, stretch=2)

        # Right: Card grid
        right = QWidget()
        right_vl = QVBoxLayout(right)
        right_vl.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel("Bookmarked Anime")
        self.title_label.setObjectName("ViewTitle")
        right_vl.addWidget(self.title_label)

        self.status_label = QLabel("No bookmarks saved.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setObjectName("BookmarksStatus")
        right_vl.addWidget(self.status_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_area.setObjectName("ViewScrollArea")

        self.grid_container = QWidget()
        self.grid_container.setObjectName("GridContainer")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setHorizontalSpacing(15)
        self.grid_layout.setVerticalSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.grid_container)
        right_vl.addWidget(self.scroll_area)
        self.scroll_area.hide()

        hl.addWidget(right, stretch=3)
        self.stack.addWidget(tab)

    # ------------------------------------------------------------------
    # Tab 1: History
    # ------------------------------------------------------------------

    def _build_history_tab(self):
        tab = QWidget()
        vl = QVBoxLayout(tab)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        # Header
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 8)
        title = QLabel("Watch History")
        title.setObjectName("ViewTitle")
        header_row.addWidget(title)
        header_row.addStretch()
        vl.addLayout(header_row)

        # Status label
        self.history_status = QLabel("No watch history yet.")
        self.history_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_status.setObjectName("BookmarksStatus")
        vl.addWidget(self.history_status)

        # Scroll area for history entries
        self.history_scroll = QScrollArea()
        self.history_scroll.setWidgetResizable(True)
        self.history_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.history_scroll.setObjectName("ViewScrollArea")

        self.history_container = QWidget()
        self.history_container.setObjectName("GridContainer")
        self.history_list_layout = QVBoxLayout(self.history_container)
        self.history_list_layout.setContentsMargins(0, 0, 10, 10)
        self.history_list_layout.setSpacing(4)
        self.history_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.history_scroll.setWidget(self.history_container)
        vl.addWidget(self.history_scroll)
        self.history_scroll.hide()

        self.stack.addWidget(tab)

    # ------------------------------------------------------------------
    # Tab 2: Create Folder
    # ------------------------------------------------------------------

    def _build_folders_tab(self):
        tab = QWidget()
        vl = QVBoxLayout(tab)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(12)

        # Header
        title = QLabel("Manage Folders")
        title.setObjectName("ViewTitle")
        vl.addWidget(title)

        # Create folder input row
        create_row = QHBoxLayout()
        create_row.setSpacing(8)

        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Enter folder name...")
        self.folder_input.setObjectName("FolderInput")
        self.folder_input.setFixedHeight(36)
        self.folder_input.setStyleSheet(apply_theme(
            "QLineEdit { background-color: #1a1a1a; color: #e8e8e8; "
            "border: 1px solid #2e2e2e; border-radius: 6px; "
            "padding: 4px 12px; font-size: 13px; }"
            "QLineEdit:focus { border-color: #c084fc; }"
        ))
        self.folder_input.returnPressed.connect(self._create_folder)
        create_row.addWidget(self.folder_input, stretch=1)

        create_btn = QPushButton("Create Folder")
        create_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        create_btn.setObjectName("CreateFolderBtn")
        create_btn.setFixedHeight(36)
        create_btn.setStyleSheet(apply_theme(
            "QPushButton { background-color: #c084fc; color: #0f0f0f; "
            "border: none; border-radius: 6px; padding: 0 20px; "
            "font-weight: bold; font-size: 13px; }"
            "QPushButton:hover { background-color: #a855f7; }"
        ))
        create_btn.clicked.connect(self._create_folder)
        create_row.addWidget(create_btn)

        vl.addLayout(create_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(apply_theme("color: #2e2e2e;"))
        vl.addWidget(sep)

        # Existing folders label
        self.folders_count_label = QLabel("Your Folders")
        self.folders_count_label.setStyleSheet(apply_theme(
            "color: #888888; font-size: 12px; font-weight: bold;"
        ))
        vl.addWidget(self.folders_count_label)

        # Empty state
        self.folders_empty_label = QLabel("No folders created yet. Create one above!")
        self.folders_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.folders_empty_label.setObjectName("BookmarksStatus")
        vl.addWidget(self.folders_empty_label)

        # Scroll area for folder list
        self.folders_scroll = QScrollArea()
        self.folders_scroll.setWidgetResizable(True)
        self.folders_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.folders_scroll.setObjectName("ViewScrollArea")

        self.folders_list_container = QWidget()
        self.folders_list_container.setObjectName("GridContainer")
        self.folders_list_layout = QVBoxLayout(self.folders_list_container)
        self.folders_list_layout.setContentsMargins(0, 0, 10, 10)
        self.folders_list_layout.setSpacing(6)
        self.folders_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.folders_scroll.setWidget(self.folders_list_container)
        vl.addWidget(self.folders_scroll)
        self.folders_scroll.hide()

        self.stack.addWidget(tab)

    # ==================================================================
    # Event handlers
    # ==================================================================

    def _on_tab_changed(self, tab_label: str):
        # Show folder filter bar only on the Bookmarked tab
        show_folders = (tab_label == self.TAB_BOOKMARKED)
        self._folder_separator.setVisible(show_folders)
        self._folder_filter_scroll.setVisible(show_folders)

        if tab_label == self.TAB_BOOKMARKED:
            self.stack.setCurrentIndex(0)
            self._refresh_bookmarks()
        elif tab_label == self.TAB_HISTORY:
            self.stack.setCurrentIndex(1)
            self._refresh_history()
        elif tab_label == self.TAB_FOLDERS:
            self.stack.setCurrentIndex(2)
            self._refresh_folders_tab()

    def _on_folder_select(self, folder_id: int | None):
        self._active_folder_id = folder_id
        if folder_id is None:
            self.title_label.setText("Bookmarked Anime")
        else:
            folders = db.get_bookmark_folders()
            name = next((f["name"] for f in folders if f["id"] == folder_id), "Folder")
            self.title_label.setText(f"📁  {name}")
        self._refresh_folder_filter_bar()
        self._refresh_bookmarks()

    def _refresh_folder_filter_bar(self):
        """Rebuild the horizontal folder filter buttons in the top bar."""
        # Clear existing buttons
        while self._folder_filter_layout.count():
            item = self._folder_filter_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # "All Bookmarks" button
        all_btn = QPushButton("All Bookmarks")
        all_btn.setCheckable(True)
        all_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        all_btn.setFixedHeight(32)
        all_btn.setObjectName("FolderFilterBtn")
        is_all_active = (self._active_folder_id is None)
        all_btn.setChecked(is_all_active)
        self._style_folder_btn(all_btn, is_all_active)
        all_btn.clicked.connect(lambda: self._on_folder_select(None))
        self._folder_filter_layout.addWidget(all_btn)

        # Folder buttons
        folders = db.get_bookmark_folders()
        for folder in folders:
            btn = QPushButton(f"📁 {folder['name']}")
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFixedHeight(32)
            btn.setObjectName("FolderFilterBtn")
            is_active = (folder["id"] == self._active_folder_id)
            btn.setChecked(is_active)
            self._style_folder_btn(btn, is_active)
            btn.clicked.connect(lambda checked, fid=folder["id"]: self._on_folder_select(fid))
            self._folder_filter_layout.addWidget(btn)

        self._folder_filter_layout.addStretch()

    def _style_folder_btn(self, btn: QPushButton, active: bool):
        """Style a folder filter button (active vs inactive)."""
        if active:
            btn.setStyleSheet(apply_theme(
                "QPushButton { background-color: #7c3aed; color: #f0f0f0; "
                "border: none; border-radius: 16px; padding: 0 16px; "
                "font-weight: bold; font-size: 12px; }"
            ))
        else:
            btn.setStyleSheet(apply_theme(
                "QPushButton { background-color: #2a2a2a; color: #aaaaaa; "
                "border: 1px solid #3a3a3a; border-radius: 16px; padding: 0 16px; "
                "font-size: 12px; }"
                "QPushButton:hover { color: #e8e8e8; border-color: #7c3aed; }"
            ))

    # ------------------------------------------------------------------
    # Bookmarked tab logic
    # ------------------------------------------------------------------

    def on_local_card_clicked(self, anime_data):
        from anigui.views.detail import AnimeDetailWidget

        if self.current_detail:
            self.detail_layout.removeWidget(self.current_detail)
            self.current_detail.deleteLater()

        self.placeholder_label.hide()
        self.current_detail = AnimeDetailWidget(anime_data, self.detail_container)
        self.detail_layout.addWidget(self.current_detail)

    def _refresh_bookmarks(self):
        """Refresh the bookmarks grid, optionally filtered by folder."""
        if self._active_folder_id is not None:
            items = db.get_bookmarks_in_folder(self._active_folder_id)
        else:
            items = db.get_bookmarks()

        # Clear grid
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        self.cards.clear()

        if not items:
            if self._active_folder_id is not None:
                self.status_label.setText("No bookmarks in this folder.")
            else:
                self.status_label.setText("No bookmarks saved.")
            self.status_label.show()
            self.scroll_area.hide()
            if self.current_detail:
                self.detail_layout.removeWidget(self.current_detail)
                self.current_detail.deleteLater()
                self.current_detail = None
                self.placeholder_label.show()
            return

        self.status_label.hide()
        self.scroll_area.show()

        for item in items:
            anime_id = item["anime_id"]
            last_watched = db.get_last_watched_episode(anime_id)
            item["last_watched"] = last_watched

            anime_dict = {
                "id": anime_id,
                "name": item["anime_title"],
                "thumbnail_url_local": item["thumbnail_url"],
                "sub_count": item["sub_count"],
                "dub_count": item["dub_count"],
                "last_watched": last_watched,
                "anilist_id": item.get("anilist_id")
            }

            card = AnimeCard(anime_dict, self)
            card.clicked.connect(self.on_local_card_clicked)

            card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            card.customContextMenuRequested.connect(lambda pos, c=card: self._show_bookmark_context_menu(c, pos))

            self.cards.append(card)

        self.rearrange_grid()

    def _show_bookmark_context_menu(self, card: AnimeCard, pos: QPoint):
        menu = QMenu(self)
        menu.setObjectName("ContextMenu")

        action_detail = menu.addAction("Go to detail")
        action_remove = menu.addAction("Remove bookmark")

        # Folder assignment submenu
        folders = db.get_bookmark_folders()
        if folders:
            folder_menu = menu.addMenu("Add to folder")
            current_folders = db.get_folders_for_bookmark(card.anime_id)
            for folder in folders:
                prefix = "✓ " if folder["id"] in current_folders else ""
                action = folder_menu.addAction(f"{prefix}{folder['name']}")
                action.setData(folder)

            # Remove from folder option (if in any folder)
            if current_folders:
                remove_folder_menu = menu.addMenu("Remove from folder")
                for folder in folders:
                    if folder["id"] in current_folders:
                        action = remove_folder_menu.addAction(folder["name"])
                        action.setData(("remove", folder))

        global_pos = card.mapToGlobal(pos)
        selected_action = menu.exec(global_pos)

        if selected_action == action_detail:
            self.on_local_card_clicked(card.anime_data)
        elif selected_action == action_remove:
            db.remove_bookmark(card.anime_id)
            self._refresh_bookmarks()
        elif selected_action and selected_action.data():
            data = selected_action.data()
            if isinstance(data, tuple) and data[0] == "remove":
                folder = data[1]
                db.remove_bookmark_from_folder(folder["id"], card.anime_id)
                self._refresh_bookmarks()
            elif isinstance(data, dict):
                folder = data
                if folder["id"] in db.get_folders_for_bookmark(card.anime_id):
                    db.remove_bookmark_from_folder(folder["id"], card.anime_id)
                else:
                    db.add_bookmark_to_folder(folder["id"], card.anime_id)
                self._refresh_bookmarks()

    def rearrange_grid(self):
        if not self.cards:
            return

        width = self.scroll_area.width()
        cols = max(1, width // 200)

        for i, card in enumerate(self.cards):
            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(card, row, col)

    # ------------------------------------------------------------------
    # History tab logic
    # ------------------------------------------------------------------

    def _refresh_history(self):
        """Load and display the full watch history, grouped by date."""
        # Clear existing entries
        while self.history_list_layout.count():
            item = self.history_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        entries = db.get_full_watch_history()

        if not entries:
            self.history_status.show()
            self.history_scroll.hide()
            return

        self.history_status.hide()
        self.history_scroll.show()

        # Group entries by date
        current_date_label = None
        now = datetime.now()
        today = now.date()
        yesterday = today - timedelta(days=1)

        for entry in entries:
            watched_at = entry.get("watched_at", "")
            try:
                entry_date = datetime.fromisoformat(watched_at).date()
            except (ValueError, TypeError):
                entry_date = None

            # Determine date label
            if entry_date == today:
                date_text = "Today"
            elif entry_date == yesterday:
                date_text = "Yesterday"
            elif entry_date:
                days_diff = (today - entry_date).days
                if days_diff < 7:
                    date_text = entry_date.strftime("%A")  # Day name
                else:
                    date_text = entry_date.strftime("%B %d, %Y")
            else:
                date_text = "Unknown Date"

            # Add date header if new group
            if date_text != current_date_label:
                current_date_label = date_text
                header = DateHeader(date_text)
                self.history_list_layout.addWidget(header)

            # Add entry row
            row = HistoryEntryRow(entry, self._on_history_entry_click, self._on_history_entry_remove)
            self.history_list_layout.addWidget(row)

    def _on_history_entry_click(self, entry: dict):
        """When a history entry is clicked, open its detail view."""
        anime_data = {
            "id": entry.get("anime_id", ""),
            "name": entry.get("anime_title", "Unknown"),
            "anilist_id": entry.get("anilist_id"),
        }
        self.on_card_clicked(anime_data)

    def _on_history_entry_remove(self, entry_id: int):
        """Remove a single watch history entry."""
        if entry_id:
            db.remove_watch_history_entry(entry_id)
            self._refresh_history()

    # ------------------------------------------------------------------
    # Create Folder tab logic
    # ------------------------------------------------------------------

    def _refresh_folders_tab(self):
        """Refresh the folder management list."""
        # Clear existing rows
        while self.folders_list_layout.count():
            item = self.folders_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        folders = db.get_bookmark_folders()

        if not folders:
            self.folders_empty_label.show()
            self.folders_scroll.hide()
            self.folders_count_label.setText("Your Folders")
            return

        self.folders_empty_label.hide()
        self.folders_scroll.show()
        self.folders_count_label.setText(f"Your Folders ({len(folders)})")

        for folder in folders:
            row = FolderRow(folder, self._rename_folder, self._delete_folder)
            self.folders_list_layout.addWidget(row)

    def _create_folder(self):
        name = self.folder_input.text().strip()
        if not name:
            return

        # Check for duplicate names
        existing = db.get_bookmark_folders()
        if any(f["name"].lower() == name.lower() for f in existing):
            QMessageBox.warning(self, "Duplicate", f"A folder named '{name}' already exists.")
            return

        db.create_bookmark_folder(name)
        self.folder_input.clear()
        self._refresh_folders_tab()
        self._refresh_folder_filter_bar()

    def _rename_folder(self, folder: dict):
        new_name, ok = QInputDialog.getText(
            self, "Rename Folder",
            "Enter new name:",
            QLineEdit.EchoMode.Normal,
            folder["name"]
        )
        if ok and new_name.strip():
            new_name = new_name.strip()
            existing = db.get_bookmark_folders()
            if any(f["name"].lower() == new_name.lower() and f["id"] != folder["id"] for f in existing):
                QMessageBox.warning(self, "Duplicate", f"A folder named '{new_name}' already exists.")
                return
            db.rename_bookmark_folder(folder["id"], new_name)
            self._refresh_folders_tab()
            self._refresh_folder_filter_bar()

    def _delete_folder(self, folder: dict):
        reply = QMessageBox.question(
            self, "Delete Folder",
            f"Delete folder '{folder['name']}'?\n\nBookmarks inside will NOT be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            db.delete_bookmark_folder(folder["id"])
            if self._active_folder_id == folder["id"]:
                self._active_folder_id = None
            self._refresh_folders_tab()
            self._refresh_folder_filter_bar()

    # ==================================================================
    # Public API
    # ==================================================================

    def refresh(self):
        """Called when the Bookmarks tab is selected in the sidebar."""
        self._refresh_folder_filter_bar()
        current_tab = self.stack.currentIndex()
        if current_tab == 0:
            self._refresh_bookmarks()
        elif current_tab == 1:
            self._refresh_history()
        elif current_tab == 2:
            self._refresh_folders_tab()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.rearrange_grid()
