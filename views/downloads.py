from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QMessageBox
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
        
        # Heading and Toolbar
        self.toolbar_layout = QHBoxLayout()
        self.title_label = QLabel("Downloads", self)
        self.title_label.setObjectName("ViewTitle")
        self.toolbar_layout.addWidget(self.title_label)
        
        self.toolbar_layout.addStretch()
        
        self.delete_btn = QPushButton("Delete Selected", self)
        self.delete_btn.clicked.connect(self.delete_selected)
        self.toolbar_layout.addWidget(self.delete_btn)
        
        self.layout.addLayout(self.toolbar_layout)
        
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
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
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
            t_item.setData(Qt.ItemDataRole.UserRole, item["id"])
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

    def delete_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
            
        reply = QMessageBox.question(
            self, 'Confirm Deletion',
            f'Are you sure you want to delete {len(selected_rows)} selected download(s)?\\nThis will also delete the downloaded files from your disk.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for index in selected_rows:
                row = index.row()
                # Get the item containing the ID
                t_item = self.table.item(row, 0)
                path_item = self.table.item(row, 2)
                
                if t_item and path_item:
                    download_id = t_item.data(Qt.ItemDataRole.UserRole)
                    file_path = path_item.text().strip()
                    
                    # Delete file from disk
                    if file_path and os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            print(f"Error deleting file {file_path}: {e}")
                    
                    # Remove from database
                    if download_id is not None:
                        db.remove_download(download_id)
            
            self.refresh()

