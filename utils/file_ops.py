from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any


def ensure_directory(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def safe_json_load(file_path: str | Path, default: Any) -> Any:
    path = Path(file_path)
    if not path.exists():
        return default
    try:
        raw_text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return default
    if not raw_text:
        return default
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return default


def safe_json_save(file_path: str | Path, data: Any, indent: int = 2) -> None:
    path = Path(file_path)
    ensure_directory(path.parent)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=indent),
        encoding="utf-8",
    )


def ensure_json_file(file_path: str | Path, default: Any) -> None:
    path = Path(file_path)
    if path.exists():
        return
    safe_json_save(path, default)


def get_img_base64(file_path: str | Path) -> str:
    path = Path(file_path)
    binary = path.read_bytes()
    return base64.b64encode(binary).decode("utf-8")
