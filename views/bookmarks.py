from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QGridLayout, QLabel, QMenu
from PyQt6.QtCore import Qt, QPoint
from anigui.backend.db import db
from anigui.widgets.card import AnimeCard

class BookmarksView(QWidget):
    """View rendering bookmarked anime from the local SQLite database.

    Features a split screen with a persistent detail view on the left
    and the grid of bookmarked cards on the right.
    """
    def __init__(self, on_card_clicked, parent=None):
        super().__init__(parent)
        self.on_card_clicked = on_card_clicked  # Preserved just in case, but we use local click
        self.cards = []
        
        # Main Layout (Horizontal split)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(15)
        
        # --- Left Panel (Detail) ---
        self.left_container = QWidget(self)
        self.left_container.setMinimumWidth(450)
        self.left_container.setObjectName("BookmarksLeftPanel")
        self.left_container.setStyleSheet("""
            QWidget#BookmarksLeftPanel {
                background-color: #161616;
                border: 1px solid #2e2e2e;
                border-radius: 8px;
            }
        """)
        self.left_panel_layout = QVBoxLayout(self.left_container)
        self.left_panel_layout.setContentsMargins(10, 10, 10, 10)
        
        self.placeholder_label = QLabel("Select a bookmark to view details.", self.left_container)
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #888888; font-size: 14px; border: none;")
        self.left_panel_layout.addWidget(self.placeholder_label)
        self.current_detail = None
        
        self.layout.addWidget(self.left_container, stretch=2)
        
        # --- Right Panel (Grid) ---
        self.right_container = QWidget(self)
        self.right_panel_layout = QVBoxLayout(self.right_container)
        self.right_panel_layout.setContentsMargins(0, 0, 0, 0)
        
        # Heading
        self.title_label = QLabel("Bookmarked Anime", self.right_container)
        self.title_label.setObjectName("ViewTitle")
        self.right_panel_layout.addWidget(self.title_label)
        
        # Empty/Status label
        self.status_label = QLabel("No bookmarks saved.", self.right_container)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setObjectName("BookmarksStatus")
        self.right_panel_layout.addWidget(self.status_label)
        
        # Scroll Area
        self.scroll_area = QScrollArea(self.right_container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_area.setObjectName("ViewScrollArea")
        
        # Grid Container
        self.grid_container = QWidget()
        self.grid_container.setObjectName("GridContainer")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setHorizontalSpacing(15)
        self.grid_layout.setVerticalSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.grid_container)
        self.right_panel_layout.addWidget(self.scroll_area)
        self.scroll_area.hide()
        
        self.layout.addWidget(self.right_container, stretch=3)
        
        # Initial load
        self.refresh()

    def on_local_card_clicked(self, anime_data):
        from anigui.views.detail import AnimeDetailWidget
        
        if self.current_detail:
            self.left_panel_layout.removeWidget(self.current_detail)
            self.current_detail.deleteLater()
            
        self.placeholder_label.hide()
        self.current_detail = AnimeDetailWidget(anime_data, self.left_container)
        self.left_panel_layout.addWidget(self.current_detail)

    def refresh(self):
        # Fetch bookmarks from SQLite
        items = db.get_bookmarks()
        
        # Clear layout
        for i in reversed(range(self.grid_layout.count())): 
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                
        self.cards.clear()
        
        if not items:
            self.status_label.show()
            self.scroll_area.hide()
            # Also clear the detail view if it exists
            if self.current_detail:
                self.left_panel_layout.removeWidget(self.current_detail)
                self.current_detail.deleteLater()
                self.current_detail = None
                self.placeholder_label.show()
            return
            
        self.status_label.hide()
        self.scroll_area.show()
        
        # Map bookmarks to cards, loading last watched history
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
                "last_watched": last_watched
            }
            
            card = AnimeCard(anime_dict, self)
            card.clicked.connect(self.on_local_card_clicked)
            
            # Setup custom context menu on card right-click
            card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            card.customContextMenuRequested.connect(lambda pos, c=card: self.show_context_menu(c, pos))
            
            self.cards.append(card)
            
        self.rearrange_grid()

    def show_context_menu(self, card: AnimeCard, pos: QPoint):
        menu = QMenu(self)
        menu.setObjectName("ContextMenu")
        
        action_detail = menu.addAction("Go to detail")
        action_remove = menu.addAction("Remove bookmark")
        
        global_pos = card.mapToGlobal(pos)
        selected_action = menu.exec(global_pos)
        
        if selected_action == action_detail:
            self.on_local_card_clicked(card.anime_data)
        elif selected_action == action_remove:
            db.remove_bookmark(card.anime_id)
            self.refresh()

    def rearrange_grid(self):
        if not self.cards:
            return
            
        width = self.scroll_area.width()
        cols = max(1, width // 200)
        
        for i, card in enumerate(self.cards):
            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(card, row, col)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.rearrange_grid()
