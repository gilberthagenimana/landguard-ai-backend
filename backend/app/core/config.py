from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "land-fraud-detection"
    app_env: str = "development"
    app_debug: bool = True
    app_port: int = 8000
    database_url: str
    jwt_secret_key: str = "dev-only-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    model_path: str = "ml/models/risk_model.joblib"
    synthetic_data_path: str = "ml/data/synthetic_land_transactions.csv"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=("settings_",),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
