import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root .env (when uvicorn runs from backend/, cwd-relative ".env" misses it)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILES = (
    _REPO_ROOT / ".env",
    _REPO_ROOT / "backend" / ".env",
)


def _env_files() -> list[str]:
    if os.environ.get("MEMORIA_SKIP_ENV_FILE"):
        return []
    files = [str(p) for p in _ENV_FILES if p.is_file()]
    return files or [str(_REPO_ROOT / ".env")]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://memoria:memoria@localhost:5432/memoria"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    fireworks_api_key: str = ""
    fireworks_base_url: str = "https://api.fireworks.ai/inference/v1"
    fireworks_chat_model: str = "accounts/fireworks/models/deepseek-v4-pro"
    fireworks_embedding_model: str = "fireworks/qwen3-embedding-8b"
    fireworks_embedding_dimensions: int = 1536
    monad_rpc_url: str = "https://testnet-rpc.monad.xyz"
    chain_id: int = 10143
    memory_token_address: str = "0x0000000000000000000000000000000000000000"
    memory_registry_address: str = "0x0000000000000000000000000000000000000000"
    license_manager_address: str = "0x0000000000000000000000000000000000000000"
    royalty_engine_address: str = "0x0000000000000000000000000000000000000000"
    memory_score_registry_address: str = "0x0000000000000000000000000000000000000000"
    private_key: str = ""
    enable_demo_flow: bool = False
    demo_parent_private_key: str = ""
    demo_forker_private_key: str = ""
    demo_buyer_private_key: str = ""
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
