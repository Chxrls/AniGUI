import os
import sys

# Add parent directory to sys.path to resolve 'anigui' package imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QMessageBox
from anigui.backend.api import check_mpv_installed
from anigui.window import MainWindow

QSS_STYLESHEET = """
/* General Styles */
QMainWindow, QDialog, QWidget#GridContainer {
    background-color: #0f0f0f;
    color: #e8e8e8;
    font-family: 'Segoe UI', 'Roboto', 'Inter', sans-serif;
    font-size: 13px;
}

/* Sidebar Styling */
QWidget#Sidebar {
    background-color: #1a1a1a;
    border-right: 1px solid #2e2e2e;
}

QLabel#LogoLabel {
    color: #c084fc;
    font-size: 18px;
    font-weight: bold;
}

/* Navigation Buttons */
QPushButton[objectName^="nav_"] {
    text-align: left;
    padding-left: 15px;
    font-size: 13px;
    font-weight: 500;
    background: transparent;
    border: none;
}

QPushButton[objectName^="nav_"][active="true"] {
    color: #c084fc;
    border-left: 2px solid #c084fc;
}

QPushButton[objectName^="nav_"][active="false"] {
    color: #888888;
    border-left: 2px solid transparent;
}

QPushButton[objectName^="nav_"]:hover {
    color: #e8e8e8;
    background-color: #242424;
}

/* View Header */
QLabel#ViewTitle {
    font-size: 20px;
    font-weight: bold;
    color: #e8e8e8;
    padding-bottom: 5px;
}

QLabel#LoadingLabel, QLabel#BookmarksStatus, QLabel#SearchStatus {
    font-size: 14px;
    color: #888888;
}

/* Scroll Areas */
QScrollArea {
    background: transparent;
    border: none;
}

/* Anime Card Styling */
QFrame#AnimeCard {
    background-color: #1a1a1a;
    border: 1px solid #2e2e2e;
    border-radius: 4px;
}

QFrame#AnimeCard:hover {
    border-color: #c084fc;
}

QLabel#CardTitle {
    color: #e8e8e8;
    font-weight: bold;
    font-size: 12px;
}

QLabel#CardMetadata {
    color: #888888;
    font-size: 11px;
}

/* Detail dialog styling */
QLabel#DetailTitle {
    font-size: 18px;
    font-weight: bold;
    color: #e8e8e8;
}

QLabel#DetailEnglishTitle {
    font-size: 13px;
    color: #888888;
}

QLabel#DetailGenres {
    color: #888888;
    font-size: 11px;
}

QLabel#DetailSynopsis {
    font-size: 12px;
    color: #e8e8e8;
}

QLabel#EpisodesHeader {
    font-size: 14px;
    font-weight: bold;
    color: #e8e8e8;
}

/* Controls */
QComboBox {
    background-color: #242424;
    color: #e8e8e8;
    border: 1px solid #2e2e2e;
    border-radius: 4px;
    padding: 4px 8px;
    min-width: 60px;
}

QComboBox::drop-down {
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #1a1a1a;
    color: #e8e8e8;
    border: 1px solid #2e2e2e;
    selection-background-color: #242424;
}

QPushButton#BookmarkButton, QPushButton#DownloadButton {
    background-color: #242424;
    color: #e8e8e8;
    border: 1px solid #2e2e2e;
    border-radius: 4px;
    padding: 5px 10px;
    font-weight: bold;
}

QPushButton#BookmarkButton:hover, QPushButton#DownloadButton:hover {
    border-color: #c084fc;
    background-color: #2e2e2e;
}

/* Lists and Tables */
QListWidget, QTableWidget {
    background-color: #1a1a1a;
    border: 1px solid #2e2e2e;
    border-radius: 4px;
    color: #e8e8e8;
    gridline-color: #2e2e2e;
}

QListWidget::item:alternate, QTableWidget::item:alternate {
    background-color: #242424;
}

QListWidget::item:selected, QTableWidget::item:selected {
    background-color: #2e2e2e;
    color: #c084fc;
}

QHeaderView::section {
    background-color: #242424;
    color: #e8e8e8;
    border: 1px solid #2e2e2e;
    padding: 5px;
    font-weight: bold;
}

/* Search input */
QLineEdit#SearchInput {
    background-color: #1a1a1a;
    color: #e8e8e8;
    border: 1px solid #2e2e2e;
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 13px;
}

QLineEdit#SearchInput:focus {
    border-color: #c084fc;
}
"""

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AniGUI")
    
    # Check if mpv media player dependency is on path
    if not check_mpv_installed():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("mpv Required")
        msg.setText("The mpv media player was not found on your system PATH.")
        msg.setInformativeText(
            "AniGUI requires 'mpv' to stream media content.\n\n"
            "Please install it and ensure it is in your environment PATH variables:\n"
            "  • Windows: https://mpv.io/installation/\n"
            "  • macOS: brew install mpv\n"
            "  • Linux: sudo apt install mpv"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
        sys.exit(1)
        
    # Apply global QSS dark stylesheet
    app.setStyleSheet(QSS_STYLESHEET)
    
    # Load Main Window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
