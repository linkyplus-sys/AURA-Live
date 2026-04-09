from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

import chromadb
from chromadb.api.types import EmbeddingFunction

from config import MemoryConfig, OllamaConfig
from models.llm import LLMClient
from utils.exceptions import EmbeddingError, MemoryStoreError
from utils.file_ops import ensure_directory
from utils.parser import extract_first_sentence, parse_content


MEMORY_HINTS = (
    "我是",
    "我叫",
    "我的",
    "我喜欢",
    "我不喜欢",
    "我讨厌",
    "我想",
    "我希望",
    "我打算",
    "我准备",
    "我计划",
    "我最近",
    "我现在",
    "我正在",
    "我会",
    "我住在",
    "我来自",
    "我习惯",
    "我爱",
    "请你记住",
    "以后",
)

LOW_VALUE_PATTERNS = (
    re.compile(r"^(你好|您好|嗨|哈喽|在吗|早上好|中午好|晚上好|晚安)[!！,.，。 ]*$"),
    re.compile(r"^(谢谢|谢了|好的|好哦|收到|明白|行|行吧|可以|ok|OK)[!！,.，。 ]*$"),
    re.compile(r"^(哈哈+|嘿嘿+|嗯+|哦+|啊+|欸+)[!！,.，。 ]*$"),
    re.compile(r"^(拜拜|再见)[!！,.，。 ]*$"),
)

PROFILE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("profile.name", re.compile(r"我叫\s*([^，。；;,\s]{1,16})")),
    ("profile.alias", re.compile(r"你可以叫我\s*([^，。；;,\s]{1,16})")),
    ("profile.location", re.compile(r"我(?:现在)?住在\s*([^，。；;,]{1,24})")),
    ("profile.origin", re.compile(r"我来自\s*([^，。；;,]{1,24})")),
    ("profile.job", re.compile(r"我是(?:一名|一个|个|位)?([^，。；;,]{1,24})")),
)

TARGET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("preference.like", re.compile(r"我(?:很|更|最)?喜欢([^，。；;,]{1,24})")),
    ("preference.dislike", re.compile(r"我(?:不喜欢|讨厌|不爱)([^，。；;,]{1,24})")),
    ("habit", re.compile(r"我习惯([^。！？!?]{1,32})")),
    ("plan", re.compile(r"我(?:打算|准备|计划|想要?|希望)([^。！？!?]{1,40})")),
    ("state", re.compile(r"我(?:最近|现在|这段时间|这几天)([^。！？!?]{1,40})")),
    ("boundary", re.compile(r"(?:请你记住|希望你|以后请你|以后)([^。！？!?]{1,40})")),
)

ASSISTANT_CONTEXT_PATTERNS: tuple[tuple[str, str, re.Pattern[str], int], ...] = (
    ("context.appearance", "context.appearance", re.compile(r"(?:穿着|披着|套着|身上是|换上了|戴着)([^。！？!?]{1,48})"), 3),
    ("context.appearance", "context.appearance", re.compile(r"(?:外套|衬衫|裙子|长裙|短裙|裤子|长裤|鞋子|靴子|围巾|领口|袖口|发丝|发梢|耳饰)([^。！？!?]{0,32})"), 2),
    ("context.action", "context.action", re.compile(r"(?:正在|刚刚|刚才|依旧在|还在)([^。！？!?]{1,48})"), 3),
    ("context.action", "context.action", re.compile(r"(?:坐在|站在|靠在|俯身|低头|抬手|伸手|整理|抱着|倚着|望向|走到|停在|翻着|捧着)([^。！？!?]{0,36})"), 2),
    ("context.scene", "context.scene", re.compile(r"(?:窗外|房间里|室内|沙发上|桌边|灯光下|雨声里|夜色里|走廊里|门边|床边)([^。！？!?]{0,36})"), 2),
)

SLOT_CATEGORIES = {"profile.name", "profile.alias", "profile.location", "profile.origin", "profile.job"}
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[。！？!?；;])\s+|[\r\n]+")

