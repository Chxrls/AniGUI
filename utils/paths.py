"""Centralized path resolution for bundled assets (MPV, app icon).

When running from a PyInstaller bundle the executable directory is used
as the root for locating ``vendor/mpv/mpv.exe`` and ``repoAssets/logo.ico``.
During development the project root is used instead, with a final fallback
to the system PATH for MPV.
"""

import os
import sys
import shutil


def _app_root() -> str:
    """Return the application root directory for data files.

    * **Frozen (PyInstaller)** – ``sys._MEIPASS`` (the ``_internal`` folder
      where PyInstaller unpacks bundled data).
    * **Development** – directory containing the top-level ``main.py``.
    """
    if getattr(sys, "frozen", False):
        # PyInstaller puts datas under _MEIPASS (_internal/ subfolder)
        return sys._MEIPASS
    # Development: this file is at <project>/utils/paths.py
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_mpv_path() -> str | None:
    """Resolve the MPV executable path.

    Resolution order:
    1. Bundled ``vendor/mpv/mpv.exe`` relative to the app root.
    2. System PATH via ``shutil.which``.

    Returns the absolute path string, or *None* if MPV cannot be found.
    """
    bundled = os.path.join(_app_root(), "vendor", "mpv", "mpv.exe")
    if os.path.isfile(bundled):
        return bundled
    return shutil.which("mpv")


def get_icon_path() -> str | None:
    """Resolve the application icon path.

    Looks for ``repoAssets/logo.ico`` relative to the app root.
    Returns *None* if the file does not exist.
    """
    icon = os.path.join(_app_root(), "repoAssets", "logo.ico")
    if os.path.isfile(icon):
        return icon
    return None
