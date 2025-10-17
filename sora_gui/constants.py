"""Application constants and configuration"""
from enum import Enum

API_BASE = "https://api.openai.com/v1"
SERVICE_NAME = "Sora Studio"

SUPPORTED_SIZES = {
    "sora-2": ["1280x720", "720x1280"],
    "sora-2-pro": ["1280x720", "720x1280", "1024x1792", "1792x1024"]
}

SUPPORTED_SECONDS = ["4", "8", "12"]

DOWNLOAD_CHUNK_SIZE = 262144
TIMEOUT_POST = 300
TIMEOUT_GET = 120
TIMEOUT_DOWNLOAD = 600
TIMEOUT_TEST = 20
TIMEOUT_MODERATION = 60
MAX_BACKOFF = 15
BACKOFF_MULTIPLIER = 1.5
STUCK_CHECK_INTERVAL = 10
PREVIEW_MAX_SIZE = 360
MIN_DISK_SPACE_GB = 5.0
MIN_API_KEY_LENGTH = 20
API_KEY_PREFIX = "sk-"

class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
