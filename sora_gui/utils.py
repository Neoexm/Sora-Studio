"""Utility functions"""
import json
import logging
import shutil
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
from requests import Response

logger = logging.getLogger(__name__)

def parse_size(size_str: str) -> Tuple[int, int]:
    """Parse aspect ratio string like '1280x720' into (width, height).
    
    Raises:
        ValueError: If size_str format is invalid
    """
    try:
        parts = size_str.lower().split("x")
        if len(parts) != 2:
            raise ValueError(f"Invalid size format: {size_str}")
        w, h = int(parts[0]), int(parts[1])
        if w <= 0 or h <= 0:
            raise ValueError(f"Size dimensions must be positive: {w}x{h}")
        return w, h
    except (ValueError, IndexError) as e:
        raise ValueError(f"Failed to parse size '{size_str}': {e}") from e

def aspect_of(size_str: str) -> Tuple[int, int]:
    """Legacy alias for parse_size. Use parse_size instead."""
    return parse_size(size_str)

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
    """Check if there's enough disk space at the given path.
    
    Returns:
        True if sufficient space available, False otherwise.
        Returns True on error to avoid blocking user (logs warning).
    """
    try:
        stat = shutil.disk_usage(path)
        return stat.free >= required_bytes
    except Exception as e:
        logger.warning(f"Failed to check disk space at '{path}': {e}. Assuming sufficient space.")
        return True

def validate_api_key(key: str) -> bool:
    """Validate API key format.
    
    Args:
        key: API key string to validate
        
    Returns:
        True if key appears valid, False otherwise
    """
    from .constants import API_KEY_PREFIX, MIN_API_KEY_LENGTH
    return key.startswith(API_KEY_PREFIX) and len(key) > MIN_API_KEY_LENGTH

def validate_file_path(path: str) -> Optional[str]:
    """Validate a file path exists and is readable.
    
    Returns:
        None if valid, error message string if invalid
    """
    try:
        p = Path(path)
        if not p.exists():
            return f"File does not exist: {path}"
        if not p.is_file():
            return f"Path is not a file: {path}"
        if not p.stat().st_size > 0:
            return f"File is empty: {path}"
        return None
    except Exception as e:
        return f"Invalid file path: {e}"
