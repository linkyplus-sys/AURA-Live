from __future__ import annotations

import json
import time
from typing import Iterable, Iterator

import requests

from config import OllamaConfig
from utils.exceptions import EmbeddingError, LLMConnectionError, LLMResponseError


class LLMClient:
    def __init__(self, config: OllamaConfig) -> None:
        self.config = config
        self.current_model = config.default_model
        self.session = requests.Session()

    def set_model(self, model: str) -> None:
        self.current_model = model.strip()

    def set_base_url(self, base_url: str) -> None:
        normalized = base_url.strip().rstrip("/")
        object.__setattr__(self.config, "base_url", normalized)

    def resolve_model(self, model: str | None = None) -> str:
        resolved = (model or self.current_model).strip()
        if not resolved:
            available_models = self.get_available_models()
            if not available_models:
                raise LLMResponseError("未发现可用模型，请先在 Ollama 中拉取至少一个模型。")
            resolved = available_models[0]
            self.current_model = resolved
        return resolved

    def is_healthy(self) -> bool:
        try:
            self.get_available_models()
        except LLMConnectionError:
            return False
        return True

    def get_available_models(self) -> list[str]:
        response = self._request("GET", "/api/tags")
        payload = response.json()
        models = payload.get("models", [])
        names: list[str] = []
        for item in models:
            if isinstance(item, dict):
                name = item.get("name") or item.get("model")
                if name:
                    names.append(str(name))
        return names

    def chat(self, messages: list[dict[str, str]], model: str | None = None) -> Iterator[str]:
        payload = {
            "model": self.resolve_model(model),
            "messages": messages,
            "stream": True,
        }
        response = self._request("POST", "/api/chat", json_data=payload, stream=True)
        try:
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                try:
                    data = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                chunk = ""
                if isinstance(data.get("message"), dict):
                    chunk = str(data["message"].get("content", ""))
                if not chunk:
                    chunk = str(data.get("response", ""))
                if chunk:
                    yield chunk
        finally:
            response.close()

    def chat_complete(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        payload = {
            "model": self.resolve_model(model),
            "messages": messages,
            "stream": False,
        }
        response = self._request("POST", "/api/chat", json_data=payload)
        data = response.json()
        content = ""
        if isinstance(data.get("message"), dict):
            content = str(data["message"].get("content", ""))
        if not content:
            content = str(data.get("response", ""))
        if not content:
            raise LLMResponseError("模型响应为空。")
        return content

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            text = text.strip()
            if not text:
                raise EmbeddingError("空文本无法向量化。")
            embeddings.append(self._embed_one(text))
        return embeddings

    def _embed_one(self, text: str) -> list[float]:
        legacy_payload = {"model": self.config.embed_model, "prompt": text}
        try:
            response = self._request("POST", "/api/embeddings", json_data=legacy_payload)
            data = response.json()
            embedding = data.get("embedding")
            if isinstance(embedding, list):
                return [float(value) for value in embedding]
        except LLMConnectionError as exc:
            if "404" not in str(exc):
                raise EmbeddingError(str(exc)) from exc

        modern_payload = {"model": self.config.embed_model, "input": text}
        try:
            response = self._request("POST", "/api/embed", json_data=modern_payload)
            data = response.json()
        except LLMConnectionError as exc:
            raise EmbeddingError(str(exc)) from exc

        embeddings = data.get("embeddings")
        if isinstance(embeddings, list) and embeddings:
            first = embeddings[0]
            if isinstance(first, list):
                return [float(value) for value in first]
        embedding = data.get("embedding")
        if isinstance(embedding, list):
            return [float(value) for value in embedding]
        raise EmbeddingError("Ollama 未返回有效的嵌入向量。")

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: dict | None = None,
        stream: bool = False,
    ) -> requests.Response:
        url = f"{self.config.base_url}{path}"
        delay = self.config.retry_delay
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    json=json_data,
                    timeout=self.config.request_timeout,
                    stream=stream,
                )
                response.raise_for_status()
                return response
            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else "unknown"
                last_error = LLMConnectionError(
                    f"Ollama 请求失败: {path} 返回 HTTP {status_code}。"
                )
            except requests.RequestException as exc:
                last_error = LLMConnectionError(
                    f"无法连接到 Ollama: {self.config.base_url}。"
                )
            if attempt < self.config.max_retries - 1:
                time.sleep(delay)
                delay *= 2

        if isinstance(last_error, Exception):
            raise last_error
        raise LLMConnectionError("Ollama 请求失败。")
