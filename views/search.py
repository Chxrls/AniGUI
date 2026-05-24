from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QScrollArea, QGridLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, QThreadPool
from anigui.backend.worker import SearchWorker
from anigui.widgets.card import AnimeCard

class SearchView(QWidget):
    """View allowing user to search for anime on AllAnime.

    Uses a debounced QTimer to start searches after typing stops.
    """
    def __init__(self, on_card_clicked, parent=None):
        super().__init__(parent)
        self.on_card_clicked = on_card_clicked
        self.cards = []
        
        # Debounce timer
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.perform_search)
        
        # Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        
        # Search bar header
        search_bar_layout = QHBoxLayout()
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search anime by name...")
        self.search_input.setObjectName("SearchInput")
        self.search_input.textChanged.connect(self.on_text_changed)
        self.search_input.returnPressed.connect(self.perform_search_immediately)
        search_bar_layout.addWidget(self.search_input)
        self.layout.addLayout(search_bar_layout)
        
        # Status Label (Loading/Error/No Results)
        self.status_label = QLabel("", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setObjectName("SearchStatus")
        self.status_label.hide()
        self.layout.addWidget(self.status_label)
        
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

    def on_text_changed(self):
        # Reset 500ms debounce timer on keystroke
        self.timer.start(500)

    def perform_search_immediately(self):
        self.timer.stop()
        self.perform_search()

    def perform_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
            
        self.status_label.setText("Loading...")
        self.status_label.show()
        self.scroll_area.hide()
        
        worker = SearchWorker(query)
        worker.signals.finished.connect(self._on_search_finished)
        worker.signals.error.connect(self._on_search_error)
        QThreadPool.globalInstance().start(worker)

    def _on_search_finished(self, results):
        self.status_label.hide()
        self.scroll_area.show()
        
        # Clear existing grid contents
        for i in reversed(range(self.grid_layout.count())): 
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                
        self.cards.clear()
        
        if not results:
            self.status_label.setText("No results found.")
            self.status_label.show()
            self.scroll_area.hide()
            return

        # Render cards
        for item in results:
            card = AnimeCard(item, self)
            card.clicked.connect(self.on_card_clicked)
            self.cards.append(card)
            
        self.rearrange_grid()

    def _on_search_error(self, err):
        self.scroll_area.hide()
        self.status_label.setText(f"Error: {err}")
        self.status_label.show()

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
