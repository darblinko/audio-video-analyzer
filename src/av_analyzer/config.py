"""Runtime settings read from environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def _flag(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _origins(value: str | None) -> tuple[str, ...]:
    if not value:
        return DEFAULT_CORS_ORIGINS
    return tuple(origin.strip() for origin in value.split(",") if origin.strip())


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path("data")
    max_upload_bytes: int = 50 * 1024 * 1024
    keep_uploads: bool = False
    google_api_key: str = ""
    gemini_model: str = DEFAULT_GEMINI_MODEL
    gemini_timeout_s: float = 120.0
    cors_origins: tuple[str, ...] = field(default=DEFAULT_CORS_ORIGINS)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "analyzer.db"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        env = dict(os.environ) if env is None else env
        max_mb = float(env.get("AVA_MAX_UPLOAD_MB", "50"))
        if max_mb <= 0:
            raise ValueError("AVA_MAX_UPLOAD_MB must be positive")
        return cls(
            data_dir=Path(env.get("AVA_DATA_DIR", "data")),
            max_upload_bytes=int(max_mb * 1024 * 1024),
            keep_uploads=_flag(env.get("AVA_KEEP_UPLOADS")),
            google_api_key=env.get("GOOGLE_API_KEY", "").strip(),
            gemini_model=env.get("GEMINI_MODEL", "").strip() or DEFAULT_GEMINI_MODEL,
            gemini_timeout_s=float(env.get("GEMINI_TIMEOUT_S", "120")),
            cors_origins=_origins(env.get("AVA_CORS_ORIGINS")),
        )
