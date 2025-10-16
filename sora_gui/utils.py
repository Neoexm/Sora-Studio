"""Utility functions"""
import json
import shutil
from typing import Tuple, Dict, Any
from requests import Response

def aspect_of(size_str: str) -> Tuple[int, int]:
    """Parse aspect ratio string like '1280x720' into (width, height)"""
    w, h = size_str.split("x")
    return int(w), int(h)

def safe_json(resp: Response) -> Dict[str, Any]:
    """Safely extract JSON from response, with fallbacks"""
    try:
        return resp.json()
    except ValueError:
        try:
            return {"text": resp.text}
        except Exception:
            return {"error": "unreadable response"}

def pretty(obj: Any) -> str:
    """Format object as pretty-printed JSON"""
    return json.dumps(obj, ensure_ascii=False, indent=2)

def check_disk_space(path: str, required_bytes: int = 5_000_000_000) -> bool:
    """Check if there's enough disk space at the given path"""
    try:
        stat = shutil.disk_usage(path)
        return stat.free >= required_bytes
    except Exception:
        return True

def validate_api_key(key: str) -> bool:
    """Validate API key format"""
    return key.startswith("sk-") and len(key) > 20
