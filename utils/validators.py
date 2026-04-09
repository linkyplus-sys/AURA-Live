from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from utils.exceptions import ValidationError


MAX_INPUT_LENGTH = 1000
DANGEROUS_PATTERNS = [
    re.compile(r"<\s*script", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),
    re.compile(r"data\s*:\s*text/html", re.IGNORECASE),
]


def sanitize_input(text: object, max_length: int = MAX_INPUT_LENGTH) -> str:
    if not isinstance(text, str):
        raise ValidationError("输入必须是字符串。")
    cleaned = text.strip()
    if not cleaned:
        raise ValidationError("输入不能为空。")
    if len(cleaned) > max_length:
        raise ValidationError(f"输入长度不能超过 {max_length} 个字符。")
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(cleaned):
            raise ValidationError("输入包含不允许的内容。")
    return cleaned


def validate_path(base_dir: str | Path, filename: str) -> Path:
    base_path = Path(base_dir).resolve()
    candidate = (base_path / filename).resolve()
    if candidate != base_path and base_path not in candidate.parents:
        raise ValidationError("检测到非法路径访问。")
    return candidate


def validate_json_structure(data: object, required_keys: Iterable[str]) -> bool:
    if not isinstance(data, Mapping):
        raise ValidationError("JSON 内容必须是对象。")
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        joined = ", ".join(missing_keys)
        raise ValidationError(f"JSON 缺少必填字段: {joined}")
    return True
