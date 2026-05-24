from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QGridLayout, QLabel, QMenu
from PyQt6.QtCore import Qt, QPoint
from anigui.backend.db import db
from anigui.widgets.card import AnimeCard

class BookmarksView(QWidget):
    """View rendering bookmarked anime from the local SQLite database.

    Enables right-click context actions to delete or view details.
    """
    def __init__(self, on_card_clicked, parent=None):
        super().__init__(parent)
        self.on_card_clicked = on_card_clicked
        self.cards = []
        
        # Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # Heading
        self.title_label = QLabel("Bookmarked Anime", self)
        self.title_label.setObjectName("ViewTitle")
        self.layout.addWidget(self.title_label)
        
        # Empty/Status label
        self.status_label = QLabel("No bookmarks saved.", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setObjectName("BookmarksStatus")
        self.layout.addWidget(self.status_label)
        
        # Scroll Area
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_area.setObjectName("ViewScrollArea")
        
        # Container
        self.grid_container = QWidget()
        self.grid_container.setObjectName("GridContainer")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setHorizontalSpacing(15)
        self.grid_layout.setVerticalSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.grid_container)
        self.layout.addWidget(self.scroll_area)
        self.scroll_area.hide()
        
        # Initial load
        self.refresh()

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
            return
            
        self.status_label.hide()
        self.scroll_area.show()
        
        # Map bookmarks to cards, loading last watched history
        for item in items:
            anime_id = item["anime_id"]
            # Look up last watched episode in DB
            last_watched = db.get_last_watched_episode(anime_id)
            item["last_watched"] = last_watched
            
            # Since stored DB entries have 'thumbnail_url' (local path),
            # we need to map keys back to the structure expected by AnimeCard
            anime_dict = {
                "id": anime_id,
                "name": item["anime_title"],
                "thumbnail_url_local": item["thumbnail_url"],
                "sub_count": item["sub_count"],
                "dub_count": item["dub_count"],
                "last_watched": last_watched
            }
            
            card = AnimeCard(anime_dict, self)
            card.clicked.connect(self.on_card_clicked)
            
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
        
        # Map local card position to global screen position
        global_pos = card.mapToGlobal(pos)
        selected_action = menu.exec(global_pos)
        
        if selected_action == action_detail:
            self.on_card_clicked(card.anime_data)
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
