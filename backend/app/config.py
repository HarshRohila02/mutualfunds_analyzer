from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR.parent / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{BACKEND_DIR / 'mf_analyzer.db'}"
    anthropic_api_key: str | None = None
    mfapi_base_url: str = "https://api.mfapi.in"
    mfdata_base_url: str = "https://mfdata.in/api/v1"


settings = Settings()
