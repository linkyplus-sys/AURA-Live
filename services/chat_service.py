from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import asdict
from typing import Any

from config import AppConfig
from models import LLMClient, MemoryManager
from utils.exceptions import AURAPetError, ValidationError
from utils.file_ops import ensure_directory, ensure_json_file, safe_json_load, safe_json_save
from utils.parser import normalize_action_perspective
from utils.validators import sanitize_input, validate_json_structure


logger = logging.getLogger(__name__)


DEFAULT_SOUL = {
    "name": "AURA",
    "personality": "温柔、清醒、带一点陪伴感的本地 AI 宠物。",
    "style": "如果需要动作或环境描写，请写在括号()内。",
    "scene": "",
    "pet_image": "bot.png",
}

DEFAULT_WORLDBOOK = {
    "AURA": "一个运行在本地环境中的 AI 宠物助手，强调陪伴、记忆和人格化表达。",
}

DEFAULT_MEMORY_SETTINGS = {
    "enabled": True,
    "save_latest_turn": True,
    "recall_count": 3,
}

DEFAULT_RUNTIME_SETTINGS = {
    "base_url": "",
    "current_model": "",
}


class ChatService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._bootstrap_files()
        self.llm = LLMClient(config.ollama)
        self.memory = MemoryManager(config.memory, self.llm)
        self.current_model = config.ollama.default_model
        self.last_memory_error = ""
        self._apply_runtime_settings()

    def _bootstrap_files(self) -> None:
        ensure_directory(self.config.files.avatars_dir)
        ensure_directory(self.config.memory.db_path)
        ensure_json_file(self.config.files.hist, [])
        ensure_json_file(self.config.files.soul, DEFAULT_SOUL)
        ensure_json_file(self.config.files.worldbook, DEFAULT_WORLDBOOK)
        ensure_json_file(self.config.files.memory, DEFAULT_MEMORY_SETTINGS)
        ensure_json_file(self.config.files.runtime, DEFAULT_RUNTIME_SETTINGS)

    def load_soul(self) -> dict[str, str]:
        soul = safe_json_load(self.config.files.soul, DEFAULT_SOUL)
        if not isinstance(soul, dict):
            return DEFAULT_SOUL.copy()
        data = DEFAULT_SOUL.copy()
        data.update({str(key): str(value) for key, value in soul.items()})
        try:
            validate_json_structure(data, ["name", "personality"])
        except ValidationError:
            return DEFAULT_SOUL.copy()
        if not data["name"].strip() or not data["personality"].strip():
            return DEFAULT_SOUL.copy()
        return data

    def load_worldbook(self) -> Any:
        worldbook = safe_json_load(self.config.files.worldbook, DEFAULT_WORLDBOOK)
        if not isinstance(worldbook, dict):
            return DEFAULT_WORLDBOOK.copy()
        return self._normalize_worldbook_payload(worldbook)

    def load_runtime_settings(self) -> dict[str, str]:
        runtime = safe_json_load(self.config.files.runtime, DEFAULT_RUNTIME_SETTINGS)
        if not isinstance(runtime, dict):
            return DEFAULT_RUNTIME_SETTINGS.copy()
        normalized = DEFAULT_RUNTIME_SETTINGS.copy()
        normalized.update({str(key): str(value).strip() for key, value in runtime.items()})
        return normalized

    def save_runtime_settings(self, runtime_data: dict[str, str]) -> dict[str, str]:
        normalized = DEFAULT_RUNTIME_SETTINGS.copy()
        normalized.update({str(key): str(value).strip() for key, value in runtime_data.items()})
        safe_json_save(self.config.files.runtime, normalized)
        return normalized

    def save_soul(self, soul_data: dict[str, str]) -> dict[str, str]:
        if not isinstance(soul_data, dict):
            raise ValidationError("人格配置必须是对象。")
        normalized = DEFAULT_SOUL.copy()
        normalized.update({str(key): str(value).strip() for key, value in soul_data.items()})
        validate_json_structure(normalized, ["name", "personality"])
        if not normalized["name"] or not normalized["personality"]:
            raise ValidationError("人格名称和性格描述不能为空。")
        safe_json_save(self.config.files.soul, normalized)
        return normalized

    def save_worldbook(self, worldbook_data: Any) -> Any:
        if not isinstance(worldbook_data, dict):
            raise ValidationError("世界书必须是 JSON 对象。")
        normalized = self._normalize_worldbook_payload(worldbook_data)
        safe_json_save(self.config.files.worldbook, normalized)
        return normalized

    def get_conversation_history(self) -> list[dict[str, str]]:
        history = safe_json_load(self.config.files.hist, [])
        if not isinstance(history, list):
            return []
        sanitized_history: list[dict[str, str]] = []
        for item in history:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "assistant"))
            content = str(item.get("content", ""))
            sanitized_history.append({"role": role, "content": content})
        return sanitized_history

    def save_conversation(self, messages: list[dict[str, str]]) -> None:
        safe_json_save(self.config.files.hist, messages)

    def retrieve_memories(self, query: str) -> str:
        return self.memory.recall(query, self.config.memory.recall_count)

    def save_memory(self, user_text: str, bot_text: str) -> bool:
        return self.memory.memorize(user_text, bot_text)

    def get_available_models(self) -> list[str]:
        return self.llm.get_available_models()

    def get_memory_count(self) -> int:
        return self.memory.count()

    def get_memory_error(self) -> str:
        return self.last_memory_error

    def get_memories(self) -> list[dict[str, Any]]:
        entries = self.memory.get_all_memories()
        sorted_entries = sorted(
            entries,
            key=lambda item: item.updated_at or item.created_at,
            reverse=True,
        )
        return [asdict(item) for item in sorted_entries]

    def set_model(self, model: str) -> None:
        self.current_model = model.strip()
        self.llm.set_model(self.current_model)
        runtime = self.load_runtime_settings()
        runtime["current_model"] = self.current_model
        runtime["base_url"] = self.llm.config.base_url
        self.save_runtime_settings(runtime)

    def set_base_url(self, base_url: str) -> None:
        normalized = self._normalize_base_url(base_url)
        self.llm.set_base_url(normalized)
        runtime = self.load_runtime_settings()
        runtime["base_url"] = normalized
        runtime["current_model"] = self.current_model
        self.save_runtime_settings(runtime)

    def build_system_prompt(
        self,
        soul: dict[str, str],
        memories: str,
        worldbook_context: str,
    ) -> str:
        sections = [
            f"你是{soul['name']}。{soul['personality']}",
        ]
        if soul.get("style"):
            sections.append(f"【表达风格】\n{soul['style']}")
        if soul.get("scene"):
            sections.append(f"【当前环境与背景】\n{soul['scene']}")
        if worldbook_context:
            sections.append(f"【世界书】\n{worldbook_context}")
        if memories:
            sections.append(f"【长期记忆】\n{memories}")
        sections.append(
            "【回复规则】\n"
            "- 保持自然、简洁、有陪伴感。\n"
            "- 不要自称语言模型或系统。\n"
            f"- 如果要描写动作、神态或环境，请放在括号()内，并使用第三人称描述{soul['name']}，不要用“我”。"
        )
        return "\n\n".join(sections)

    def chat(self, user_input: str) -> Iterator[str]:
        cleaned_input = sanitize_input(user_input, self.config.max_input_length)
        history = self.get_conversation_history()
        recent_history = history[-self.config.history_window :]
        soul = self.load_soul()
        worldbook = self.load_worldbook()
        memories = self.retrieve_memories(cleaned_input)
        trigger_text = self._build_worldbook_trigger_text(recent_history, cleaned_input)
        worldbook_context = self.resolve_worldbook_context(worldbook, trigger_text)
        system_prompt = self.build_system_prompt(soul, memories, worldbook_context)

        messages = [
            {"role": "system", "content": system_prompt},
            *recent_history,
            {"role": "user", "content": cleaned_input},
        ]

        chunks: list[str] = []
        try:
            for chunk in self.llm.chat(messages, model=self.current_model or None):
                chunks.append(chunk)
                yield chunk
        except ValidationError:
            raise
        except AURAPetError:
            raise
        except Exception as exc:
            logger.exception("Chat execution failed")
            raise AURAPetError("对话执行失败。") from exc

        assistant_text = normalize_action_perspective("".join(chunks).strip(), soul["name"])
        if not assistant_text:
            raise AURAPetError("模型没有返回有效内容。")

        updated_history = [
            *history,
            {"role": "user", "content": cleaned_input},
            {"role": "assistant", "content": assistant_text},
        ]
        self.save_conversation(updated_history)

        self.last_memory_error = ""
        try:
            self.save_memory(cleaned_input, assistant_text)
        except AURAPetError as exc:
            self.last_memory_error = str(exc)
            logger.exception("Memory save failed after chat")

    def _normalize_worldbook_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if isinstance(payload.get("entries"), list):
            entries = [
                entry
                for item in payload["entries"]
                if (entry := self._normalize_worldbook_entry(item))
            ]
            return {"entries": entries}

        normalized: dict[str, Any] = {}
        for key, value in payload.items():
            cleaned_key = str(key).strip()
            if not cleaned_key:
                continue
            if isinstance(value, str):
                cleaned_value = value.strip()
                if cleaned_value:
                    normalized[cleaned_key] = cleaned_value
                continue
            if isinstance(value, dict):
                entry = self._normalize_worldbook_entry(value, fallback_title=cleaned_key)
                if entry:
                    normalized[cleaned_key] = entry
        return normalized

    @staticmethod
    def _normalize_worldbook_entry(
        item: Any,
        fallback_title: str = "",
    ) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None

        title = str(item.get("title") or fallback_title).strip()
        content = str(item.get("content") or "").strip()
        raw_keywords = item.get("keywords", [])
        if isinstance(raw_keywords, str):
            raw_keywords = [raw_keywords]
        keywords = [str(keyword).strip() for keyword in raw_keywords if str(keyword).strip()]
        always = bool(item.get("always", False))

        if not content:
            return None
        if not keywords and not always and fallback_title:
            keywords = [fallback_title]
        if not title:
            title = keywords[0] if keywords else fallback_title or "entry"

        return {
            "title": title,
            "keywords": keywords,
            "content": content,
            "always": always,
        }

    @staticmethod
    def _build_worldbook_trigger_text(
        recent_history: list[dict[str, str]],
        user_input: str,
    ) -> str:
        recent_text = "\n".join(str(item.get("content", "")) for item in recent_history[-4:])
        return f"{recent_text}\n{user_input}".lower().strip()

    def resolve_worldbook_context(self, worldbook: Any, trigger_text: str) -> str:
        entries: list[str] = []
        seen: set[tuple[str, str]] = set()

        if isinstance(worldbook, dict) and isinstance(worldbook.get("entries"), list):
            for item in worldbook["entries"]:
                self._append_worldbook_entry(entries, seen, item, trigger_text)
        elif isinstance(worldbook, dict):
            for key, value in worldbook.items():
                if isinstance(value, str):
                    self._append_worldbook_entry(
                        entries,
                        seen,
                        {"title": key, "keywords": [key], "content": value, "always": False},
                        trigger_text,
                    )
                elif isinstance(value, dict):
                    entry = self._normalize_worldbook_entry(value, fallback_title=key)
                    self._append_worldbook_entry(entries, seen, entry, trigger_text)

        return "\n".join(entries)

    @staticmethod
    def _append_worldbook_entry(
        entries: list[str],
        seen: set[tuple[str, str]],
        item: dict[str, Any] | None,
        trigger_text: str,
    ) -> None:
        if not item:
            return

        title = str(item.get("title", "")).strip()
        content = str(item.get("content", "")).strip()
        keywords = [str(keyword).strip().lower() for keyword in item.get("keywords", []) if str(keyword).strip()]
        always = bool(item.get("always", False))

        if not content:
            return
        if not always and keywords and not any(keyword in trigger_text for keyword in keywords):
            return
        if not always and not keywords:
            return

        marker = (title, content)
        if marker in seen:
            return
        seen.add(marker)
        entries.append(f"- {title}: {content}")

    def clear_history(self) -> None:
        self.save_conversation([])

    def delete_message(self, index: int) -> bool:
        history = self.get_conversation_history()
        if index < 0 or index >= len(history):
            return False
        history.pop(index)
        self.save_conversation(history)
        return True

    def clear_memories(self) -> None:
        self.memory.clear_all()

    def prepare_regeneration(self) -> tuple[str, list[dict[str, str]]]:
        history = self.get_conversation_history()
        assistant_index = self._find_regeneration_target(history)
        removed_turn = history[assistant_index - 1 : assistant_index + 1]
        user_message = str(removed_turn[0].get("content", "")).strip()
        if not user_message:
            raise ValidationError("找不到可重新生成的用户消息。")
        remaining_history = history[: assistant_index - 1] + history[assistant_index + 1 :]
        self.save_conversation(remaining_history)
        return user_message, removed_turn

    def restore_turn(self, messages: list[dict[str, str]]) -> None:
        if not messages:
            return
        history = self.get_conversation_history()
        self.save_conversation([*history, *messages])

    def _apply_runtime_settings(self) -> None:
        runtime = self.load_runtime_settings()
        base_url = runtime.get("base_url") or self.config.ollama.base_url
        model = runtime.get("current_model") or self.config.ollama.default_model
        self.llm.set_base_url(self._normalize_base_url(base_url))
        self.current_model = model.strip()
        self.llm.set_model(self.current_model)

    @staticmethod
    def _find_regeneration_target(history: list[dict[str, str]]) -> int:
        for index in range(len(history) - 1, 0, -1):
            role = str(history[index].get("role", ""))
            previous_role = str(history[index - 1].get("role", ""))
            if role == "assistant" and previous_role == "user":
                return index
        raise ValidationError("当前没有可重新生成的最新回复。")

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        normalized = str(base_url).strip().rstrip("/")
        if not normalized:
            raise ValidationError("服务地址不能为空。")
        if not normalized.startswith(("http://", "https://")):
            normalized = f"http://{normalized}"
        return normalized
