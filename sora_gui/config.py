"""Configuration management"""
import json
import base64
import logging
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import keyring
except ImportError:
    keyring = None

try:
    from platformdirs import user_config_dir
except ImportError:
    user_config_dir = None

from .constants import SERVICE_NAME

logger = logging.getLogger(__name__)

def get_config_dir() -> Path:
    """Get configuration directory path"""
    if user_config_dir:
        return Path(user_config_dir(SERVICE_NAME))
    return Path.home() / ".sorastudio"

def get_output_dir() -> Path:
    """Get default output directory path"""
    return Path.home() / "Videos" / "Sora AI Videos"

CONFIG_DIR = get_config_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"
OUTPUT_DIR = get_output_dir()

def ensure_dirs() -> None:
    """Ensure config and output directories exist"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning(f"Failed to create directories: {e}")

def load_config() -> Dict[str, Any]:
    """Load configuration from file"""
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {}

def save_config(data: Dict[str, Any]) -> None:
    """Save configuration to file"""
    try:
        ensure_dirs()
        CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to save config: {e}")

def get_saved_key() -> str:
    """Retrieve saved API key from keyring or config file"""
    if keyring:
        try:
            key = keyring.get_password(SERVICE_NAME, "OPENAI_API_KEY")
            if key:
                return key
        except Exception as e:
            logger.warning(f"Keyring access failed: {e}")
    
    cfg = load_config()
    encoded_key = cfg.get("api_key", "")
    if encoded_key:
        try:
            return base64.b64decode(encoded_key.encode()).decode()
        except Exception as e:
            logger.warning(f"Failed to decode key: {e}")
            return encoded_key
    return ""

def set_saved_key(key: str) -> None:
    """Save API key to keyring or config file"""
    if keyring:
        try:
            keyring.set_password(SERVICE_NAME, "OPENAI_API_KEY", key)
            cfg = load_config()
            if "api_key" in cfg:
                del cfg["api_key"]
            save_config(cfg)
            return
        except Exception as e:
            logger.warning(f"Keyring save failed, using config file: {e}")
    
    encoded = base64.b64encode(key.encode()).decode()
    cfg = load_config()
    cfg["api_key"] = encoded
    save_config(cfg)

def get_settings() -> Dict[str, Any]:
    """Get settings from config"""
    cfg = load_config()
    return cfg.get("settings", {})

def save_settings(settings: Dict[str, Any]) -> None:
    """Save settings to config"""
    cfg = load_config()
    cfg["settings"] = settings
    save_config(cfg)

def get_recent_projects() -> list[str]:
    """Get list of recent project paths"""
    cfg = load_config()
    return cfg.get("recent_projects", [])

def add_recent_project(path: str) -> None:
    """Add project to recent list"""
    cfg = load_config()
    recent = cfg.get("recent_projects", [])
    if path in recent:
        recent.remove(path)
    recent.insert(0, path)
    cfg["recent_projects"] = recent[:10]
    save_config(cfg)

def get_last_state() -> Dict[str, Any]:
    """Get last application state"""
    cfg = load_config()
    return cfg.get("last_state", {})

def save_last_state(state: Dict[str, Any]) -> None:
    """Save last application state"""
    cfg = load_config()
    cfg["last_state"] = state
    save_config(cfg)

def get_window_geometry() -> Dict[str, Any]:
    """Get window geometry"""
    cfg = load_config()
    return cfg.get("window_geometry", {})

def save_window_geometry(geometry: Dict[str, Any]) -> None:
    """Save window geometry"""
    cfg = load_config()
    cfg["window_geometry"] = geometry
    save_config(cfg)
