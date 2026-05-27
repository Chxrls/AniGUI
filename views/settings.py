from anigui.utils.theme import apply_theme
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QCheckBox, QComboBox, QSpinBox
from PyQt6.QtCore import Qt
from anigui.backend.db import db
import os
import sys

class SettingsView(QWidget):
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
        self.download_dir_label.setStyleSheet(apply_theme("font-weight: bold; color: #e8e8e8; font-size: 14px;"))
        
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
        
        # Hardware & Performance Section
        self.hw_perf_label = QLabel("Hardware & Performance", self.settings_container)
        self.hw_perf_label.setStyleSheet(apply_theme("font-weight: bold; color: #e8e8e8; font-size: 14px; margin-top: 10px;"))
        self.settings_layout.addWidget(self.hw_perf_label)

        # Hardware Acceleration Toggle
        self.hwdec_cb = QCheckBox("GPU Hardware Acceleration (MPV only)", self.settings_container)
        self.hwdec_cb.setStyleSheet(apply_theme("color: #e8e8e8; font-size: 13px;"))
        hwdec_val = db.get_setting("hwdec_enabled", "false")
        self.hwdec_cb.setChecked(hwdec_val == "true")
        self.hwdec_cb.stateChanged.connect(self.toggle_hwdec)
        self.settings_layout.addWidget(self.hwdec_cb)

        # Custom Video Player Path
        self.player_path_layout = QHBoxLayout()
        self.player_path_label = QLabel("Custom Player Path:", self.settings_container)
        self.player_path_label.setStyleSheet(apply_theme("color: #e8e8e8; font-size: 13px;"))
        self.player_path_input = QLineEdit(self.settings_container)
        self.player_path_input.setObjectName("SearchInput")
        self.player_path_input.setReadOnly(True)
        player_path_val = db.get_setting("player_path", "mpv")
        self.player_path_input.setText(player_path_val)
        
        self.browse_player_btn = QPushButton("Browse", self.settings_container)
        self.browse_player_btn.setObjectName("DownloadButton")
        self.browse_player_btn.clicked.connect(self.browse_player)
        
        self.player_path_layout.addWidget(self.player_path_label)
        self.player_path_layout.addWidget(self.player_path_input)
        self.player_path_layout.addWidget(self.browse_player_btn)
        self.settings_layout.addLayout(self.player_path_layout)
        
        # Cache Management
        self.cache_layout = QHBoxLayout()
        self.cache_label = QLabel("API Cache Size:", self.settings_container)
        self.cache_label.setStyleSheet(apply_theme("color: #e8e8e8; font-size: 13px;"))
        
        self.cache_size_label = QLabel(self.format_size(db.get_db_size()), self.settings_container)
        self.cache_size_label.setStyleSheet(apply_theme("color: #888888; font-size: 13px;"))
        
        self.clear_cache_btn = QPushButton("Clear Cache", self.settings_container)
        self.clear_cache_btn.setObjectName("DownloadButton")
        self.clear_cache_btn.clicked.connect(self.clear_cache)
        
        self.cache_layout.addWidget(self.cache_label)
        self.cache_layout.addWidget(self.cache_size_label)
        self.cache_layout.addStretch()
        self.cache_layout.addWidget(self.clear_cache_btn)
        self.settings_layout.addLayout(self.cache_layout)
        
        # Quality of Life Section
        self.qol_label = QLabel("Miscellaneous", self.settings_container)
        self.qol_label.setStyleSheet(apply_theme("font-weight: bold; color: #e8e8e8; font-size: 14px; margin-top: 10px;"))
        self.settings_layout.addWidget(self.qol_label)

        # Default Translation Preference
        self.trans_layout = QHBoxLayout()
        self.trans_label = QLabel("Default Release Preference:", self.settings_container)
        self.trans_label.setStyleSheet(apply_theme("color: #e8e8e8; font-size: 13px;"))
        
        self.trans_combo = QComboBox(self.settings_container)
        self.trans_combo.setStyleSheet(apply_theme("""
            QComboBox {
                padding: 5px;
                background-color: #2e2e2e;
                border-radius: 4px;
                color: white;
            }
        """))
        self.trans_combo.addItem("Sub", "sub")
        self.trans_combo.addItem("Dub", "dub")
        
        default_trans = db.get_setting("default_translation", "sub")
        index = self.trans_combo.findData(default_trans)
        if index != -1:
            self.trans_combo.setCurrentIndex(index)
            
        self.trans_combo.currentIndexChanged.connect(self.update_default_translation)
        
        self.trans_layout.addWidget(self.trans_label)
        self.trans_layout.addWidget(self.trans_combo)
        self.trans_layout.addStretch()
        self.settings_layout.addLayout(self.trans_layout)

        # Default Streaming Quality
        self.quality_layout = QHBoxLayout()
        self.quality_label = QLabel("Default Streaming Quality:", self.settings_container)
        self.quality_label.setStyleSheet(apply_theme("color: #e8e8e8; font-size: 13px;"))
        
        self.quality_combo = QComboBox(self.settings_container)
        self.quality_combo.setStyleSheet(apply_theme("""
            QComboBox {
                padding: 5px;
                background-color: #2e2e2e;
                border-radius: 4px;
                color: white;
            }
        """))
        self.quality_combo.addItem("Auto", "auto")
        self.quality_combo.addItem("1080p", "1080")
        self.quality_combo.addItem("720p", "720")
        self.quality_combo.addItem("480p", "480")
        self.quality_combo.addItem("360p", "360")
        
        default_quality = db.get_setting("default_quality", "auto")
        idx = self.quality_combo.findData(default_quality)
        if idx != -1:
            self.quality_combo.setCurrentIndex(idx)
            
        self.quality_combo.currentIndexChanged.connect(self.update_default_quality)
        
        self.quality_layout.addWidget(self.quality_label)
        self.quality_layout.addWidget(self.quality_combo)
        self.quality_layout.addStretch()
        self.settings_layout.addLayout(self.quality_layout)

        # App Theme
        self.theme_layout = QHBoxLayout()
        self.theme_label = QLabel("App Theme (Requires Restart):", self.settings_container)
        self.theme_label.setStyleSheet(apply_theme("color: #e8e8e8; font-size: 13px;"))
        
        self.theme_combo = QComboBox(self.settings_container)
        self.theme_combo.setStyleSheet(apply_theme("""
            QComboBox {
                padding: 5px;
                background-color: #2e2e2e;
                border-radius: 4px;
                color: white;
            }
        """))
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Light", "light")
        
        current_theme = db.get_setting("theme", "dark")
        idx = self.theme_combo.findData(current_theme)
        if idx != -1:
            self.theme_combo.setCurrentIndex(idx)
            
        self.theme_combo.currentIndexChanged.connect(self.update_theme)
        
        # Add Restart button
        self.restart_btn = QPushButton("Restart to Apply", self.settings_container)
        self.restart_btn.setObjectName("DownloadButton")
        self.restart_btn.clicked.connect(self.restart_app)
        self.restart_btn.hide() # Hidden initially
        
        self.theme_layout.addWidget(self.theme_label)
        self.theme_layout.addWidget(self.theme_combo)
        self.theme_layout.addWidget(self.restart_btn)
        self.theme_layout.addStretch()
        self.settings_layout.addLayout(self.theme_layout)

        # Essential / Download Settings
        #self.essential_label = QLabel("📥 Essential / Download Settings", self.settings_container)
        #self.essential_label.setStyleSheet(apply_theme("font-weight: bold; color: #e8e8e8; font-size: 14px; margin-top: 10px;"))
        #self.settings_layout.addWidget(self.essential_label)

        # Auto-Delete Finished Downloads
        self.auto_delete_cb = QCheckBox("Auto-Delete Finished Downloads (80%+ watched)", self.settings_container)
        self.auto_delete_cb.setStyleSheet(apply_theme("color: #e8e8e8; font-size: 13px;"))
        auto_del_val = db.get_setting("auto_delete_downloads", "false")
        self.auto_delete_cb.setChecked(auto_del_val == "true")
        self.auto_delete_cb.stateChanged.connect(self.toggle_auto_delete)
        self.settings_layout.addWidget(self.auto_delete_cb)

        # Concurrent Download Limits
        self.download_limit_layout = QHBoxLayout()
        self.download_limit_label = QLabel("Max Concurrent Downloads:", self.settings_container)
        self.download_limit_label.setStyleSheet(apply_theme("color: #e8e8e8; font-size: 13px;"))
        
        self.download_limit_spin = QSpinBox(self.settings_container)
        self.download_limit_spin.setStyleSheet(apply_theme("""
            QSpinBox {
                padding: 5px;
                background-color: #2e2e2e;
                border-radius: 4px;
                color: white;
            }
        """))

        self.download_limit_spin.setRange(1, 10)
        
        max_downloads = int(db.get_setting("max_concurrent_downloads", "3"))
        self.download_limit_spin.setValue(max_downloads)
        
        self.download_limit_spin.valueChanged.connect(self.update_download_limit)
        
        self.download_limit_layout.addWidget(self.download_limit_label)
        self.download_limit_layout.addWidget(self.download_limit_spin)
        self.download_limit_layout.addStretch()
        self.settings_layout.addLayout(self.download_limit_layout)
        
        self.settings_layout.addStretch()
        self.layout.addWidget(self.settings_container)
        
    def browse_directory(self):
        current_dir = self.download_dir_input.text()
        new_dir = QFileDialog.getExistingDirectory(self, "Select Download Directory", current_dir)
        
        if new_dir:
            self.download_dir_input.setText(new_dir)
            db.set_setting("download_path", new_dir)

    def toggle_hwdec(self, state):
        # state is an integer corresponding to Qt.CheckState
        is_checked = state == Qt.CheckState.Checked.value
        db.set_setting("hwdec_enabled", "true" if is_checked else "false")

    def browse_player(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Video Player Executable", "", "Executables (*.exe);;All Files (*)")
        if file_path:
            self.player_path_input.setText(file_path)
            db.set_setting("player_path", file_path)

    def format_size(self, size_bytes: int) -> str:
        if not size_bytes or size_bytes <= 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"

    def clear_cache(self):
        db.clear_cache()
        self.cache_size_label.setText(self.format_size(db.get_db_size()))

    def update_default_translation(self):
        val = self.trans_combo.currentData()
        db.set_setting("default_translation", val)
        
    def update_default_quality(self):
        val = self.quality_combo.currentData()
        db.set_setting("default_quality", val)
        
    def update_download_limit(self):
        val = self.download_limit_spin.value()
        db.set_setting("max_concurrent_downloads", str(val))
        # Update running manager if possible
        try:
            from anigui.backend.worker import download_manager
            download_manager.update_max_downloads(val)
        except Exception as e:
            print(f"Failed to update running download manager: {e}")

    def toggle_auto_delete(self, state):
        is_checked = state == Qt.CheckState.Checked.value
        db.set_setting("auto_delete_downloads", "true" if is_checked else "false")
        
    def update_theme(self):
        val = self.theme_combo.currentData()
        current_db_theme = db.get_setting("theme", "dark")
        if val != current_db_theme:
            db.set_setting("theme", val)
            self.restart_btn.show()
            
    def restart_app(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()
        os.execl(sys.executable, sys.executable, *sys.argv)
