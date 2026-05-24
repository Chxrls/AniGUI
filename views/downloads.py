from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from anigui.backend.db import db
import os

class DownloadsView(QWidget):
    """View displaying downloaded anime episodes in a QTableWidget table.

    Double-clicking a row launches the file in the system default player.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        
        # Heading
        self.title_label = QLabel("Downloads", self)
        self.title_label.setObjectName("ViewTitle")
        self.layout.addWidget(self.title_label)
        
        # Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Title", "Episode", "File Path", "Size", "Status", "Date Added"
        ])
        
        # Style table headers
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Title takes up space
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Path takes up space
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setObjectName("DownloadsTable")
        self.table.itemDoubleClicked.connect(self.open_file)
        
        self.layout.addWidget(self.table)
        
        # Initial load
        self.refresh()

    def format_size(self, size_bytes: int) -> str:
        if not size_bytes or size_bytes <= 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"

    def refresh(self):
        # Fetch entries
        items = db.get_downloads()
        
        self.table.setRowCount(0)
        self.table.setRowCount(len(items))
        
        for row_idx, item in enumerate(items):
            title = item.get("anime_title") or "Unknown"
            episode = item.get("episode_str") or "?"
            file_path = item.get("file_path") or ""
            size = self.format_size(item.get("file_size_bytes", 0))
            status = item.get("status") or "queued"
            date = item.get("added_at") or ""
            
            # Create non-editable items
            t_item = QTableWidgetItem(title)
            t_item.setFlags(t_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 0, t_item)
            
            ep_item = QTableWidgetItem(f"Ep {episode}")
            ep_item.setFlags(ep_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 1, ep_item)
            
            path_item = QTableWidgetItem(file_path)
            path_item.setFlags(path_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 2, path_item)
            
            sz_item = QTableWidgetItem(size)
            sz_item.setFlags(sz_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 3, sz_item)
            
            st_item = QTableWidgetItem(status.capitalize())
            st_item.setFlags(st_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 4, st_item)
            
            dt_item = QTableWidgetItem(date)
            dt_item.setFlags(dt_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 5, dt_item)

    def open_file(self, item: QTableWidgetItem):
        row = item.row()
        path_item = self.table.item(row, 2)
        if not path_item:
            return
            
        file_path = path_item.text().strip()
        if not file_path:
            return
            
        # Standard desktop service open
        url = QUrl.fromLocalFile(file_path)
        QDesktopServices.openUrl(url)
