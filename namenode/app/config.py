"""
Configuración del NameNode leída desde variables de entorno o .env.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    block_size_mb: int = 64
    replication_factor: int = 2
    heartbeat_timeout: int = 90
    secret_key: str = "dev-secret"
    database_url: str = "sqlite:///./data/namenode.db"
    algorithm: str = "HS256"
    token_expire_minutes: int = 1440

    class Config:
        env_file = ".env"


settings = Settings()
