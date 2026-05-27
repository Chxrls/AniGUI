from anigui.utils.theme import apply_theme
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QMessageBox, QProgressBar
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from anigui.backend.db import db
from anigui.backend.worker import download_manager
import os
import subprocess

class DownloadsView(QWidget):
    """View displaying downloaded anime episodes in a QTableWidget table.

    Double-clicking a row launches the file in mpv.
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
        
        self.layout.addLayout(self.toolbar_layout)
        
        # Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Title", "Episode", "File Path", "Progress", "Status", "Date Added", "Actions"
        ])
        
        # Style table headers
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        
        self.table.setColumnWidth(0, 250) # Title
        self.table.setColumnWidth(1, 70)  # Episode
        self.table.setColumnWidth(2, 300) # File Path
        self.table.setColumnWidth(3, 160) # Progress
        self.table.setColumnWidth(4, 90)  # Status
        self.table.setColumnWidth(5, 120) # Date Added
        self.table.setColumnWidth(6, 120) # Actions
        
        header.setStretchLastSection(True)
        
        # Increase row height for a less cramped feel
        self.table.verticalHeader().setDefaultSectionSize(45)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setObjectName("DownloadsTable")
        self.table.itemDoubleClicked.connect(self.open_file)
        
        self.layout.addWidget(self.table)
        
        # Signals
        download_manager.progress_updated.connect(self.update_progress)
        download_manager.status_changed.connect(self.update_status)
        
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
            
            # Progress widget
            progress_widget = QWidget()
            p_layout = QVBoxLayout(progress_widget)
            p_layout.setContentsMargins(5, 5, 5, 5)
            p_bar = QProgressBar()
            p_bar.setRange(0, 100)
            if status == "completed":
                p_bar.setValue(100)
            else:
                p_bar.setValue(0)
            p_label = QLabel(size)
            p_label.setStyleSheet(apply_theme("font-size: 10px; color: #888888;"))
            p_layout.addWidget(p_bar)
            p_layout.addWidget(p_label)
            self.table.setCellWidget(row_idx, 3, progress_widget)
            
            st_item = QTableWidgetItem(status.capitalize())
            st_item.setFlags(st_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 4, st_item)
            
            dt_item = QTableWidgetItem(date)
            dt_item.setFlags(dt_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 5, dt_item)
            
            # Actions widget
            action_widget = QWidget()
            a_layout = QHBoxLayout(action_widget)
            a_layout.setContentsMargins(2, 2, 2, 2)
            a_layout.setSpacing(5)
            
            download_id = item["id"]
            
            if status in ["queued", "downloading", "paused"]:
                pause_btn = QPushButton("Pause" if status == "downloading" else "Resume")
                pause_btn.clicked.connect(lambda checked, d_id=download_id, b=pause_btn: self.toggle_pause(d_id, b))
                a_layout.addWidget(pause_btn)
                
            delete_btn = QPushButton("🗑️") # Trash icon
            delete_btn.setToolTip("Delete Download")
            delete_btn.setFixedWidth(35)
            delete_btn.clicked.connect(lambda checked, d_id=download_id: self.delete_single(d_id))
            a_layout.addWidget(delete_btn)
            
            self.table.setCellWidget(row_idx, 6, action_widget)

    def find_row_by_id(self, download_id: int):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == download_id:
                return row
        return -1

    def update_progress(self, download_id: int, info: dict):
        row = self.find_row_by_id(download_id)
        if row >= 0:
            widget = self.table.cellWidget(row, 3)
            if widget:
                p_bar = widget.findChild(QProgressBar)
                p_label = widget.findChild(QLabel)
                if p_bar and p_label:
                    p_bar.setValue(info.get("percentage", 0))
                    p_label.setText(f"{info.get('size', '0')} | {info.get('bitrate', '0 kb/s')}")

    def update_status(self, download_id: int, status: str):
        row = self.find_row_by_id(download_id)
        if row >= 0:
            st_item = self.table.item(row, 4)
            if st_item:
                st_item.setText(status.capitalize())
            
            # Force progress to 100% on completion
            if status == "completed":
                widget = self.table.cellWidget(row, 3)
                if widget:
                    p_bar = widget.findChild(QProgressBar)
                    if p_bar:
                        p_bar.setValue(100)
            
            action_widget = self.table.cellWidget(row, 6)
            if action_widget:
                buttons = action_widget.findChildren(QPushButton)
                if status in ["completed", "failed"]:
                    for btn in buttons:
                        if btn.text() in ["Pause", "Resume"]:
                            btn.hide()
                else:
                    for btn in buttons:
                        if btn.text() in ["Pause", "Resume"]:
                            btn.setText("Pause" if status == "downloading" else "Resume")

    def toggle_pause(self, download_id: int, btn: QPushButton):
        if btn.text() == "Pause":
            download_manager.pause_download(download_id)
        else:
            download_manager.resume_download(download_id)
            
    def delete_single(self, download_id: int):
        reply = QMessageBox.question(
            self, 'Confirm Deletion',
            'Are you sure you want to delete this download? \nThis will also delete the file from your disk.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            download_manager.cancel_download(download_id)
            items = db.get_downloads()
            for item in items:
                if item["id"] == download_id:
                    file_path = item.get("file_path", "")
                    if file_path and os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            print(f"Error deleting file {file_path}: {e}")
                    break
            db.remove_download(download_id)
            self.refresh()

    def open_file(self, item: QTableWidgetItem):
        row = item.row()
        path_item = self.table.item(row, 2)
        if not path_item:
            return
            
        file_path = path_item.text().strip()
        if not file_path or not os.path.exists(file_path):
            return
            
        try:
            player_path = db.get_setting("player_path", "mpv")
            hwdec_enabled = db.get_setting("hwdec_enabled", "false")
            
            cmd = [player_path]
            is_mpv = "mpv" in player_path.lower()
            if is_mpv:
                cmd.append("--no-terminal")
                if hwdec_enabled == "true":
                    cmd.append("--hwdec=auto")
            cmd.append(file_path)

            kwargs = {"start_new_session": True}
            if os.name == "nt":
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                kwargs["startupinfo"] = si
            subprocess.Popen(cmd, **kwargs)
        except FileNotFoundError:
            print(f"Player '{player_path}' not found! Falling back to default player.")
            url = QUrl.fromLocalFile(file_path)
            QDesktopServices.openUrl(url)
        except Exception as e:
            print(f"Error launching player: {e}")


