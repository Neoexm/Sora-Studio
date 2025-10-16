from dataclasses import dataclass

@dataclass(frozen=True)
class Theme:
    bg: str = "#0F1220"
    surface: str = "#161A2A"
    surface_alt: str = "#121627"
    border: str = "#2A3248"
    text: str = "#E6EAF5"
    text_muted: str = "#A9B0C6"
    text_disabled: str = "#7B829A"
    primary_start: str = "#22D3EE"
    primary_mid: str = "#66AAFF"
    primary_end: str = "#7B61FF"
    success: str = "#22C55E"
    warn: str = "#F59E0B"
    error: str = "#EF4444"

THEME = Theme()
