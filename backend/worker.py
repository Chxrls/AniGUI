import os
import subprocess
import hashlib
import requests
import psutil
import re
from PyQt6.QtCore import QRunnable, QObject, pyqtSignal, QThreadPool
from anigui.backend.api import search_anime, get_anilist_metadata, resolve_stream_url, fetch_top_ranked, search_anilist

def parse_time(time_str: str) -> float:
    try:
        h, m, s = time_str.split(':')
        return int(h) * 3600 + int(m) * 60 + float(s)
    except:
        return 0.0

THUMB_DIR = os.path.expanduser("~/.config/anigui/thumbnails")

_active_workers = set()

def start_worker(worker):
    """Start a QRunnable worker while keeping its Python object alive.
    
    Prevents 'wrapped C/C++ object of type WorkerSignals has been deleted'
    by keeping a strong Python reference until the worker finishes or errors.
    """
    _active_workers.add(worker)
    
    def cleanup(*args):
        _active_workers.discard(worker)
        
    if hasattr(worker, 'signals'):
        worker.signals.finished.connect(cleanup)
        worker.signals.error.connect(cleanup)
        
    QThreadPool.globalInstance().start(worker)

class WorkerSignals(QObject):
    """Container for signals emitted by the background workers."""
    finished = pyqtSignal(object)  # Can be list, dict, str, etc.
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

class DownloadManager(QObject):
    progress_updated = pyqtSignal(int, dict)
    status_changed = pyqtSignal(int, str)
    
    def __init__(self):
        super().__init__()
        self.active_workers = {}
        self.thread_pool = QThreadPool()
        from anigui.backend.db import db
        max_downloads = int(db.get_setting("max_concurrent_downloads", "3"))
        self.thread_pool.setMaxThreadCount(max_downloads)
        
    def update_max_downloads(self, count: int):
        self.thread_pool.setMaxThreadCount(count)
        

    def start_download(self, download_id, anime_id, ep_str, translation_type, file_path,
                       anilist_id=None, miruro_provider=None):
        from anigui.backend.db import db
        from anigui.backend.worker import DownloadWorker
        worker = DownloadWorker(
            download_id, anime_id, ep_str, translation_type, file_path,
            anilist_id=anilist_id, miruro_provider=miruro_provider,
        )
        self.active_workers[download_id] = worker
        db.update_download_status(download_id, "downloading")
        self.status_changed.emit(download_id, "downloading")
        self.thread_pool.start(worker)
        
    def pause_download(self, download_id):
        worker = self.active_workers.get(download_id)
        if worker and hasattr(worker, 'proc') and worker.proc:
            try:
                p = psutil.Process(worker.proc.pid)
                p.suspend()
                from anigui.backend.db import db
                db.update_download_status(download_id, "paused")
                self.status_changed.emit(download_id, "paused")
            except Exception as e:
                print(f"Error suspending: {e}")
                
    def resume_download(self, download_id):
        worker = self.active_workers.get(download_id)
        if worker and hasattr(worker, 'proc') and worker.proc:
            try:
                p = psutil.Process(worker.proc.pid)
                p.resume()
                from anigui.backend.db import db
                db.update_download_status(download_id, "downloading")
                self.status_changed.emit(download_id, "downloading")
            except Exception as e:
                print(f"Error resuming: {e}")

    def cancel_download(self, download_id):
        worker = self.active_workers.get(download_id)
        if worker and hasattr(worker, 'proc') and worker.proc:
            try:
                p = psutil.Process(worker.proc.pid)
                p.kill()
                from anigui.backend.db import db
                db.update_download_status(download_id, "failed")
                self.status_changed.emit(download_id, "failed")
            except Exception as e:
                print(f"Error killing: {e}")

download_manager = DownloadManager()

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

class FilteredSearchWorker(QRunnable):
    """Worker to perform a filtered AniList search.
 
    Used by SearchView when any filter (genre, season, year, format,
    status) is active, with or without a text query.  Results are AniList
    media dicts — rich metadata included, no AllAnime streaming ID.
    The ID is resolved lazily at click time via AllAnimeResolveWorker.
 
    Parameters
    ----------
    query    : optional text search string
    genres   : list of AniList genre strings  e.g. ["Action", "Fantasy"]
    season   : AniList season enum            e.g. "WINTER"
    year     : season year integer            e.g. 2024
    fmt      : AniList format enum            e.g. "TV"
    status   : AniList status enum            e.g. "RELEASING"
    """
    def __init__(
        self,
        query:   str | None       = None,
        genres:  list[str] | None = None,
        season:  str | None       = None,
        year:    int | None       = None,
        fmt:     str | None       = None,
        status:  str | None       = None,
    ):
        super().__init__()
        self.query  = query
        self.genres = genres
        self.season = season
        self.year   = year
        self.fmt    = fmt
        self.status = status
        self.signals = WorkerSignals()
 
    def run(self):
        try:
            results = search_anilist(
                query=self.query,
                genres=self.genres,
                season=self.season,
                year=self.year,
                format=self.fmt,
                status=self.status,
            )
            self.signals.finished.emit(results)
        except Exception as e:
            self.signals.error.emit(str(e))


