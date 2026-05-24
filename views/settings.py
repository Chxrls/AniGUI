from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog
from PyQt6.QtCore import Qt
from anigui.backend.db import db
import os

class SettingsView(QWidget):
    """View for application settings, including configuring download directory."""
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(15)
        
        # View Title
        self.title_label = QLabel("Settings", self)
        self.title_label.setObjectName("ViewTitle")
        self.layout.addWidget(self.title_label)
        
        # Settings Container
        self.settings_container = QWidget(self)
        self.settings_layout = QVBoxLayout(self.settings_container)
        self.settings_layout.setContentsMargins(0, 10, 0, 0)
        self.settings_layout.setSpacing(20)
        
        # Download Directory Setting
        self.download_dir_layout = QVBoxLayout()
        self.download_dir_label = QLabel("Download Directory", self.settings_container)
        self.download_dir_label.setStyleSheet("font-weight: bold; color: #e8e8e8; font-size: 14px;")
        
        self.download_dir_input_layout = QHBoxLayout()
        self.download_dir_input = QLineEdit(self.settings_container)
        self.download_dir_input.setObjectName("SearchInput") # Using existing styling
        self.download_dir_input.setReadOnly(True)
        
        # Load current setting
        current_dir = db.get_setting("download_path", "~/Downloads")
        self.download_dir_input.setText(os.path.expanduser(current_dir))
        
        self.browse_btn = QPushButton("Browse", self.settings_container)
        self.browse_btn.setObjectName("DownloadButton") # Using existing styling
        self.browse_btn.clicked.connect(self.browse_directory)
        
        self.download_dir_input_layout.addWidget(self.download_dir_input)
        self.download_dir_input_layout.addWidget(self.browse_btn)
        
        self.download_dir_layout.addWidget(self.download_dir_label)
        self.download_dir_layout.addLayout(self.download_dir_input_layout)
        
        self.settings_layout.addLayout(self.download_dir_layout)
        
        self.settings_layout.addStretch()
        self.layout.addWidget(self.settings_container)
        
    def browse_directory(self):
        current_dir = self.download_dir_input.text()
        new_dir = QFileDialog.getExistingDirectory(self, "Select Download Directory", current_dir)
        
        if new_dir:
            self.download_dir_input.setText(new_dir)
            db.set_setting("download_path", new_dir)
