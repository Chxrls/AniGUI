import os
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Any, Optional

DB_DIR = os.path.expanduser("~/.config/anigui")
DB_PATH = os.path.join(DB_DIR, "anigui.db")

class Database:
    """Helper to manage local SQLite databases thread-safely by creating
    new connections per thread via threading.local.
    """
    def __init__(self):
        os.makedirs(DB_DIR, exist_ok=True)
        self._local = threading.local()
        self.init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    def init_tables(self):
        with self._get_conn() as conn:
            # Watch history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS watch_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    anime_id TEXT,
                    anime_title TEXT,
                    episode_str TEXT,
                    translation_type TEXT,
                    position REAL DEFAULT 0,
                    duration REAL DEFAULT 0,
                    watched INTEGER DEFAULT 0,
                    watched_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Migration check
            try:
                conn.execute("ALTER TABLE watch_history ADD COLUMN position REAL DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE watch_history ADD COLUMN duration REAL DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE watch_history ADD COLUMN watched INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass

            # Bookmarks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    anime_id TEXT UNIQUE,
                    anime_title TEXT,
                    thumbnail_url TEXT,
                    sub_count INTEGER,
                    dub_count INTEGER,
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Downloads table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    anime_id TEXT,
                    anime_title TEXT,
                    episode_str TEXT,
                    file_path TEXT,
                    file_size_bytes INTEGER,
                    status TEXT DEFAULT 'queued',
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # GraphQL and other API query cache table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    expires_at TIMESTAMP
                )
            """)
            # Settings table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    # Watch History API
    def add_watch_history(self, anime_id: str, anime_title: str, episode_str: str, translation_type: str):
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                SELECT id FROM watch_history 
                WHERE anime_id = ? AND episode_str = ? AND translation_type = ?
                LIMIT 1
                """,
                (anime_id, episode_str, translation_type)
            )
            row = cur.fetchone()
            if row:
                conn.execute(
                    "UPDATE watch_history SET watched_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (row["id"],)
                )
            else:
                conn.execute(
                    """
                    INSERT INTO watch_history (anime_id, anime_title, episode_str, translation_type)
                    VALUES (?, ?, ?, ?)
                    """,
                    (anime_id, anime_title, episode_str, translation_type)
                )
            conn.commit()

    def save_playback_position(self, anime_id: str, anime_title: str, episode_str: str, position: float, duration: float, translation_type: str = "sub"):
        watched = 1 if (duration > 0 and position / duration >= 0.8) else 0
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                SELECT id FROM watch_history 
                WHERE anime_id = ? AND episode_str = ? AND translation_type = ?
                LIMIT 1
                """,
                (anime_id, episode_str, translation_type)
            )
            row = cur.fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE watch_history 
                    SET position = ?, duration = ?, watched = CASE WHEN ? = 1 THEN 1 ELSE watched END, watched_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (position, duration, watched, row["id"])
                )
            else:
                conn.execute(
                    """
                    INSERT INTO watch_history (anime_id, anime_title, episode_str, translation_type, position, duration, watched)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (anime_id, anime_title, episode_str, translation_type, position, duration, watched)
                )
            conn.commit()
            
        if watched == 1 and self.get_setting("auto_delete_downloads", "false") == "true":
            self.auto_delete_download(anime_id, episode_str)

    def auto_delete_download(self, anime_id: str, episode_str: str):
        import os
        with self._get_conn() as conn:
            cur = conn.execute(
                "SELECT id, file_path FROM downloads WHERE anime_id = ? AND episode_str = ?",
                (anime_id, episode_str)
            )
            rows = cur.fetchall()
            for row in rows:
                file_path = row["file_path"]
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"Error auto-deleting file {file_path}: {e}")
                conn.execute("DELETE FROM downloads WHERE id = ?", (row["id"],))
            conn.commit()

    def get_playback_position(self, anime_id: str, episode_str: str, translation_type: str = "sub") -> float:
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                SELECT position FROM watch_history
                WHERE anime_id = ? AND episode_str = ? AND translation_type = ?
                LIMIT 1
                """,
                (anime_id, episode_str, translation_type)
            )
            row = cur.fetchone()
            return row["position"] if row else 0.0

    def is_watched(self, anime_id: str, episode_str: str, translation_type: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                SELECT 1 FROM watch_history 
                WHERE anime_id = ? AND episode_str = ? AND translation_type = ?
                LIMIT 1
                """,
                (anime_id, episode_str, translation_type)
            )
            return cur.fetchone() is not None

    def get_last_watched_episode(self, anime_id: str) -> Optional[str]:
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                SELECT episode_str FROM watch_history
                WHERE anime_id = ?
                ORDER BY watched_at DESC
                LIMIT 1
                """,
                (anime_id,)
            )
            row = cur.fetchone()
            return row["episode_str"] if row else None

    def get_recent_watch_history(self, limit: int = 5) -> list[dict]:
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                SELECT * FROM watch_history
                ORDER BY watched_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cur.fetchall()]

    def get_recent_unique_watch_history(self, limit: int = 10) -> list[dict]:
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                SELECT anime_id, anime_title, episode_str, translation_type,
                       MAX(watched_at) AS watched_at
                FROM watch_history
                GROUP BY anime_id
                ORDER BY MAX(watched_at) DESC
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cur.fetchall()]

    # Bookmarks API
    def add_bookmark(self, anime_id: str, anime_title: str, thumbnail_url: str, sub_count: int, dub_count: int):
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO bookmarks (anime_id, anime_title, thumbnail_url, sub_count, dub_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (anime_id, anime_title, thumbnail_url, sub_count, dub_count)
            )
            conn.commit()

    def remove_bookmark(self, anime_id: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM bookmarks WHERE anime_id = ?", (anime_id,))
            conn.commit()

    def is_bookmarked(self, anime_id: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT 1 FROM bookmarks WHERE anime_id = ? LIMIT 1", (anime_id,))
            return cur.fetchone() is not None

    def get_bookmarks(self) -> list[dict]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT * FROM bookmarks ORDER BY added_at DESC")
            return [dict(row) for row in cur.fetchall()]

    # Downloads API
    def add_download(self, anime_id: str, anime_title: str, episode_str: str, file_path: str, size: int = 0) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO downloads (anime_id, anime_title, episode_str, file_path, file_size_bytes, status)
                VALUES (?, ?, ?, ?, ?, 'queued')
                """,
                (anime_id, anime_title, episode_str, file_path, size)
            )
            conn.commit()
            return cur.lastrowid

    def update_download_status(self, download_id: int, status: str, size: int = 0):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE downloads SET status = ?, file_size_bytes = ? WHERE id = ?",
                (status, size, download_id)
            )
            conn.commit()

    def get_downloads(self) -> list[dict]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT * FROM downloads ORDER BY added_at DESC")
            return [dict(row) for row in cur.fetchall()]

    def remove_download(self, download_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM downloads WHERE id = ?", (download_id,))
            conn.commit()

    # Caching API
    def get_cached(self, key: str) -> Optional[str]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT value, expires_at FROM api_cache WHERE key = ?", (key,))
            row = cur.fetchone()
            if row:
                expires_at = datetime.fromisoformat(row["expires_at"])
                if datetime.now() < expires_at:
                    return row["value"]
                else:
                    # Expired, clean up
                    conn.execute("DELETE FROM api_cache WHERE key = ?", (key,))
                    conn.commit()
            return None

    def set_cached(self, key: str, value: str, ttl_seconds: int = 86400):
        with self._get_conn() as conn:
            expires_at = (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat()
            conn.execute(
                """
                INSERT OR REPLACE INTO api_cache (key, value, expires_at)
                VALUES (?, ?, ?)
                """,
                (key, value, expires_at)
            )
            conn.commit()

    def clear_cache(self):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM api_cache")
            conn.commit()

    def get_db_size(self) -> int:
        if os.path.exists(DB_PATH):
            return os.path.getsize(DB_PATH)
        return 0

    # Settings API
    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cur.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO settings (key, value)
                VALUES (?, ?)
                """,
                (key, value)
            )
            conn.commit()

# Single global instance
db = Database()
