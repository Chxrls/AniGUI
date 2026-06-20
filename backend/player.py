import platform
import subprocess
from anigui.utils.paths import get_mpv_path

def check_mpv_installed() -> bool:
    return get_mpv_path() is not None

def launch_player(url: str, episode_label: str, referer: str = "https://allmanga.to") -> None:
    from anigui.backend.db import db
    player_path = db.get_setting("player_path", "mpv")
    hwdec_enabled = db.get_setting("hwdec_enabled", "false")
    default_quality = db.get_setting("default_quality", "auto")
    
    # Resolve bundled MPV when using the default setting
    if player_path == "mpv":
        resolved = get_mpv_path()
        if resolved:
            player_path = resolved
    
    cmd = [player_path]
    is_mpv = "mpv" in player_path.lower()
    
    if is_mpv:
        cmd.extend([
            "--no-terminal",
            f"--http-header-fields=Referer: {referer}",
            f"--title={episode_label}",
        ])
        if hwdec_enabled == "true":
            cmd.append("--hwdec=auto")
        if default_quality != "auto":
            cmd.append(f"--ytdl-format=bestvideo[height<=?{default_quality}]+bestaudio/best")
            
    cmd.append(url)

    try:
        kwargs = {"start_new_session": True}
        if platform.system() == "Windows":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs["startupinfo"] = si

        subprocess.Popen(cmd, **kwargs)
    except FileNotFoundError:
        raise RuntimeError(f"Player '{player_path}' not found. Check your settings or PATH.")
    except OSError as e:
        raise RuntimeError(f"Failed to launch player: {e}")
