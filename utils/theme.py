import re
from anigui.backend.db import db

# Base colors from dark theme to light theme (Slate UI palette)
THEME_COLORS = {
    '#0f0f0f': '#f8fafc',  # Main background -> Slate 50
    '#1a1a1a': '#f1f5f9',  # Sidebar/Card/Boxes -> Slate 100
    '#2e2e2e': '#cbd5e1',  # Borders -> Slate 300
    '#e8e8e8': '#0f172a',  # Text -> Slate 900
    '#888888': '#64748b',  # Dim Text -> Slate 500
    '#c084fc': '#8b5cf6',  # Accent color -> Violet 500
    '#242424': '#e2e8f0',  # Hover bg / Alternating -> Slate 200
    'white': '#0f172a',    # Explicit white text to dark slate
    '#ffffff': '#0f172a',  # Explicit #ffffff to dark slate
}

def apply_theme(qss_text: str) -> str:
    """Takes a stylesheet string containing dark hex colors and converts them to light hex colors if the light theme is active."""
    theme = db.get_setting("theme", "dark")
    if theme == "dark":
        return qss_text
        
    # Build regex pattern for single-pass replacement
    patterns = []
    for k in THEME_COLORS.keys():
        if k.isalpha():
            patterns.append(r'\b' + re.escape(k) + r'\b')
        else:
            patterns.append(re.escape(k))
            
    regex = re.compile('|'.join(patterns), re.IGNORECASE)
    
    def replacer(match):
        key = match.group(0).lower()
        return THEME_COLORS.get(key, match.group(0))
        
    return regex.sub(replacer, qss_text)
