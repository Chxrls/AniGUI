from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QStackedWidget, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from anigui.utils.paths import get_icon_path
from anigui.views.home import HomeView
from anigui.views.search import SearchView
from anigui.views.bookmarks import BookmarksView
from anigui.views.downloads import DownloadsView
from anigui.views.settings import SettingsView
from anigui.views.about import AboutView
from anigui.views.detail import AnimeDetailDialog

class MainWindow(QMainWindow):
    """Primary application frame containing left navigation sidebar and central stacked router."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AniGUI")
        self.setMinimumSize(1100, 640)
        self.setObjectName("MainWindow")
        
        # Set window icon
        icon_path = get_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        
        self.showMaximized()
        
        # Central widget and layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- LEFT SIDEBAR (fixed 200px width) ---
        sidebar = QWidget(self)
        sidebar.setFixedWidth(200)
        sidebar.setObjectName("Sidebar")
        
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 15, 0, 15)
        sidebar_layout.setSpacing(5)
        
        # App logo/header (QLabel)
        self.logo_label = QLabel("  AniGUI", sidebar)
        self.logo_label.setObjectName("LogoLabel")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.logo_label.setFixedHeight(45)
        sidebar_layout.addWidget(self.logo_label)
        sidebar_layout.addSpacing(15)
        
        # Navigation buttons
        self.nav_buttons = {}
        
        btn_config = [
            ("Home", 0),
            ("Search", 1),
            ("Bookmarks", 2),
            ("Downloads", 3),
            ("Settings", 4)
        ]
        
        for text, index in btn_config:
            btn = QPushButton(f" {text}", sidebar)
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName(f"nav_{text.lower()}")
            btn.setProperty("active", "false")
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda checked, idx=index: self.switch_view(idx))
            
            sidebar_layout.addWidget(btn)
            self.nav_buttons[index] = btn
            
        sidebar_layout.addStretch()  # Push nav buttons up
        
        # "About" label pinned to the bottom of the sidebar
        self.about_label = QLabel("  About", sidebar)
        self.about_label.setObjectName("nav_about")
        self.about_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.about_label.setFixedHeight(32)
        self.about_label.setStyleSheet(
            "QLabel#nav_about {"
            "  color: #888888; font-size: 11px; padding-left: 15px;"
            "}"
            "QLabel#nav_about:hover { color: #c084fc; }"
        )
        self.about_label.mousePressEvent = lambda _: self.switch_view(5)
        sidebar_layout.addWidget(self.about_label)
        
        main_layout.addWidget(sidebar)
        
        # --- CENTRAL VIEWS STACK ---
        self.stacked_widget = QStackedWidget(self)
        self.stacked_widget.setObjectName("StackedWidget")
        
        # Instantiate subviews
        self.home_view = HomeView(on_card_clicked=self.show_anime_detail, parent=self)
        self.search_view = SearchView(on_card_clicked=self.show_anime_detail, parent=self)
        self.bookmarks_view = BookmarksView(on_card_clicked=self.show_anime_detail, parent=self)
        self.downloads_view = DownloadsView(parent=self)
        self.settings_view = SettingsView(parent=self)
        self.about_view = AboutView(parent=self)
        
        self.stacked_widget.addWidget(self.home_view)
        self.stacked_widget.addWidget(self.search_view)
        self.stacked_widget.addWidget(self.bookmarks_view)
        self.stacked_widget.addWidget(self.downloads_view)
        self.stacked_widget.addWidget(self.settings_view)
        self.stacked_widget.addWidget(self.about_view)
        
        main_layout.addWidget(self.stacked_widget)
        
        # Default view is Home (index 0)
        self.switch_view(0)

    def switch_view(self, index: int):
        self.stacked_widget.setCurrentIndex(index)
        
        # Update nav active states and dynamic QSS property
        for idx, btn in self.nav_buttons.items():
            is_active = (idx == index)
            btn.setProperty("active", "true" if is_active else "false")
            # Force UI styling updates
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            
        # Update About label highlight (it's outside the normal nav_buttons dict)
        is_about = (index == 5)
        self.about_label.setStyleSheet(
            "QLabel#nav_about {"
            f"  color: {'#c084fc' if is_about else '#888888'};"
            "  font-size: 11px; padding-left: 15px;"
            "}"
            "QLabel#nav_about:hover { color: #c084fc; }"
        )
        
        # Refresh dynamic database views on selection
        if index == 0:  # Home
            self.home_view.refresh_continue_watching()
        elif index == 2:  # Bookmarks
            self.bookmarks_view.refresh()
        elif index == 3:  # Downloads
            self.downloads_view.refresh()
        elif index == 5:  # About
            self.about_view.refresh_status()

    def show_anime_detail(self, anime_data: dict):
        dialog = AnimeDetailDialog(anime_data, self)
        dialog.exec()
        
        # Refresh current views in case bookmarks, watch state, or downloads changed
        current_idx = self.stacked_widget.currentIndex()
        if current_idx == 0:
            self.home_view.refresh_continue_watching()
        elif current_idx == 2:
            self.bookmarks_view.refresh()
