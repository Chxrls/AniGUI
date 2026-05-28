from anigui.utils.theme import apply_theme
import os
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QWidget
from PyQt6.QtCore import pyqtSignal, Qt, QThreadPool
from PyQt6.QtGui import QPixmap, QPainter, QColor
from anigui.backend.worker import MetadataWorker, ThumbnailWorker

def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len characters, appending '…' if trimmed."""
    return text if len(text) <= max_len else text[:max_len - 1] + "…"

class AnimeCard(QFrame):
    """Custom widget displaying an anime cover image, title, and metadata.

    Fetches AniList cover images and synopsis asynchronously.
    """
    clicked = pyqtSignal(dict)  # Emits the updated anime data dict when clicked

    def __init__(self, anime_data: dict, parent: QWidget = None):
        super().__init__(parent)
        self.anime_data = anime_data.copy()
        
        # Determine core properties
        self.anime_id = self.anime_data.get("id") or self.anime_data.get("anime_id")
        self.title = self.anime_data.get("name") or self.anime_data.get("anime_title") or "Unknown Title"
        self.english_name = self.anime_data.get("english_name", "")
        
        # Sub/Dub counts
        self.sub_count = self.anime_data.get("sub_count", 0)
        self.dub_count = self.anime_data.get("dub_count", 0)
        
        # Setup dialog-specific fields
        self.synopsis = ""
        self.genres = []
        self.score = 0
        self.banner_url = ""
        
        # UI Setup
        self.setFixedWidth(180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("AnimeCard")
        
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(6)
        
        # Thumbnail area (fixed 180px card width, image width ~164px, aspect ratio ~1.5)
        self.image_label = QLabel(self)
        self.image_label.setFixedSize(164, 246)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setObjectName("CardImage")
        
        # Placeholder style while loading
        self.image_label.setStyleSheet(apply_theme("background-color: #242424; color: #888888;"))
        self.image_label.setText("Loading...")
        self.layout.addWidget(self.image_label)
        
        # Title Label (plain text, max 2 lines)
        self.title_label = QLabel(_truncate(self.title, 28), self)
        self.title_label.setWordWrap(True)
        self.title_label.setObjectName("CardTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        # Limit height to roughly 2 lines
        self.title_label.setMaximumHeight(40)
        self.layout.addWidget(self.title_label)
        
        # Episode / Sub-Dub counts
        ep_text = f"Sub: {self.sub_count} eps"
        if self.dub_count > 0:
            ep_text += f" | Dub: {self.dub_count} eps"
        if self.anime_data.get("last_watched"):
            ep_text += f"\nLast: Ep {self.anime_data['last_watched']}"
        self.ep_label = QLabel(ep_text, self)
        self.ep_label.setObjectName("CardMetadata")
        self.layout.addWidget(self.ep_label)
        
        # Start async metadata/thumbnail retrieval
        self.load_metadata()

    def load_metadata(self):
        # Check if we already have a thumbnail cached locally (e.g. from local DB)
        saved_thumb = self.anime_data.get("thumbnail_url")
        if saved_thumb and not saved_thumb.startswith("http"):
            # It's already a local file path
            self.set_image_from_path(saved_thumb)
            return

        # Fetch AniList metadata
        worker = MetadataWorker(self.title)
        worker.signals.finished.connect(self._on_metadata_loaded)
        worker.signals.error.connect(self._on_metadata_failed)
        QThreadPool.globalInstance().start(worker)

    def _on_metadata_loaded(self, meta: dict):
        if not meta:
            self._on_metadata_failed("No metadata found")
            return
            
        # Store metadata details
        self.synopsis = meta.get("description") or ""
        self.genres = meta.get("genres") or []
        self.score = meta.get("averageScore") or 0
        self.banner_url = meta.get("bannerImage") or ""
        
        # Update anime data dictionary
        self.anime_data["synopsis"] = self.synopsis
        self.anime_data["genres"] = self.genres
        self.anime_data["score"] = self.score
        self.anime_data["banner_url"] = self.banner_url
        
        # If english title is available and different, save it
        eng_title = meta.get("title", {}).get("english")
        if eng_title and eng_title.lower() != self.title.lower():
            self.english_name = eng_title
            self.anime_data["english_name"] = eng_title

        # Load cover image
        cover_image_url = None
        cover_data = meta.get("coverImage", {})
        if cover_data:
            cover_image_url = cover_data.get("extraLarge") or cover_data.get("large")
            
        if cover_image_url:
            self.anime_data["thumbnail_url"] = cover_image_url
            thumb_worker = ThumbnailWorker(cover_image_url)
            thumb_worker.signals.finished.connect(self.set_image_from_path)
            QThreadPool.globalInstance().start(thumb_worker)
        else:
            self._on_metadata_failed("No cover image URL")

    def _on_metadata_failed(self, err_msg: str):
        # Fallback to grey placeholder with truncated title centered
        self.image_label.setText(self.title[:15] + "...")
        self.image_label.setStyleSheet(apply_theme("background-color: #242424; color: #888888; border: 1px dashed #2e2e2e;"))

    def set_image_from_path(self, path: str):
        if path and os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                # Scale smoothly to fit thumbnail area
                scaled = pixmap.scaled(
                    self.image_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                # Crop to fit layout
                self.image_label.setPixmap(scaled)
                # Store local path back to anime data
                self.anime_data["thumbnail_url_local"] = path
                return
        
        self._on_metadata_failed("Failed to load local thumbnail file")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.anime_data)
        super().mousePressEvent(event)
