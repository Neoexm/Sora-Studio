"""Configuration management"""
import json
import base64
from pathlib import Path

try:
    import keyring
except:
    keyring = None

try:
    from platformdirs import user_config_dir
except:
    user_config_dir = None

from .constants import SERVICE_NAME

CONFIG_DIR = Path(user_config_dir(SERVICE_NAME)) if user_config_dir else Path.home() / ".sorastudio"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "config.json"

OUTPUT_DIR = Path.home() / "Videos" / "Sora AI Videos"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except:
            return {}
    return {}

def save_config(d):
    CONFIG_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

def get_saved_key():
    if keyring:
        try:
            v = keyring.get_password(SERVICE_NAME, "OPENAI_API_KEY")
            if v:
                return v
        except:
            pass
    cfg = load_config()
    v = cfg.get("api_key", "")
    if v:
        try:
            return base64.b64decode(v.encode()).decode()
        except:
            return v
    return ""

def set_saved_key(v):
    if keyring:
        try:
            keyring.set_password(SERVICE_NAME, "OPENAI_API_KEY", v)
            cfg = load_config()
            if "api_key" in cfg:
                del cfg["api_key"]
            save_config(cfg)
            return
        except:
            pass
    b = base64.b64encode(v.encode()).decode()
    cfg = load_config()
    cfg["api_key"] = b
    save_config(cfg)
