from anigui.utils.theme import apply_theme
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, 
    QComboBox, QListWidget, QListWidgetItem, QPushButton, QWidget, QScrollArea, QMenu
)
from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtGui import QPixmap
from anigui.backend.api import fetch_episodes, get_available_providers
from anigui.backend.db import db
from anigui.backend.worker import EpisodeResolveWorker, start_worker
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
        self.anilist_id = self.anime_data.get("anilist_id") or self.anime_data.get("anilistId")
        self.title = self.anime_data.get("name") or self.anime_data.get("anime_title") or "Unknown Title"
        self.english_title = self.anime_data.get("english_name", "")
        raw_synopsis = self.anime_data.get("synopsis") or "No synopsis available."
        self.synopsis = raw_synopsis.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n").replace("<i>", "").replace("</i>", "").replace("<b>", "").replace("</b>", "").strip()
        self.genres = self.anime_data.get("genres") or []
        self.sub_count = self.anime_data.get("sub_count", 0)
        self.dub_count = self.anime_data.get("dub_count", 0)
        
        # Local thumbnail path
        self.thumb_path = self.anime_data.get("thumbnail_url_local") or ""
        
        if not self.thumb_path:
            cover_url = self.anime_data.get("thumbnail_url") or ""
            if not cover_url:
                cover_dict = self.anime_data.get("coverImage") or {}
                cover_url = cover_dict.get("large") or cover_dict.get("medium") or ""
            if cover_url:
                import hashlib
                thumb_dir = os.path.expanduser("~/.config/anigui/thumbnails")
                # Try sha256 format (worker.py ThumbnailWorker)
                sha_name = hashlib.sha256(cover_url.encode("utf-8")).hexdigest()[:16] + ".jpg"
                sha_path = os.path.join(thumb_dir, sha_name)
                # Try md5 format (home.py load_image)
                md5_name = hashlib.md5(cover_url.encode()).hexdigest() + ".jpg"
                md5_path = os.path.join(thumb_dir, md5_name)
                if os.path.exists(sha_path):
                    self.thumb_path = sha_path
                elif os.path.exists(md5_path):
                    self.thumb_path = md5_path
        
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

        # Airing status badge
        status_raw = self.anime_data.get("status") or ""
        STATUS_DISPLAY = {
            "RELEASING": ("Airing", "#16a34a", "#dcfce7"),
            "FINISHED": ("Finished", "#64748b", "#e2e8f0"),
            "NOT_YET_RELEASED": ("Upcoming", "#d97706", "#fef3c7"),
            "CANCELLED": ("Cancelled", "#dc2626", "#fee2e2"),
            "HIATUS": ("Hiatus", "#9333ea", "#f3e8ff"),
        }
        self.airing_status_label = QLabel("", self)
        self.airing_status_label.setObjectName("DetailAiringStatus")
        if status_raw in STATUS_DISPLAY:
            display_text, bg_color, text_color = STATUS_DISPLAY[status_raw]
            self.airing_status_label.setText(display_text)
            self.airing_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.airing_status_label.setStyleSheet(
                f"QLabel#DetailAiringStatus {{ background-color: {bg_color}; color: {text_color}; "
                f"font-size: 11px; font-weight: bold; padding: 4px 14px; "
                f"border-radius: 4px; }}"
            )
            self.airing_status_label.setSizePolicy(
                self.airing_status_label.sizePolicy().horizontalPolicy(),
                self.airing_status_label.sizePolicy().verticalPolicy()
            )
            self.airing_status_label.setMaximumWidth(120)
        else:
            self.airing_status_label.hide()
        info_layout.addWidget(self.airing_status_label, alignment=Qt.AlignmentFlag.AlignLeft)
        
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
        self.trans_selector.view().setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        
        # Provider selector (Miruro streaming providers)
        self.provider_selector = QComboBox(self)
        self.provider_selector.view().setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.provider_selector.setObjectName("ProviderSelector")
        self.provider_selector.addItem("Auto", None)
        for prov in get_available_providers():
            self.provider_selector.addItem(prov["name"].capitalize(), prov["name"])
        self.provider_selector.setToolTip("Streaming provider (Auto tries all in order)")
        controls_layout.addWidget(self.provider_selector)
        
        # Bookmark button
        self.bookmark_btn = QPushButton(self)
        self.bookmark_btn.setObjectName("BookmarkButton")
        self.bookmark_btn.clicked.connect(self.toggle_bookmark)
        self.update_bookmark_button_ui()
        controls_layout.addWidget(self.bookmark_btn)

        # Folder assignment dropdown
        self.folder_selector = QComboBox(self)
        self.folder_selector.view().setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.folder_selector.setObjectName("FolderSelector")
        self.folder_selector.setMinimumWidth(140)
        self.folder_selector.setFixedHeight(self.bookmark_btn.sizeHint().height())
        self._refresh_folder_selector()
        self.folder_selector.currentIndexChanged.connect(self._on_folder_selected)
        controls_layout.addWidget(self.folder_selector)

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

        # If status is not available, fetch it asynchronously from AniList
        if not status_raw and self.title:
            self._fetch_status_async()

        # Backfill anilist_id for old bookmarks if we have it now
        if db.is_bookmarked(self.anime_id) and self.anilist_id:
            db.add_bookmark(
                anime_id=self.anime_id,
                anime_title=self.title,
                thumbnail_url=self.thumb_path,
                sub_count=self.sub_count,
                dub_count=self.dub_count,
                anilist_id=self.anilist_id
            )

    def get_current_translation(self) -> str:
        return self.trans_selector.currentData() or "sub"

    def _fetch_status_async(self):
        """Fetch AniList metadata to get the airing status when not available."""
        from anigui.backend.worker import MetadataWorker, start_worker
        worker = MetadataWorker(self.title)
        worker.signals.finished.connect(self._on_status_fetched)
        start_worker(worker)

    def _on_status_fetched(self, meta: dict):
        """Update the airing status badge when metadata arrives."""
        if not meta:
            return
        status_raw = meta.get("status") or ""
        if not status_raw:
            return

        STATUS_DISPLAY = {
            "RELEASING": ("Airing", "#16a34a", "#dcfce7"),
            "FINISHED": ("Finished", "#64748b", "#e2e8f0"),
            "NOT_YET_RELEASED": ("Upcoming", "#d97706", "#fef3c7"),
            "CANCELLED": ("Cancelled", "#dc2626", "#fee2e2"),
            "HIATUS": ("Hiatus", "#9333ea", "#f3e8ff"),
        }
        if status_raw in STATUS_DISPLAY:
            display_text, bg_color, text_color = STATUS_DISPLAY[status_raw]
            self.airing_status_label.setText(display_text)
            self.airing_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.airing_status_label.setStyleSheet(
                f"QLabel#DetailAiringStatus {{ background-color: {bg_color}; color: {text_color}; "
                f"font-size: 11px; font-weight: bold; padding: 4px 14px; "
                f"border-radius: 4px; }}"
            )
            self.airing_status_label.setMaximumWidth(120)
            self.airing_status_label.show()

        # Also update genres and synopsis if they were missing
        if not self.genres and meta.get("genres"):
            self.genres = meta["genres"]
            self.genres_label.setText(f"Genres: {', '.join(self.genres)}")
        if self.synopsis == "No synopsis available." and meta.get("description"):
            raw = meta["description"]
            cleaned = raw.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
            cleaned = cleaned.replace("<i>", "").replace("</i>", "").replace("<b>", "").replace("</b>", "").strip()
            self.synopsis = cleaned
            self.synopsis_label.setText(cleaned)

        # Backfill anilist_id if it was missing and we found it
        if meta.get("id") and not self.anilist_id:
            self.anilist_id = meta["id"]
            if db.is_bookmarked(self.anime_id):
                db.add_bookmark(
                    anime_id=self.anime_id,
                    anime_title=self.title,
                    thumbnail_url=self.thumb_path,
                    sub_count=self.sub_count,
                    dub_count=self.dub_count,
                    anilist_id=self.anilist_id
                )

    def _get_selected_provider(self) -> str | None:
        """Return the currently selected Miruro provider, or None for auto."""
        return self.provider_selector.currentData()

    def load_episodes(self):
        self.episode_list_widget.clear()
        translation_type = self.get_current_translation()
        
        # Build data dict with anilist_id for Miruro resolution
        fetch_data = self.anime_data.copy()
        if self.anilist_id:
            fetch_data["anilist_id"] = self.anilist_id
        ep_list = fetch_episodes(fetch_data, translation_type)
        
        # Batch-fetch watched status in a single DB query
        watched_set = db.get_watched_episodes(self.anime_id, translation_type)
        
        for ep in ep_list:
            ep_str = ep["number_str"]
            is_watched = ep_str in watched_set
            
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
                dub_count=self.dub_count,
                anilist_id=self.anilist_id
            )
        self.update_bookmark_button_ui()
        self._refresh_folder_selector()

    def _refresh_folder_selector(self):
        """Populate the folder dropdown with available folders."""
        self.folder_selector.blockSignals(True)
        self.folder_selector.clear()
        self.folder_selector.addItem("Add to folder...", None)

        folders = db.get_bookmark_folders()
        if not folders:
            self.folder_selector.setItemText(0, "No folders yet")
            self.folder_selector.blockSignals(False)
            return

        current_folder_ids = db.get_folders_for_bookmark(self.anime_id)
        for folder in folders:
            prefix = "✓  " if folder["id"] in current_folder_ids else ""
            self.folder_selector.addItem(f"{prefix}📁 {folder['name']}", folder["id"])

        self.folder_selector.setCurrentIndex(0)
        self.folder_selector.blockSignals(False)

    def _on_folder_selected(self, index: int):
        """Handle folder selection from the dropdown."""
        if index <= 0:
            return

        folder_id = self.folder_selector.currentData()
        if folder_id is None:
            return

        # Auto-bookmark if not already bookmarked
        if not db.is_bookmarked(self.anime_id):
            db.add_bookmark(
                anime_id=self.anime_id,
                anime_title=self.title,
                thumbnail_url=self.thumb_path,
                sub_count=self.sub_count,
                dub_count=self.dub_count,
                anilist_id=self.anilist_id
            )
            self.update_bookmark_button_ui()

        # Toggle folder assignment
        current_folder_ids = db.get_folders_for_bookmark(self.anime_id)
        if folder_id in current_folder_ids:
            db.remove_bookmark_from_folder(folder_id, self.anime_id)
        else:
            db.add_bookmark_to_folder(folder_id, self.anime_id)

        # Refresh dropdown to reflect changes
        self._refresh_folder_selector()

    def play_selected_episode(self, item: QListWidgetItem):
        ep_data = item.data(Qt.ItemDataRole.UserRole)
        if not ep_data:
            return
            
        ep_str = ep_data["number_str"]
        translation_type = self.get_current_translation()
        
        self.status_label.setText("Resolving stream URL...")
        self.status_label.setStyleSheet(apply_theme("color: #c084fc;"))  # Accent status
        
        # Store reference to the clicked item for targeted badge update
        self._playing_item = item
        
        # Async stream resolution (Miruro-first when anilist_id available)
        worker = EpisodeResolveWorker(
            self.anime_id, ep_str, translation_type,
            anilist_id=self.anilist_id,
            miruro_provider=self._get_selected_provider(),
        )
        worker.signals.progress.connect(self._on_stream_progress)
        worker.signals.finished.connect(lambda result: self._on_stream_resolved(result, ep_str, translation_type))
        worker.signals.error.connect(self._on_stream_failed)
        start_worker(worker)

    def _on_stream_progress(self, message: str):
        self.status_label.setText(message)
        self.status_label.setStyleSheet(apply_theme("color: #a78bfa;"))

    def _on_stream_resolved(self, result, ep_str: str, translation_type: str):
        try:
            url, referer = result
            self.status_label.setText("Success")
            self.status_label.setStyleSheet(apply_theme("color: #10b981;"))
        except RuntimeError:
            return  # View was closed while resolving

        
        try:
            # Play using mpv and record watched log
            launch_player_and_save_history(
                url=url,
                anime_id=self.anime_id,
                anime_title=self.title,
                episode_str=ep_str,
                translation_type=translation_type,
                referer=referer,
                anilist_id=self.anilist_id
            )
            # Update only the played episode's badge instead of rebuilding
            # the entire list (avoids N individual DB queries on main thread)
            self._mark_episode_watched(ep_str)
        except Exception as e:
            self._on_stream_failed(str(e))

    def _mark_episode_watched(self, ep_str: str):
        """Update the watched badge on a single episode item without
        rebuilding the entire episode list widget."""
        item = getattr(self, "_playing_item", None)
        if item is not None:
            label = self.episode_list_widget.itemWidget(item)
            if label and isinstance(label, QLabel):
                current_text = label.text()
                if "[Watched]" not in current_text:
                    label.setText(f"Ep {ep_str} <font color='#888888'>[Watched]</font>")
            self._playing_item = None

    def _on_stream_failed(self, err_msg: str):
        # Truncate long error messages to keep the status label readable;
        # raw API errors can include URLs with long hashes.
        clean = err_msg.split("\n")[0]  # Take first line only
        if len(clean) > 80:
            clean = clean[:77] + "…"
        self.status_label.setText(f"Error: {clean}")
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
        miruro_provider = self._get_selected_provider()
        
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
            size=0,
            anilist_id=self.anilist_id,
            translation_type=translation_type,
            miruro_provider=miruro_provider,
        )
        
        from anigui.backend.worker import download_manager, start_worker
        download_manager.start_download(
            download_id, self.anime_id, ep_str, translation_type, file_path,
            anilist_id=self.anilist_id, miruro_provider=miruro_provider,
        )
        
        self.status_label.setText(f"Started downloading Ep {ep_str}.")
        self.status_label.setStyleSheet(apply_theme("color: #c084fc;"))

    def queue_download_all(self):
        translation_type = self.get_current_translation()
        miruro_provider = self._get_selected_provider()
        
        # Ensure anilist_id is injected for Miruro resolution
        fetch_data = self.anime_data.copy()
        if self.anilist_id:
            fetch_data["anilist_id"] = self.anilist_id
        ep_list = fetch_episodes(fetch_data, translation_type)
        if not ep_list:
            self.status_label.setText("No episodes found to download.")
            self.status_label.setStyleSheet(apply_theme("color: #f87171;"))
            return
            
        download_dir = db.get_setting("download_path", "~/Downloads")
        download_dir = os.path.expanduser(download_dir)
        os.makedirs(download_dir, exist_ok=True)
        
        safe_title = "".join([c for c in self.title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        
        from anigui.backend.worker import download_manager, start_worker
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
                size=0,
                anilist_id=self.anilist_id,
                translation_type=translation_type,
                miruro_provider=miruro_provider,
            )
            download_manager.start_download(
                download_id, self.anime_id, ep_str, translation_type, file_path,
                anilist_id=self.anilist_id, miruro_provider=miruro_provider,
            )
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
