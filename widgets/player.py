from anigui.backend.api import launch_player as backend_launch_player
from anigui.backend.db import db

def launch_player_and_save_history(
    url: str, 
    anime_id: str, 
    anime_title: str, 
    episode_str: str, 
    translation_type: str,
    referer: str = "https://allmanga.to"
):
    """Wrapper that calls launch_player to play the video in mpv, and

    records the watch progress to local SQLite.
    """
    episode_label = f"{anime_title} Ep {episode_str}"
    
    # Launch player
    backend_launch_player(url, episode_label, referer)
    
    # Write to watch history DB immediately after launching
    db.add_watch_history(
        anime_id=anime_id,
        anime_title=anime_title,
        episode_str=episode_str,
        translation_type=translation_type
    )
