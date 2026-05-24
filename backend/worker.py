import os
import hashlib
import requests
from PyQt6.QtCore import QRunnable, QObject, pyqtSignal
from anigui.backend.api import search_anime, get_anilist_metadata, resolve_stream_url

THUMB_DIR = os.path.expanduser("~/.config/anigui/thumbnails")

class WorkerSignals(QObject):
    """Container for signals emitted by the background workers."""
    finished = pyqtSignal(object)  # Can be list, dict, str, etc.
    error = pyqtSignal(str)

class SearchWorker(QRunnable):
    """Worker to perform non-blocking AllAnime searches."""
    def __init__(self, query: str):
        super().__init__()
        self.query = query
        self.signals = WorkerSignals()

    def run(self):
        try:
            results = search_anime(self.query)
            self.signals.finished.emit(results)
        except Exception as e:
            self.signals.error.emit(str(e))

class MetadataWorker(QRunnable):
    """Worker to fetch metadata for a single anime from AniList."""
    def __init__(self, title: str):
        super().__init__()
        self.title = title
        self.signals = WorkerSignals()

    def run(self):
        try:
            meta = get_anilist_metadata(self.title)
            self.signals.finished.emit(meta)
        except Exception as e:
            self.signals.error.emit(str(e))

class ThumbnailWorker(QRunnable):
    """Worker to fetch and cache cover images to local disk.

    Saves files to ~/.config/anigui/thumbnails/<hash>.jpg.
    Emits the local file path on success.
    """
    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self.signals = WorkerSignals()

    def run(self):
        if not self.url:
            self.signals.finished.emit(None)
            return

        try:
            os.makedirs(THUMB_DIR, exist_ok=True)
            
            # Hash thumbnail URL for caching
            url_hash = hashlib.sha256(self.url.encode("utf-8")).hexdigest()[:16]
            filepath = os.path.join(THUMB_DIR, f"{url_hash}.jpg")

            # Check cache
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                self.signals.finished.emit(filepath)
                return

            # Download
            resp = requests.get(self.url, timeout=10)
            resp.raise_for_status()

            with open(filepath, "wb") as f:
                f.write(resp.content)

            self.signals.finished.emit(filepath)
        except Exception as e:
            self.signals.error.emit(str(e))

class EpisodeResolveWorker(QRunnable):
    """Worker to resolve direct stream HLS/MP4 link from AllAnime."""
    def __init__(self, anime_id: str, episode_str: str, translation_type: str):
        super().__init__()
        self.anime_id = anime_id
        self.episode_str = episode_str
        self.translation_type = translation_type
        self.signals = WorkerSignals()

    def run(self):
        try:
            url = resolve_stream_url(self.anime_id, self.episode_str, self.translation_type)
            self.signals.finished.emit(url)
        except Exception as e:
            self.signals.error.emit(str(e))