CATEGORY_LABELS = {
    "profile.name": "身份称呼",
    "profile.alias": "偏好称呼",
    "profile.location": "所在地点",
    "profile.origin": "来源信息",
    "profile.job": "职业身份",
    "preference.like": "明确偏好",
    "preference.dislike": "明确厌恶",
    "habit": "习惯",
    "plan": "计划",
    "state": "近期状态",
    "boundary": "互动边界",
    "context.appearance": "当前衣着",
    "context.action": "当前动作",
    "context.scene": "当前场景",
    "general": "一般记忆",
}


@dataclass(frozen=True)
class MemoryEntry:
    id: str
    user_text: str
    bot_text: str
    created_at: str
    user_memory: str = ""
    bot_memory: str = ""
    summary: str = ""
    category: str = ""
    key: str = ""
    updated_at: str = ""
    score: int = 0


@dataclass(frozen=True)
class MemoryCandidate:
    user_text: str
    bot_text: str
    user_memory: str
    bot_memory: str
    summary: str
    category: str
    key: str
    score: int


def _clean_context_text(text: str) -> str:
    return re.sub(r"[（）()]+", "", text).strip()


class OllamaEmbeddingFunction(EmbeddingFunction[list[str]]):
    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client
        self._config = {
            "base_url": llm_client.config.base_url,
            "embed_model": llm_client.config.embed_model,
            "default_model": llm_client.config.default_model,
            "request_timeout": llm_client.config.request_timeout,
            "max_retries": llm_client.config.max_retries,
            "retry_delay": llm_client.config.retry_delay,
        }

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self.llm_client.embed_texts(input)

    @staticmethod
    def name() -> str:
        return "ollama"

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "OllamaEmbeddingFunction":
        ollama_config = OllamaConfig(
            base_url=str(config["base_url"]),
            embed_model=str(config["embed_model"]),
            default_model=str(config.get("default_model", "")),
            request_timeout=int(config.get("request_timeout", 60)),
            max_retries=int(config.get("max_retries", 3)),
            retry_delay=float(config.get("retry_delay", 1.0)),
        )
        return OllamaEmbeddingFunction(LLMClient(ollama_config))

    def get_config(self) -> dict[str, Any]:
        return dict(self._config)

    def default_space(self) -> str:
        return "cosine"


