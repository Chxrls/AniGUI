from anigui.utils.theme import apply_theme
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QCheckBox, QComboBox, QSpinBox,
    QGridLayout, QSizePolicy, QFrame, QScrollArea,
)
from PyQt6.QtCore import Qt
from anigui.backend.db import db
import os
import sys


# ── Shared helpers ──────────────────────────────────────────────────
_LABEL_SS  = "color: #e8e8e8; font-size: 13px;"
_HEADER_SS = "font-weight: bold; color: #e8e8e8; font-size: 14px;"
_COMBO_SS  = """
    QComboBox {
        padding: 5px;
        background-color: #2e2e2e;
        border-radius: 4px;
        color: white;
    }
"""
_SPIN_SS = """
    QSpinBox {
        padding: 5px;
        background-color: #2e2e2e;
        border-radius: 4px;
        color: white;
    }
"""

_LEFT  = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
_RIGHT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter   # labels also left-aligned


def _make_label(text: str, parent=None, style: str = _LABEL_SS) -> QLabel:
    lbl = QLabel(text, parent)
    lbl.setStyleSheet(apply_theme(style))
    return lbl


def _make_divider(parent=None) -> QFrame:
    line = QFrame(parent)
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Plain)
    line.setStyleSheet("QFrame { color: #2e2e2e; }")
    line.setFixedHeight(1)
    return line


class SettingsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Outer layout: title + scrollable form
        outer = QVBoxLayout(self)
        outer.setContentsMargins(15, 15, 15, 15)
        outer.setSpacing(15)
        self.layout = outer                        # keep attr name for compat

        self.title_label = QLabel("Settings", self)
        self.title_label.setObjectName("ViewTitle")
        outer.addWidget(self.title_label)

        # Scroll area wrapping the grid
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setObjectName("ViewScrollArea")

        self.settings_container = QWidget()
        self.settings_container.setObjectName("SettingsContainer")
        self.settings_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.settings_container.setStyleSheet(apply_theme(
            "QWidget#SettingsContainer {"
            "  background-color: #1a1a1a;"
            "  border: 1px solid #2e2e2e;"
            "  border-radius: 8px;"
            "}"
        ))
        scroll.setWidget(self.settings_container)
        outer.addWidget(scroll)

        grid = QGridLayout(self.settings_container)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 1)
        self.settings_layout = grid                # keep attr name for compat

        row = 0

        # ── 1. Download Directory ───────────────────────────────────
        self.download_dir_input = QLineEdit(self.settings_container)
        self.download_dir_input.setObjectName("SearchInput")
        self.download_dir_input.setReadOnly(True)
        self.download_dir_input.setSizePolicy(QSizePolicy.Policy.Expanding,
                                              QSizePolicy.Policy.Fixed)

        current_dir = db.get_setting("download_path", "~/Downloads")
        self.download_dir_input.setText(os.path.expanduser(current_dir))

        self.browse_btn = QPushButton("Browse", self.settings_container)
        self.browse_btn.setObjectName("DownloadButton")
        self.browse_btn.setFixedWidth(100)
        self.browse_btn.setSizePolicy(QSizePolicy.Policy.Fixed,
                                      QSizePolicy.Policy.Fixed)
        self.browse_btn.clicked.connect(self.browse_directory)

        dir_w = QWidget()
        dir_l = QHBoxLayout(dir_w)
        dir_l.setContentsMargins(0, 0, 0, 0)
        dir_l.setSpacing(8)
        dir_l.addWidget(self.download_dir_input)
        dir_l.addWidget(self.browse_btn)

        grid.addWidget(dir_w, row, 0)
        grid.addWidget(_make_label("Download Directory"), row, 1, _RIGHT)
        row += 1

        # ── Divider ────────────────────────────────────────────────
        grid.addWidget(_make_divider(), row, 0, 1, 2)
        row += 1

        # ── 2. Section: Hardware & Performance ─────────────────────
        grid.addWidget(_make_label("Hardware & Performance",
                                   style=_HEADER_SS), row, 0, 1, 2)
        row += 1

        # 3. GPU HW Accel
        self.hwdec_cb = QCheckBox("GPU Hardware Acceleration (MPV only)",
                                  self.settings_container)
        self.hwdec_cb.setStyleSheet(apply_theme(_LABEL_SS))
        self.hwdec_cb.setSizePolicy(QSizePolicy.Policy.Minimum,
                                    QSizePolicy.Policy.Fixed)
        hwdec_val = db.get_setting("hwdec_enabled", "false")
        self.hwdec_cb.setChecked(hwdec_val == "true")
        self.hwdec_cb.stateChanged.connect(self.toggle_hwdec)

        grid.addWidget(self.hwdec_cb, row, 0, _LEFT)
        row += 1

        # 4. Custom Player Path
        self.player_path_input = QLineEdit(self.settings_container)
        self.player_path_input.setObjectName("SearchInput")
        self.player_path_input.setReadOnly(True)
        self.player_path_input.setSizePolicy(QSizePolicy.Policy.Expanding,
                                             QSizePolicy.Policy.Fixed)
        player_path_val = db.get_setting("player_path", "mpv")
        self.player_path_input.setText(player_path_val)

        self.browse_player_btn = QPushButton("Browse", self.settings_container)
        self.browse_player_btn.setObjectName("DownloadButton")
        self.browse_player_btn.setFixedWidth(100)
        self.browse_player_btn.setSizePolicy(QSizePolicy.Policy.Fixed,
                                             QSizePolicy.Policy.Fixed)
        self.browse_player_btn.clicked.connect(self.browse_player)

        player_w = QWidget()
        player_l = QHBoxLayout(player_w)
        player_l.setContentsMargins(0, 0, 0, 0)
        player_l.setSpacing(8)
        player_l.addWidget(self.player_path_input)
        player_l.addWidget(self.browse_player_btn)

        grid.addWidget(player_w, row, 0)
        grid.addWidget(_make_label("Custom Player Path"), row, 1, _RIGHT)
        row += 1

        # 5. API Cache Size
        self.cache_size_label = QLabel(self.format_size(db.get_db_size()),
                                       self.settings_container)
        self.cache_size_label.setStyleSheet(apply_theme("color: #888888; font-size: 13px;"))
        self.cache_size_label.setSizePolicy(QSizePolicy.Policy.Minimum,
                                            QSizePolicy.Policy.Fixed)

        self.clear_cache_btn = QPushButton("Clear Cache", self.settings_container)
        self.clear_cache_btn.setObjectName("DownloadButton")
        self.clear_cache_btn.setFixedWidth(100)
        self.clear_cache_btn.setSizePolicy(QSizePolicy.Policy.Fixed,
                                           QSizePolicy.Policy.Fixed)
        self.clear_cache_btn.clicked.connect(self.clear_cache)

        cache_w = QWidget()
        cache_l = QHBoxLayout(cache_w)
        cache_l.setContentsMargins(0, 0, 0, 0)
        cache_l.setSpacing(8)
        cache_l.addWidget(self.cache_size_label)
        cache_l.addStretch()
        cache_l.addWidget(self.clear_cache_btn)

        grid.addWidget(cache_w, row, 0)
        grid.addWidget(_make_label("API Cache Size"), row, 1, _RIGHT)
        row += 1


        # ── Divider ────────────────────────────────────────────────
        grid.addWidget(_make_divider(), row, 0, 1, 2)
        row += 1

        # ── 6. Section: Miscellaneous ──────────────────────────────
        grid.addWidget(_make_label("Miscellaneous", style=_HEADER_SS),
                       row, 0, 1, 2)
        row += 1

        # 7. Default Release Preference
        self.trans_combo = QComboBox(self.settings_container)
        self.trans_combo.view().setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.trans_combo.setStyleSheet(apply_theme(_COMBO_SS))
        self.trans_combo.setSizePolicy(QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Fixed)
        self.trans_combo.addItem("Sub", "sub")
        self.trans_combo.addItem("Dub", "dub")

        default_trans = db.get_setting("default_translation", "sub")
        index = self.trans_combo.findData(default_trans)
        if index != -1:
            self.trans_combo.setCurrentIndex(index)
        self.trans_combo.currentIndexChanged.connect(
            self.update_default_translation)

        grid.addWidget(self.trans_combo, row, 0, _LEFT)
        grid.addWidget(_make_label("Default Release Preference"), row, 1, _RIGHT)
        row += 1

        # 8. Default Streaming Quality
        self.quality_combo = QComboBox(self.settings_container)
        self.quality_combo.view().setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.quality_combo.setStyleSheet(apply_theme(_COMBO_SS))
        self.quality_combo.setSizePolicy(QSizePolicy.Policy.Expanding,
                                         QSizePolicy.Policy.Fixed)
        self.quality_combo.addItem("Auto", "auto")
        self.quality_combo.addItem("1080p", "1080")
        self.quality_combo.addItem("720p", "720")
        self.quality_combo.addItem("480p", "480")
        self.quality_combo.addItem("360p", "360")

        default_quality = db.get_setting("default_quality", "auto")
        idx = self.quality_combo.findData(default_quality)
        if idx != -1:
            self.quality_combo.setCurrentIndex(idx)
        self.quality_combo.currentIndexChanged.connect(
            self.update_default_quality)

        grid.addWidget(self.quality_combo, row, 0, _LEFT)
        grid.addWidget(_make_label("Default Streaming Quality"), row, 1, _RIGHT)
        row += 1

        # 9. App Theme
        self.theme_combo = QComboBox(self.settings_container)
        self.theme_combo.view().setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.theme_combo.setStyleSheet(apply_theme(_COMBO_SS))
        self.theme_combo.setSizePolicy(QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Fixed)
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Light", "light")

        current_theme = db.get_setting("theme", "dark")
        idx = self.theme_combo.findData(current_theme)
        if idx != -1:
            self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.currentIndexChanged.connect(self.update_theme)

        self.restart_btn = QPushButton("Restart to Apply", self.settings_container)
        self.restart_btn.setObjectName("DownloadButton")
        self.restart_btn.setSizePolicy(QSizePolicy.Policy.Fixed,
                                       QSizePolicy.Policy.Fixed)
        self.restart_btn.clicked.connect(self.restart_app)
        self.restart_btn.hide()

        grid.addWidget(self.theme_combo, row, 0, _LEFT)
        grid.addWidget(_make_label("App Theme (Requires Restart)"), row, 1, _RIGHT)
        row += 1

        grid.addWidget(self.restart_btn, row, 0, _LEFT)
        row += 1

        # 10. Auto-Delete Finished Downloads
        self.auto_delete_cb = QCheckBox(
            "Auto-Delete Finished Downloads (80%+ watched)",
            self.settings_container)
        self.auto_delete_cb.setStyleSheet(apply_theme(_LABEL_SS))
        self.auto_delete_cb.setSizePolicy(QSizePolicy.Policy.Minimum,
                                          QSizePolicy.Policy.Fixed)
        auto_del_val = db.get_setting("auto_delete_downloads", "false")
        self.auto_delete_cb.setChecked(auto_del_val == "true")
        self.auto_delete_cb.stateChanged.connect(self.toggle_auto_delete)

        grid.addWidget(self.auto_delete_cb, row, 0, _LEFT)
        row += 1

        # 11. Max Concurrent Downloads
        self.download_limit_spin = QSpinBox(self.settings_container)
        self.download_limit_spin.setStyleSheet(apply_theme(_SPIN_SS))
        self.download_limit_spin.setMinimumWidth(80)
        self.download_limit_spin.setSizePolicy(QSizePolicy.Policy.Minimum,
                                               QSizePolicy.Policy.Fixed)
        self.download_limit_spin.setRange(1, 10)

        max_downloads = int(db.get_setting("max_concurrent_downloads", "3"))
        self.download_limit_spin.setValue(max_downloads)
        self.download_limit_spin.valueChanged.connect(
            self.update_download_limit)

        grid.addWidget(self.download_limit_spin, row, 0, _LEFT)
        grid.addWidget(_make_label("Max Concurrent Downloads"), row, 1, _RIGHT)
        row += 1

        # Bottom spacer
        grid.setRowStretch(row, 1)



    # ── Handlers (unchanged) ───────────────────────────────────────
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
