from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime, timezone
from pathlib import Path
import json

@dataclass
class Profile:
    id: str
    name: str
    api_key_ref: str
    org: Optional[str] = None
    rate_limit_per_min: int = 60
    burst: int = 10
    backoff_seconds: float = 1.0

@dataclass
class Shot:
    id: str
    model: str
    width: int
    height: int
    duration_s: int
    prompt: str
    ref_images: list[str] = field(default_factory=list)
    status: str = "pending"
    job_id: Optional[str] = None
    output_path: Optional[str] = None
    meta: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class Template:
    id: str
    name: str
    prompt: str
    model: str
    width: int
    height: int
    duration_s: int
    tags: list[str] = field(default_factory=list)
    pinned: bool = False
    starred: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class Settings:
    poll_seconds: int = 2
    max_wait_minutes: int = 12
    preflight_moderation: bool = True
    disk_free_threshold_gb: float = 5.0
    theme: str = "system"
    font_scale: float = 1.0
    high_contrast: bool = False
    locale: str = "en"
    parallel_jobs: int = 1
    default_profile: Optional[str] = None

@dataclass
class Project:
    name: str
    schema: int = 1
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    output_dir: str = ""
    profile_id: Optional[str] = None
    shots: list[Shot] = field(default_factory=list)
    templates: list[Template] = field(default_factory=list)
    settings: Settings = field(default_factory=Settings)
    current_model: str = "sora-2"
    current_size: str = "1280x720"
    current_duration: int = 5
    current_prompt: str = ""
    
    def to_dict(self) -> dict:
        data = asdict(self)
        data["modified_at"] = datetime.now(timezone.utc).isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        settings_data = data.get("settings", {})
        settings = Settings(**settings_data) if settings_data else Settings()
        
        shots_data = data.get("shots", [])
        shots = [Shot(**s) for s in shots_data]
        
        templates_data = data.get("templates", [])
        templates = [Template(**t) for t in templates_data]
        
        return cls(
            name=data.get("name", "Untitled"),
            schema=data.get("schema", 1),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            modified_at=data.get("modified_at", datetime.now(timezone.utc).isoformat()),
            output_dir=data.get("output_dir", ""),
            profile_id=data.get("profile_id"),
            shots=shots,
            templates=templates,
            settings=settings,
            current_model=data.get("current_model", "sora-2"),
            current_size=data.get("current_size", "1280x720"),
            current_duration=data.get("current_duration", 5),
            current_prompt=data.get("current_prompt", ""),
        )
    
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, path: Path) -> "Project":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