class MemoryManager:
    def __init__(self, config: MemoryConfig, llm_client: LLMClient) -> None:
        self.config = config
        self.llm_client = llm_client
        ensure_directory(self.config.db_path)
        self.client = chromadb.PersistentClient(path=str(self.config.db_path))
        self.collection = self._create_collection()

    def _create_collection(self):
        return self.client.get_or_create_collection(
            name=self.config.collection_name,
            embedding_function=OllamaEmbeddingFunction(self.llm_client),
            metadata={"hnsw:space": "cosine"},
        )

    def recall(self, query_text: str, n: int | None = None) -> str:
        if self.count() == 0:
            return ""

        query = self._normalize_text(query_text)
        if not query:
            return ""

        target_count = max(1, n or self.config.recall_count)
        query_count = max(target_count * 3, target_count)
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=query_count,
                include=["metadatas", "distances"],
            )
        except Exception as exc:
            raise MemoryStoreError("记忆检索失败。") from exc

        metadatas = results.get("metadatas", [[]])
        distances = results.get("distances", [[]])
        threshold = self._resolve_similarity_threshold()

        candidates: list[tuple[MemoryEntry, float]] = []
        for index, item in enumerate(metadatas[0]):
            if not isinstance(item, dict):
                continue
            entry = self._metadata_to_entry(item)
            distance = distances[0][index] if index < len(distances[0]) else None
            candidates.append((entry, self._distance_to_similarity(distance)))

        selected = [(entry, similarity) for entry, similarity in candidates if similarity >= threshold]
        if not selected and candidates:
            fallback_entry, fallback_similarity = candidates[0]
            if fallback_similarity >= max(0.35, threshold - 0.2):
                selected = [(fallback_entry, fallback_similarity)]

        lines: list[str] = []
        seen: set[tuple[str, str]] = set()
        for entry, _ in selected[:target_count]:
            marker = (entry.key, entry.summary or entry.user_memory or entry.user_text)
            if marker in seen:
                continue
            seen.add(marker)
            summary = entry.summary.strip()
            if summary:
                lines.append(
                    "时间:{time} | {summary}".format(
                        time=entry.updated_at or entry.created_at or "未知",
                        summary=summary.replace("\n", " | "),
                    )
                )
                continue
            lines.append(
                "时间:{time} | 我说:{user} | 你回:{bot}".format(
                    time=entry.updated_at or entry.created_at or "未知",
                    user=entry.user_memory or extract_first_sentence(entry.user_text, max_length=80),
                    bot=entry.bot_memory or extract_first_sentence(entry.bot_text, max_length=80),
                )
            )
        return "\n".join(lines)

    def memorize(self, user_text: str, bot_text: str) -> bool:
        memory_hash = self._build_memory_hash(user_text, bot_text)
        try:
            existing = self.collection.get(where={"hash": memory_hash})
        except Exception as exc:
            raise MemoryStoreError("记忆查重失败。") from exc
        if existing.get("ids"):
            return False

        candidates = self._build_memory_candidates(user_text, bot_text)
        if not candidates:
            return False

        created_at = datetime.now().isoformat(timespec="seconds")
        saved = False
        seen_keys: set[tuple[str, str]] = set()

        for candidate in candidates:
            marker = (candidate.category, candidate.key or candidate.summary)
            if marker in seen_keys:
                continue
            seen_keys.add(marker)
            if self._save_candidate(memory_hash, candidate, created_at):
                saved = True
        return saved

    def get_all_memories(self) -> list[MemoryEntry]:
        try:
            payload = self.collection.get(include=["metadatas"])
        except Exception as exc:
            raise MemoryStoreError("获取记忆列表失败。") from exc

        entries: list[MemoryEntry] = []
        for item in payload.get("metadatas", []):
            if not isinstance(item, dict):
                continue
            entries.append(self._metadata_to_entry(item))
        return entries

    def delete_memory(self, memory_id: str) -> bool:
        try:
            self.collection.delete(ids=[memory_id])
        except Exception as exc:
            raise MemoryStoreError("删除记忆失败。") from exc
        return True

    def clear_all(self) -> bool:
        try:
            self.client.delete_collection(self.config.collection_name)
        except Exception:
            pass
        self.collection = self._create_collection()
        return True

    def count(self) -> int:
        try:
            return int(self.collection.count())
        except Exception as exc:
            raise MemoryStoreError("读取记忆数量失败。") from exc

    @staticmethod
    def _build_memory_hash(user_text: str, bot_text: str) -> str:
        content = f"{user_text}\n{bot_text}".encode("utf-8")
        return sha256(content).hexdigest()

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _truncate_text(cls, text: str, max_length: int) -> str:
        normalized = cls._normalize_text(text)
        if len(normalized) <= max_length:
            return normalized
        return normalized[: max_length - 1].rstrip() + "…"

    @classmethod
    def _distance_to_similarity(cls, distance: Any) -> float:
        try:
            value = float(distance)
        except (TypeError, ValueError):
            return 0.0
        similarity = 1.0 - value
        return max(0.0, min(1.0, similarity))

    def _resolve_similarity_threshold(self) -> float:
        threshold = float(self.config.similarity_threshold)
        if threshold <= 0:
            return 0.55
        return min(0.98, threshold)

    def _metadata_to_entry(self, item: dict[str, Any]) -> MemoryEntry:
        return MemoryEntry(
            id=str(item.get("id", "")),
            user_text=str(item.get("user_text", "")),
            bot_text=str(item.get("bot_text", "")),
            created_at=str(item.get("created_at", "")),
            user_memory=str(item.get("user_memory", "")),
            bot_memory=str(item.get("bot_memory", "")),
            summary=str(item.get("memory_summary", "")),
            category=str(item.get("memory_category", "")),
            key=str(item.get("memory_key", "")),
            updated_at=str(item.get("updated_at", "")),
            score=int(item.get("memory_score", 0) or 0),
        )

    @classmethod
    def _extract_user_memory(cls, user_text: str) -> str:
        normalized = cls._normalize_text(user_text)
        if not normalized:
            return ""

        sentences = [
            segment.strip(" ，。；;、")
            for segment in SENTENCE_SPLIT_PATTERN.split(normalized)
            if segment.strip()
        ]
        highlighted = [
            sentence
            for sentence in sentences
            if any(hint in sentence for hint in MEMORY_HINTS)
        ]
        selected = highlighted[:2] or sentences[:1]
        return cls._truncate_text("；".join(selected), 140)

    @classmethod
    def _extract_bot_memory(cls, bot_text: str) -> str:
        _, dialogue = parse_content(bot_text)
        focus = dialogue or bot_text
        return cls._truncate_text(extract_first_sentence(focus, max_length=120), 140)

    @classmethod
    def _is_low_value_message(cls, text: str) -> bool:
        normalized = cls._normalize_text(text)
        if not normalized:
            return True
        return any(pattern.fullmatch(normalized) for pattern in LOW_VALUE_PATTERNS)

    @classmethod
    def _normalize_key_fragment(cls, value: str) -> str:
        cleaned = re.sub(r"[，。；;、,.!?！？\s]+", "", cls._normalize_text(value))
        return cleaned[:48]

    @classmethod
    def _detect_memory_signal(cls, user_text: str, user_memory: str) -> tuple[str, str, int]:
        normalized_text = cls._normalize_text(user_text)
        if not normalized_text:
            return "general", "", 0

        for category, pattern in PROFILE_PATTERNS:
            match = pattern.search(normalized_text)
            if not match:
                continue
            value = cls._normalize_key_fragment(match.group(1))
            if value:
                return category, category, 4

        for category, pattern in TARGET_PATTERNS:
            match = pattern.search(normalized_text)
            if not match:
                continue
            value = cls._normalize_key_fragment(match.group(1))
            if not value:
                continue
            key = category if category in SLOT_CATEGORIES else f"{category}:{value}"
            score = 4 if category.startswith("preference") or category == "boundary" else 3
            return category, key, score

        if any(hint in normalized_text for hint in MEMORY_HINTS) and len(user_memory) >= 8:
            key = f"general:{cls._normalize_key_fragment(user_memory)[:28]}"
            return "general", key, 2

        return "general", "", 0

    @classmethod
    def _is_high_value_memory(cls, user_text: str, user_memory: str, score: int) -> bool:
        normalized_text = cls._normalize_text(user_text)
        if not normalized_text or cls._is_low_value_message(normalized_text):
            return False
        if score >= 3:
            return True
        if score == 2 and len(user_memory) >= 8:
            return True
        return False

    @classmethod
    def _extract_assistant_context_memory(cls, bot_text: str) -> str:
        action, dialogue = parse_content(bot_text)
        action_text = _clean_context_text(action)
        if action_text:
            return cls._truncate_text(action_text, 160)
        return cls._truncate_text(extract_first_sentence(dialogue or bot_text, max_length=140), 160)

    @classmethod
    def _detect_assistant_context_signals(cls, bot_text: str) -> list[tuple[str, str, str, int]]:
        action, dialogue = parse_content(bot_text)
        focus = cls._normalize_text(_clean_context_text(action) or dialogue or bot_text)
        if not focus:
            return []

        matches: list[tuple[str, str, str, int]] = []
        seen_keys: set[str] = set()
        for category, key, pattern, score in ASSISTANT_CONTEXT_PATTERNS:
            if key in seen_keys:
                continue
            match = pattern.search(focus)
            if not match:
                continue
            captured = cls._normalize_text(match.group(0))
            if captured:
                matches.append((category, key, cls._truncate_text(captured, 140), score))
                seen_keys.add(key)
        return matches

    @classmethod
    def _build_memory_summary(cls, candidate: MemoryCandidate) -> str:
        lines: list[str] = []
        category_label = CATEGORY_LABELS.get(candidate.category, CATEGORY_LABELS["general"])
        lines.append(f"记忆类型: {category_label}")
        if candidate.category.startswith("context.") and candidate.bot_memory:
            lines.append(f"当前状态: {candidate.bot_memory}")
        elif candidate.user_memory:
            lines.append(f"用户关键信息: {candidate.user_memory}")
        if candidate.bot_memory:
            if candidate.category.startswith("context."):
                lines.append(f"本轮回应: {candidate.bot_memory}")
            elif candidate.bot_memory != candidate.user_memory:
                lines.append(f"本轮回应: {candidate.bot_memory}")
        return "\n".join(lines)

    @classmethod
    def _build_user_memory_candidate(cls, user_text: str, bot_text: str) -> MemoryCandidate | None:
        user_memory = cls._extract_user_memory(user_text)
        category, key, score = cls._detect_memory_signal(user_text, user_memory)
        if not cls._is_high_value_memory(user_text, user_memory, score):
            return None

        bot_memory = cls._extract_bot_memory(bot_text)
        candidate = MemoryCandidate(
            user_text=user_text,
            bot_text=bot_text,
            user_memory=user_memory or cls._truncate_text(user_text, 140),
            bot_memory=bot_memory,
            summary="",
            category=category,
            key=key,
            score=score,
        )
        summary = cls._build_memory_summary(candidate)
        return MemoryCandidate(
            user_text=candidate.user_text,
            bot_text=candidate.bot_text,
            user_memory=candidate.user_memory,
            bot_memory=candidate.bot_memory,
            summary=summary,
            category=candidate.category,
            key=candidate.key,
            score=candidate.score,
        )

    @classmethod
    def _build_assistant_context_candidates(cls, user_text: str, bot_text: str) -> list[MemoryCandidate]:
        candidates: list[MemoryCandidate] = []
        for category, key, context_memory, score in cls._detect_assistant_context_signals(bot_text):
            if not key or not context_memory or score <= 0:
                continue
            candidate = MemoryCandidate(
                user_text=user_text,
                bot_text=bot_text,
                user_memory="",
                bot_memory=context_memory,
                summary="",
                category=category,
                key=key,
                score=score,
            )
            summary = cls._build_memory_summary(candidate)
            candidates.append(
                MemoryCandidate(
                    user_text=candidate.user_text,
                    bot_text=candidate.bot_text,
                    user_memory=candidate.user_memory,
                    bot_memory=candidate.bot_memory,
                    summary=summary,
                    category=candidate.category,
                    key=candidate.key,
                    score=candidate.score,
                )
            )
        return candidates

    @classmethod
    def _build_memory_candidates(cls, user_text: str, bot_text: str) -> list[MemoryCandidate]:
        candidates: list[MemoryCandidate] = []
        user_candidate = cls._build_user_memory_candidate(user_text, bot_text)
        if user_candidate is not None:
            candidates.append(user_candidate)

        candidates.extend(cls._build_assistant_context_candidates(user_text, bot_text))
        return candidates

    def _find_merge_target(self, candidate: MemoryCandidate) -> tuple[str, dict[str, Any]] | None:
        if candidate.key:
            try:
                exact = self.collection.get(where={"memory_key": candidate.key}, include=["metadatas"])
            except Exception as exc:
                raise MemoryStoreError("记忆合并查询失败。") from exc
            ids = exact.get("ids", [])
            metadatas = exact.get("metadatas", [])
            if ids and metadatas:
                first_meta = metadatas[0] if isinstance(metadatas[0], dict) else {}
                return str(ids[0]), first_meta

        if self.count() == 0:
            return None

        try:
            results = self.collection.query(
                query_texts=[candidate.summary or candidate.user_memory],
                n_results=3,
                include=["metadatas", "distances"],
            )
        except Exception as exc:
            raise MemoryStoreError("相似记忆查询失败。") from exc

        metadatas = results.get("metadatas", [[]])
        distances = results.get("distances", [[]])
        ids = results.get("ids", [[]])
        for index, item in enumerate(metadatas[0]):
            if not isinstance(item, dict):
                continue
            category = str(item.get("memory_category", ""))
            similarity = self._distance_to_similarity(distances[0][index] if index < len(distances[0]) else None)
            if category != candidate.category or similarity < 0.88:
                continue
            if not ids[0] or index >= len(ids[0]):
                continue
            return str(ids[0][index]), item
        return None

    @classmethod
    def _merge_metadata(
        cls,
        *,
        memory_id: str,
        existing_metadata: dict[str, Any],
        new_metadata: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        created_at = str(existing_metadata.get("created_at", "")) or now
        turn_count = int(existing_metadata.get("turn_count", 1) or 1) + 1

        merged = {
            "id": memory_id,
            "hash": str(new_metadata.get("hash", "")),
            "created_at": created_at,
            "updated_at": now,
            "turn_count": turn_count,
            "user_text": str(new_metadata.get("user_text", "")),
            "bot_text": str(new_metadata.get("bot_text", "")),
            "user_memory": str(new_metadata.get("user_memory", "")),
            "bot_memory": str(new_metadata.get("bot_memory", "")),
            "memory_summary": str(new_metadata.get("memory_summary", "")),
            "memory_category": str(new_metadata.get("memory_category", "")),
            "memory_key": str(new_metadata.get("memory_key", "")),
            "memory_score": int(new_metadata.get("memory_score", 0) or 0),
        }

        if not merged["memory_key"]:
            merged["memory_key"] = str(existing_metadata.get("memory_key", ""))
        if not merged["memory_category"]:
            merged["memory_category"] = str(existing_metadata.get("memory_category", "general"))
        return merged

    def _save_candidate(self, memory_hash: str, candidate: MemoryCandidate, created_at: str) -> bool:
        merge_target = self._find_merge_target(candidate)

        metadata = {
            "hash": memory_hash,
            "user_text": candidate.user_text,
            "bot_text": candidate.bot_text,
            "user_memory": candidate.user_memory,
            "bot_memory": candidate.bot_memory,
            "memory_summary": candidate.summary,
            "memory_category": candidate.category,
            "memory_key": candidate.key,
            "memory_score": candidate.score,
        }

        if merge_target is not None:
            memory_id, existing_meta = merge_target
            merged_metadata = self._merge_metadata(
                memory_id=memory_id,
                existing_metadata=existing_meta,
                new_metadata=metadata,
                now=created_at,
            )
            document = self._build_document(merged_metadata)
            try:
                self.collection.upsert(
                    ids=[memory_id],
                    documents=[document],
                    metadatas=[merged_metadata],
                )
            except EmbeddingError:
                raise
            except Exception as exc:
                raise MemoryStoreError("记忆合并失败。") from exc
            return True

        memory_id = str(uuid4())
        metadata.update(
            {
                "id": memory_id,
                "created_at": created_at,
                "updated_at": created_at,
                "turn_count": 1,
            }
        )
        document = self._build_document(metadata)
        try:
            self.collection.add(
                ids=[memory_id],
                documents=[document],
                metadatas=[metadata],
            )
        except EmbeddingError:
            raise
        except Exception as exc:
            raise MemoryStoreError("记忆存储失败。") from exc
        return True

    @classmethod
    def _build_document(cls, metadata: dict[str, Any]) -> str:
        category = CATEGORY_LABELS.get(str(metadata.get("memory_category", "")), CATEGORY_LABELS["general"])
        parts = [
            f"记忆类型: {category}",
            str(metadata.get("memory_summary", "")),
            f"用户原话: {metadata.get('user_text', '')}",
            f"助手原话: {metadata.get('bot_text', '')}",
        ]
        return "\n".join(part for part in parts if part)
