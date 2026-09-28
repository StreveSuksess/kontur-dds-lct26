from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / '.env'), extra='ignore')
    database_url: str = f"sqlite:///{BACKEND_DIR / 'var' / 'dds.db'}"
    demo_mode: bool = True
    cookie_name: str = 'dds_session'
    cookie_secure: bool = False
    auth_ttl_seconds: int = 28800
    allowed_origins: str = 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000'
    data_dir: Path = BACKEND_DIR / 'data'
    backup_dir: Path = BACKEND_DIR / 'var' / 'backups'
    static_dir: Path = BACKEND_DIR.parent / 'frontend' / 'dist'
    bootstrap_admin_password: str | None = None
    ai_mode: str = 'rules'
    ai_endpoint: str | None = None
    speech_endpoint: str = 'http://127.0.0.1:11435'
    tts_endpoint: str = 'http://127.0.0.1:11436'
    ai_model: str = 'qwen3-1.7b'
    ai_timeout_seconds: float = 30
    version: str = '0.1.0'