class DefaultResultsWorker(QRunnable):
    """Worker to fetch the top 40 ranked anime from AniList.
 
    Used by SearchView to populate the grid before the user has typed
    anything.  Results are AniList media dicts (not AllAnime dicts) so
    SearchView must handle them differently from SearchWorker results —
    they contain rich metadata (cover URL, genres, score) but no AllAnime
    streaming ID.  The ID is resolved lazily at click time via
    AllAnimeResolveWorker (same pattern as HomeView).
    """
    def __init__(self, per_page: int = 40):
        super().__init__()
        self.per_page = per_page
        self.signals = WorkerSignals()

    def run(self):
        try:
            results = fetch_top_ranked(per_page=self.per_page)
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
    """Worker to resolve direct stream HLS/MP4 link.

    Tries Miruro first (when *anilist_id* is provided), then falls back
    to AllAnime.
    """
    def __init__(self, anime_id: str, episode_str: str, translation_type: str,
                 anilist_id: int | None = None, miruro_provider: str | None = None):
        super().__init__()
        self.anime_id = anime_id
        self.episode_str = episode_str
        self.translation_type = translation_type
        self.anilist_id = anilist_id
        self.miruro_provider = miruro_provider
        self.signals = WorkerSignals()

    def run(self):
        try:
            url, referer = resolve_stream_url(
                self.anime_id, 
                self.episode_str, 
                self.translation_type,
                progress_callback=self.signals.progress.emit,
                anilist_id=self.anilist_id,
                miruro_provider=self.miruro_provider,
            )
            self.signals.finished.emit((url, referer))
        except Exception as e:
            self.signals.error.emit(str(e))

class DownloadWorker(QRunnable):
    """Worker to download an episode HLS stream to an mp4 file using ffmpeg."""
    def __init__(self, download_id: int, anime_id: str, episode_str: str, translation_type: str, file_path: str,
                 anilist_id: int | None = None, miruro_provider: str | None = None):
        super().__init__()
        self.download_id = download_id
        self.anime_id = anime_id
        self.episode_str = episode_str
        self.translation_type = translation_type
        self.file_path = file_path
        self.anilist_id = anilist_id
        self.miruro_provider = miruro_provider
        self.signals = WorkerSignals()

    def run(self):
        from anigui.backend.db import db
        try:
            print(f"Worker thread started for download ID {self.download_id}", flush=True)
            
            # Resolve stream URL
            print(f"Resolving stream URL for {self.anime_id} Episode {self.episode_str}...", flush=True)
            url, referer = resolve_stream_url(
                self.anime_id, self.episode_str, self.translation_type,
                anilist_id=self.anilist_id, miruro_provider=self.miruro_provider,
            )
            if not url:
                raise ValueError("Stream URL resolution failed.")
            print(f"URL resolved. Beginning download...", flush=True)

            # Download using ffmpeg
            cmd = [
                "ffmpeg",
                "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "-headers", f"Referer: {referer}\r\n",
                "-y",
                "-i", url,
                "-c", "copy",
                "-bsf:a", "aac_adtstoasc",
                self.file_path
            ]
            
            print(f"Running ffmpeg for {self.file_path}", flush=True)
            
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            self.proc = subprocess.Popen(
                cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.PIPE, 
                text=True, 
                universal_newlines=True, 
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo
            )
            
            duration_pattern = re.compile(r"Duration:\s*(\d{2}:\d{2}:\d{2}\.\d{2})")
            progress_pattern = re.compile(r"size=\s*(\d+[kKmMgG]?i?B|\d+)\s+time=(\d{2}:\d{2}:\d{2}\.\d{2})\s+bitrate=([\d\.]+kbits/s)")
            
            duration_secs = 0.0
            
            for line in self.proc.stderr:
                if duration_secs == 0.0:
                    dur_match = duration_pattern.search(line)
                    if dur_match:
                        duration_secs = parse_time(dur_match.group(1))
                
                prog_match = progress_pattern.search(line)
                if prog_match:
                    size_str = prog_match.group(1)
                    time_str = prog_match.group(2)
                    bitrate = prog_match.group(3)
                    
                    current_secs = parse_time(time_str)
                    percentage = int((current_secs / duration_secs) * 100) if duration_secs > 0 else 0
                    if percentage > 100: percentage = 100
                    
                    download_manager.progress_updated.emit(self.download_id, {
                        "size": size_str,
                        "time": time_str,
                        "bitrate": bitrate,
                        "percentage": percentage
                    })
                    
            self.proc.wait()
            if self.proc.returncode != 0:
                raise RuntimeError(f"ffmpeg error exit code: {self.proc.returncode}")

            # Get final file size and update status
            file_size = os.path.getsize(self.file_path)
            db.update_download_status(self.download_id, "completed", file_size)
            download_manager.status_changed.emit(self.download_id, "completed")
            
            self.signals.finished.emit(self.file_path)
        except Exception as e:
            db.update_download_status(self.download_id, "failed")
            download_manager.status_changed.emit(self.download_id, "failed")
            self.signals.error.emit(str(e))
