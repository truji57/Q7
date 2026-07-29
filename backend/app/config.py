"""
Q7 Backend - Configuracion
"""
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    database_url: str = "sqlite:///q7.db"
    secret_key: str = "q7-secret-key-change-in-production"
    cors_origins: list[str] = ["http://localhost:5174", "http://127.0.0.1:5174"]
    bridge_default_port: int = 5556
    bridge_default_host: str = "127.0.0.1"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
