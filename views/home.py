from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QGridLayout, QLabel
from PyQt6.QtCore import Qt, QThreadPool
from anigui.backend.worker import SearchWorker
from anigui.widgets.card import AnimeCard

CURATED_TITLES = [
    "Bleach", "Naruto", "One Piece", "Demon Slayer", 
    "Attack on Titan", "Chainsaw Man", "Frieren", "Dungeon Meshi"
]

class HomeView(QWidget):
    """View loaded on startup, executing parallel searches for curated anime titles."""
    def __init__(self, on_card_clicked, parent=None):
        super().__init__(parent)
        self.on_card_clicked = on_card_clicked
        self.cards = []
        self.loaded_ids = set()
        self.search_results = []
        self.completed_searches = 0
        
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # Heading
        self.title_label = QLabel("Popular Anime", self)
        self.title_label.setObjectName("ViewTitle")
        self.layout.addWidget(self.title_label)
        
        # Loading State
        self.loading_label = QLabel("Loading...", self)
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setObjectName("LoadingLabel")
        self.layout.addWidget(self.loading_label)
        
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
        self.layout.addWidget(self.scroll_area)
        self.scroll_area.hide()
        
        # Start fetching
        self.load_curated()

    def load_curated(self):
        self.completed_searches = 0
        self.search_results.clear()
        self.loaded_ids.clear()
        
        for title in CURATED_TITLES:
            worker = SearchWorker(title)
            worker.signals.finished.connect(self._on_search_finished)
            worker.signals.error.connect(self._on_search_error)
            QThreadPool.globalInstance().start(worker)

    def _on_search_finished(self, results):
        self.completed_searches += 1
        if results:
            # We take the first match as the most relevant for each curated title
            first_match = results[0]
            if first_match["id"] not in self.loaded_ids:
                self.loaded_ids.add(first_match["id"])
                self.search_results.append(first_match)
                
        # Once all parallel queries return, render the grid
        if self.completed_searches >= len(CURATED_TITLES):
            self.render_grid()

    def _on_search_error(self, err):
        self.completed_searches += 1
        if self.completed_searches >= len(CURATED_TITLES):
            self.render_grid()

    def render_grid(self):
        # Clear loading state
        self.loading_label.hide()
        self.scroll_area.show()
        
        # Clear layout
        for i in reversed(range(self.grid_layout.count())): 
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        self.cards.clear()
        
        # Build cards
        for item in self.search_results:
            card = AnimeCard(item, self)
            card.clicked.connect(self.on_card_clicked)
            self.cards.append(card)
            
        self.rearrange_grid()

    def rearrange_grid(self):
        if not self.cards:
            return
            
        # Determine columns dynamically based on width
        width = self.scroll_area.width()
        cols = max(1, width // 200)  # card width (180px) + margins
        
        # Remove and re-add cards to grid layout
        for i, card in enumerate(self.cards):
            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(card, row, col)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.rearrange_grid()
