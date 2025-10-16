from pathlib import Path
from .theme import THEME

def apply(app):
    qss = Path(__file__).with_name("style_base.qss").read_text(encoding="utf-8")
    qss = qss.format(
        BG=THEME.bg,
        SURFACE=THEME.surface,
        SURFACE_ALT=THEME.surface_alt,
        BORDER=THEME.border,
        TEXT=THEME.text,
        TEXT_MUTED=THEME.text_muted,
        TEXT_DISABLED=THEME.text_disabled,
        PRIMARY_START=THEME.primary_start,
        PRIMARY_MID=THEME.primary_mid,
        PRIMARY_END=THEME.primary_end,
    )
    app.setStyleSheet(qss)
