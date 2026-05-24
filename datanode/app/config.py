from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    namenode_url: str = "http://namenode:8000"
    datanode_id: str = "datanode-1"
    datanode_port: int = 8001
    datanode_host: str = "0.0.0.0"
    heartbeat_interval: int = 30
    storage_path: str = "/data/blocks"

    class Config:
        env_file = ".env"


settings = Settings()
