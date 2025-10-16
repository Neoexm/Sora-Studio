"""Application constants and configuration"""

API_BASE = "https://api.openai.com/v1"
SERVICE_NAME = "Sora Studio"

SUPPORTED_SIZES = {
    "sora-2": ["1280x720", "720x1280"],
    "sora-2-pro": ["1280x720", "720x1280", "1024x1792", "1792x1024"]
}

SUPPORTED_SECONDS = ["4", "8", "12"]
