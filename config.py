from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class OllamaConfig:
    provider: str
    base_url: str
    api_key: str
    embed_model: str
    default_model: str
    request_timeout: int
    max_retries: int
    retry_delay: float


@dataclass(frozen=True)
class MemoryConfig:
    collection_name: str
    db_path: Path
    recall_count: int
    similarity_threshold: float


@dataclass(frozen=True)
class FilesConfig:
    soul: Path
    hist: Path
    worldbook: Path
    memory: Path
    runtime: Path
    avatars_dir: Path


@dataclass(frozen=True)
class AppConfig:
    ollama: OllamaConfig
    memory: MemoryConfig
    files: FilesConfig
    app_title: str
    max_input_length: int
    history_window: int


def load_config() -> AppConfig:
    ollama = OllamaConfig(
        provider=os.getenv("LLM_PROVIDER", "ollama").strip() or "ollama",
        base_url=(
            os.getenv("LLM_BASE_URL")
            or os.getenv("OLLAMA_BASE_URL")
            or "http://192.168.50.51:11434"
        ).rstrip("/"),
        api_key=os.getenv("LLM_API_KEY", "").strip(),
        embed_model=(os.getenv("LLM_EMBED_MODEL") or os.getenv("EMBED_MODEL") or "bge-m3").strip(),
        default_model=(os.getenv("CHAT_MODEL") or os.getenv("DEFAULT_MODEL") or "Gemma4:e4b").strip(),
        request_timeout=_get_env_int("REQUEST_TIMEOUT", 60),
        max_retries=_get_env_int("MAX_RETRIES", 3),
        retry_delay=_get_env_float("RETRY_DELAY", 1.0),
    )
    memory = MemoryConfig(
        collection_name=os.getenv("MEMORY_COLLECTION", "pet_memory"),
        db_path=BASE_DIR / os.getenv("CHROMA_DB_PATH", "chroma_db"),
        recall_count=_get_env_int("MEMORY_RECALL_COUNT", 3),
        similarity_threshold=_get_env_float("MEMORY_SIMILARITY_THRESHOLD", 0.58),
    )
    files = FilesConfig(
        soul=BASE_DIR / os.getenv("SOUL_FILE", "soul.json"),
        hist=BASE_DIR / os.getenv("HISTORY_FILE", "history.json"),
        worldbook=BASE_DIR / os.getenv("WORLDBOOK_FILE", "worldbook.json"),
        memory=BASE_DIR / os.getenv("MEMORY_FILE", "memory.json"),
        runtime=BASE_DIR / os.getenv("RUNTIME_FILE", "runtime.json"),
        avatars_dir=BASE_DIR / os.getenv("AVATARS_DIR", "avatars"),
    )
    return AppConfig(
        ollama=ollama,
        memory=memory,
        files=files,
        app_title=os.getenv("APP_TITLE", "AURA Live"),
        max_input_length=_get_env_int("MAX_INPUT_LENGTH", 1000),
        history_window=_get_env_int("HISTORY_WINDOW", 12),
    )


config = load_config()
