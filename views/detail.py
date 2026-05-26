from anigui.utils.theme import apply_theme
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, 
    QComboBox, QListWidget, QListWidgetItem, QPushButton, QWidget, QScrollArea, QMenu
)
from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtGui import QPixmap
from anigui.backend.api import fetch_episodes
from anigui.backend.db import db
from anigui.backend.worker import EpisodeResolveWorker
from anigui.widgets.player import launch_player_and_save_history
import os

class AnimeDetailWidget(QWidget):
    """Detailed view for a selected anime.

    Allows translation selection, bookmark toggling, download queueing,
    and episode double-click streaming.
    """
    def __init__(self, anime_data: dict, parent=None):
        super().__init__(parent)
        self.anime_data = anime_data.copy()
        
        self.anime_id = self.anime_data.get("id") or self.anime_data.get("anime_id")
        self.title = self.anime_data.get("name") or self.anime_data.get("anime_title") or "Unknown Title"
        self.english_title = self.anime_data.get("english_name", "")
        raw_synopsis = self.anime_data.get("synopsis") or "No synopsis available."
        self.synopsis = raw_synopsis.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n").replace("<i>", "").replace("</i>", "").replace("<b>", "").replace("</b>", "").strip()
        self.genres = self.anime_data.get("genres") or []
        self.sub_count = self.anime_data.get("sub_count", 0)
        self.dub_count = self.anime_data.get("dub_count", 0)
        
        # Local thumbnail path
        self.thumb_path = self.anime_data.get("thumbnail_url_local") or ""
        
        # Widget attributes
        self.setObjectName("DetailWidget")
        
        # Layouts
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(15)
        
        # Top panel layout (Metadata columns)
        top_layout = QHBoxLayout()
        top_layout.setSpacing(15)
        
        # Left: Cover Art (fixed 200 x 300)
        self.cover_label = QLabel(self)
        self.cover_label.setFixedSize(200, 300)
        self.cover_label.setObjectName("DetailCover")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if self.thumb_path and os.path.exists(self.thumb_path):
            pix = QPixmap(self.thumb_path)
            if not pix.isNull():
                self.cover_label.setPixmap(pix.scaled(
                    self.cover_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                ))
        else:
            self.cover_label.setStyleSheet(apply_theme("background-color: #242424; color: #888888; border: 1px dashed #2e2e2e;"))
            self.cover_label.setText("No Image")
        top_layout.addWidget(self.cover_label, alignment=Qt.AlignmentFlag.AlignTop)
        
        # Right: Info details
        info_widget = QWidget(self)
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(8)
        
        self.title_label = QLabel(self.title, self)
        self.title_label.setObjectName("DetailTitle")
        self.title_label.setWordWrap(True)
        info_layout.addWidget(self.title_label)
        
        if self.english_title and self.english_title.lower() != self.title.lower():
            self.eng_label = QLabel(self.english_title, self)
            self.eng_label.setObjectName("DetailEnglishTitle")
            self.eng_label.setWordWrap(True)
            info_layout.addWidget(self.eng_label)
            
        # Genre list
        genre_str = ", ".join(self.genres) if self.genres else "Unknown Genres"
        self.genres_label = QLabel(f"Genres: {genre_str}", self)
        self.genres_label.setObjectName("DetailGenres")
        self.genres_label.setWordWrap(True)
        info_layout.addWidget(self.genres_label)
        
        # Synopsis (Full text scrollable / wrapped)
        self.synopsis_label = QLabel(self.synopsis, self)
        self.synopsis_label.setWordWrap(True)
        self.synopsis_label.setObjectName("DetailSynopsis")
        self.synopsis_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        # Wrap synopsis in a scroll area to keep layout clean
        self.synopsis_scroll = QScrollArea(self)
        self.synopsis_scroll.setWidgetResizable(True)
        self.synopsis_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.synopsis_scroll.setStyleSheet(apply_theme("background: transparent; border: none;"))
        self.synopsis_scroll.setWidget(self.synopsis_label)
        
        info_layout.addWidget(self.synopsis_scroll)
        
        # Controls row (Selector & Buttons)
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)
        
        # Translation type Selector
        self.trans_selector = QComboBox(self)
        self.trans_selector.setObjectName("TranslationSelector")
        if self.sub_count > 0:
            self.trans_selector.addItem("Sub", "sub")
        if self.dub_count > 0:
            self.trans_selector.addItem("Dub", "dub")
        if self.trans_selector.count() == 0:
            # Default fallback if counts are missing
            self.trans_selector.addItem("Sub", "sub")
            self.trans_selector.addItem("Dub", "dub")
            
        default_trans = db.get_setting("default_translation", "sub")
        index = self.trans_selector.findData(default_trans)
        if index != -1:
            self.trans_selector.setCurrentIndex(index)
            
        self.trans_selector.currentIndexChanged.connect(self.load_episodes)
        controls_layout.addWidget(self.trans_selector)
        
        # Bookmark button
        self.bookmark_btn = QPushButton(self)
        self.bookmark_btn.setObjectName("BookmarkButton")
        self.bookmark_btn.clicked.connect(self.toggle_bookmark)
        self.update_bookmark_button_ui()
        controls_layout.addWidget(self.bookmark_btn)
        
        # Download button with Dropdown Menu
        self.download_btn = QPushButton("Download", self)
        self.download_btn.setObjectName("DownloadButton")
        
        self.download_menu = QMenu(self)
        dl_ep_action = self.download_menu.addAction("Download Selected Ep")
        dl_ep_action.triggered.connect(self.queue_download)
        dl_all_action = self.download_menu.addAction("Download All Eps")
        dl_all_action.triggered.connect(self.queue_download_all)
        
        self.download_btn.setMenu(self.download_menu)
        controls_layout.addWidget(self.download_btn)
        
        top_layout.addWidget(info_widget)
        self.main_layout.addLayout(top_layout)
        self.main_layout.addLayout(controls_layout)
        
        # Bottom: Episode list header & Status
        status_row = QHBoxLayout()
        self.episodes_hdr = QLabel("Episodes", self)
        self.episodes_hdr.setObjectName("EpisodesHeader")
        status_row.addWidget(self.episodes_hdr)
        
        self.status_label = QLabel("", self)
        self.status_label.setObjectName("DetailStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status_row.addWidget(self.status_label)
        self.main_layout.addLayout(status_row)
        
        # Scrollable episode list widget
        self.episode_list_widget = QListWidget(self)
        self.episode_list_widget.setObjectName("EpisodeList")
        self.episode_list_widget.setAlternatingRowColors(True)
        self.episode_list_widget.itemDoubleClicked.connect(self.play_selected_episode)
        self.main_layout.addWidget(self.episode_list_widget)
        
        # Load initial episode list
        self.load_episodes()

    def get_current_translation(self) -> str:
        return self.trans_selector.currentData() or "sub"

    def load_episodes(self):
        self.episode_list_widget.clear()
        translation_type = self.get_current_translation()
        
        # Fetch list of episodes via AllAnime mapping
        ep_list = fetch_episodes(self.anime_data, translation_type)
        
        for ep in ep_list:
            ep_str = ep["number_str"]
            is_watched = db.is_watched(self.anime_id, ep_str, translation_type)
            
            item = QListWidgetItem()
            # Embed episode object
            item.setData(Qt.ItemDataRole.UserRole, ep)
            
            # Format display label with HTML watched tag if watched
            label_text = f"Ep {ep_str}"
            if is_watched:
                label_text += " <font color='#888888'>[Watched]</font>"
                
            label = QLabel(label_text, self.episode_list_widget)
            label.setContentsMargins(8, 6, 8, 6)
            
            # Match list item size to label size
            item.setSizeHint(label.sizeHint())
            self.episode_list_widget.addItem(item)
            self.episode_list_widget.setItemWidget(item, label)

    def update_bookmark_button_ui(self):
        is_bookmarked = db.is_bookmarked(self.anime_id)
        if is_bookmarked:
            self.bookmark_btn.setText("Remove Bookmark")
        else:
            self.bookmark_btn.setText("Bookmark")

    def toggle_bookmark(self):
        is_bookmarked = db.is_bookmarked(self.anime_id)
        if is_bookmarked:
            db.remove_bookmark(self.anime_id)
        else:
            db.add_bookmark(
                anime_id=self.anime_id,
                anime_title=self.title,
                thumbnail_url=self.thumb_path,
                sub_count=self.sub_count,
                dub_count=self.dub_count
            )
        self.update_bookmark_button_ui()

    def play_selected_episode(self, item: QListWidgetItem):
        ep_data = item.data(Qt.ItemDataRole.UserRole)
        if not ep_data:
            return
            
        ep_str = ep_data["number_str"]
        translation_type = self.get_current_translation()
        
        self.status_label.setText("Resolving stream URL...")
        self.status_label.setStyleSheet(apply_theme("color: #c084fc;"))  # Accent status
        
        # Async stream resolution
        worker = EpisodeResolveWorker(self.anime_id, ep_str, translation_type)
        worker.signals.finished.connect(lambda url: self._on_stream_resolved(url, ep_str, translation_type))
        worker.signals.error.connect(self._on_stream_failed)
        QThreadPool.globalInstance().start(worker)

    def _on_stream_resolved(self, url: str, ep_str: str, translation_type: str):
        self.status_label.setText("Success")
        self.status_label.setStyleSheet(apply_theme("color: #888888;"))
        
        try:
            # Play using mpv and record watched log
            launch_player_and_save_history(
                url=url,
                anime_id=self.anime_id,
                anime_title=self.title,
                episode_str=ep_str,
                translation_type=translation_type
            )
            # Reload episode list to reflect Watched status
            self.load_episodes()
        except Exception as e:
            self._on_stream_failed(str(e))

    def _on_stream_failed(self, err_msg: str):
        self.status_label.setText(f"Error: {err_msg}")
        self.status_label.setStyleSheet(apply_theme("color: #f87171;"))  # Error red

    def queue_download(self):
        # Find currently highlighted item in list
        selected_items = self.episode_list_widget.selectedItems()
        if not selected_items:
            self.status_label.setText("Select an episode to download first.")
            self.status_label.setStyleSheet(apply_theme("color: #f87171;"))
            return
            
        item = selected_items[0]
        ep_data = item.data(Qt.ItemDataRole.UserRole)
        if not ep_data:
            return
            
        ep_str = ep_data["number_str"]
        translation_type = self.get_current_translation()
        
        # Retrieve user configured download path
        download_dir = db.get_setting("download_path", "~/Downloads")
        download_dir = os.path.expanduser(download_dir)
        os.makedirs(download_dir, exist_ok=True)
        
        safe_title = "".join([c for c in self.title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        file_path = os.path.join(download_dir, f"{safe_title}_Ep_{ep_str}.mp4")
        
        # Insert a stub record in the local SQLite downloads table.
        print(f"Queueing download for {file_path}", flush=True)
        download_id = db.add_download(
            anime_id=self.anime_id,
            anime_title=self.title,
            episode_str=ep_str,
            file_path=file_path,
            size=0
        )
        
        from anigui.backend.worker import download_manager
        download_manager.start_download(download_id, self.anime_id, ep_str, translation_type, file_path)
        
        self.status_label.setText(f"Started downloading Ep {ep_str}.")
        self.status_label.setStyleSheet(apply_theme("color: #c084fc;"))

    def queue_download_all(self):
        translation_type = self.get_current_translation()
        ep_list = fetch_episodes(self.anime_data, translation_type)
        if not ep_list:
            self.status_label.setText("No episodes found to download.")
            self.status_label.setStyleSheet(apply_theme("color: #f87171;"))
            return
            
        download_dir = db.get_setting("download_path", "~/Downloads")
        download_dir = os.path.expanduser(download_dir)
        os.makedirs(download_dir, exist_ok=True)
        
        safe_title = "".join([c for c in self.title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        
        from anigui.backend.worker import download_manager
        count = 0
        for ep in ep_list:
            ep_str = ep["number_str"]
            file_path = os.path.join(download_dir, f"{safe_title}_Ep_{ep_str}.mp4")
            
            # Skip if already exists on disk
            if os.path.exists(file_path):
                continue
                
            download_id = db.add_download(
                anime_id=self.anime_id,
                anime_title=self.title,
                episode_str=ep_str,
                file_path=file_path,
                size=0
            )
            download_manager.start_download(download_id, self.anime_id, ep_str, translation_type, file_path)
            count += 1
            
        if count > 0:
            self.status_label.setText(f"Queued {count} new episodes for download.")
            self.status_label.setStyleSheet(apply_theme("color: #c084fc;"))
        else:
            self.status_label.setText("All episodes already exist on disk.")
            self.status_label.setStyleSheet(apply_theme("color: #888888;"))

class AnimeDetailDialog(QDialog):
    """Popup wrapper for AnimeDetailWidget for backward compatibility."""
    def __init__(self, anime_data: dict, parent=None):
        super().__init__(parent)
        title = anime_data.get("name") or anime_data.get("anime_title") or "Unknown Title"
        self.setWindowTitle(f"AniGUI — {title}")
        self.setMinimumSize(600, 500)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.detail_widget = AnimeDetailWidget(anime_data, self)
        self.layout.addWidget(self.detail_widget)
