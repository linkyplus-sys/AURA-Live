from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import config
from services import ChatService
from utils.exceptions import AURAPetError, ValidationError


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
config.files.avatars_dir.mkdir(parents=True, exist_ok=True)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=config.max_input_length)
    model: str | None = Field(default=None)


class SoulPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    personality: str = Field(..., min_length=1, max_length=800)
    style: str = Field(default="", max_length=400)
    scene: str = Field(default="", max_length=600)
    pet_image: str = Field(default="", max_length=255)


class WorldbookPayload(BaseModel):
    entries: Any


class ModelPayload(BaseModel):
    model: str = Field(..., min_length=1, max_length=120)


class BaseUrlPayload(BaseModel):
    base_url: str = Field(..., min_length=1, max_length=255)


class RegenerateRequest(BaseModel):
    model: str | None = Field(default=None)


def sse_event(payload: dict[str, Any], event: str = "message") -> str:
    body = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {body}\n\n"


@lru_cache
def get_chat_service() -> ChatService:
    return ChatService(config)


def get_runtime_state(service: ChatService) -> dict[str, Any]:
    try:
        models = service.get_available_models()
        healthy = True
        error = ""
    except AURAPetError as exc:
        models = []
        healthy = False
        error = str(exc)
    current_model = service.current_model
    if not current_model and models:
        current_model = models[0]
    return {
        "healthy": healthy,
        "error": error,
        "models": models,
        "current_model": current_model,
        "memory_count": service.get_memory_count(),
        "memory_error": service.get_memory_error(),
        "embed_model": service.llm.config.embed_model,
        "base_url": service.llm.config.base_url,
    }


def get_bootstrap_payload(service: ChatService) -> dict[str, Any]:
    return {
        "app_title": config.app_title,
        "history": service.get_conversation_history(),
        "soul": service.load_soul(),
        "worldbook": service.load_worldbook(),
        "runtime": get_runtime_state(service),
    }


app = FastAPI(title=config.app_title, docs_url="/docs", redoc_url=None)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/avatars", StaticFiles(directory=str(config.files.avatars_dir)), name="avatars")


@app.exception_handler(ValidationError)
def handle_validation_error(_: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(AURAPetError)
def handle_app_error(_: Request, exc: AURAPetError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/settings")
def settings_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "settings.html")


@app.get("/memories")
def memories_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "memories.html")


@app.get("/api/bootstrap")
def bootstrap() -> dict[str, Any]:
    service = get_chat_service()
    return get_bootstrap_payload(service)


@app.get("/api/health")
def health() -> dict[str, Any]:
    service = get_chat_service()
    return get_runtime_state(service)


@app.get("/api/history")
def history() -> dict[str, Any]:
    service = get_chat_service()
    return {"history": service.get_conversation_history()}


@app.delete("/api/history")
def clear_history() -> dict[str, Any]:
    service = get_chat_service()
    service.clear_history()
    return {"history": []}


@app.delete("/api/memory")
def clear_memory() -> dict[str, Any]:
    service = get_chat_service()
    service.clear_memories()
    return {"memory_count": service.get_memory_count()}


@app.get("/api/memories")
def memories() -> dict[str, Any]:
    service = get_chat_service()
    return {
        "memories": service.get_memories(),
        "memory_count": service.get_memory_count(),
    }


@app.get("/api/config/soul")
def get_soul() -> dict[str, Any]:
    service = get_chat_service()
    return {"soul": service.load_soul()}


@app.put("/api/config/soul")
def update_soul(payload: SoulPayload) -> dict[str, Any]:
    service = get_chat_service()
    soul = service.save_soul(payload.model_dump())
    return {"soul": soul}


@app.get("/api/config/worldbook")
def get_worldbook() -> dict[str, Any]:
    service = get_chat_service()
    return {"worldbook": service.load_worldbook()}


@app.put("/api/config/worldbook")
def update_worldbook(payload: WorldbookPayload) -> dict[str, Any]:
    service = get_chat_service()
    worldbook = service.save_worldbook(payload.entries)
    return {"worldbook": worldbook}


@app.put("/api/runtime/model")
def update_runtime_model(payload: ModelPayload) -> dict[str, Any]:
    service = get_chat_service()
    service.set_model(payload.model)
    return get_runtime_state(service)


@app.put("/api/runtime/base-url")
def update_runtime_base_url(payload: BaseUrlPayload) -> dict[str, Any]:
    service = get_chat_service()
    service.set_base_url(payload.base_url)
    return get_runtime_state(service)


@app.post("/api/chat/stream")
def chat_stream(payload: ChatRequest) -> StreamingResponse:
    service = get_chat_service()
    if payload.model:
        service.set_model(payload.model)

    def event_stream() -> Iterator[str]:
        yield sse_event({"runtime": get_runtime_state(service)}, event="status")
        try:
            for chunk in service.chat(payload.message):
                yield sse_event({"content": chunk}, event="chunk")
            yield sse_event(
                {
                    "history": service.get_conversation_history(),
                    "runtime": get_runtime_state(service),
                },
                event="done",
            )
        except (ValidationError, AURAPetError) as exc:
            yield sse_event({"message": str(exc)}, event="error")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat/regenerate")
def chat_regenerate(payload: RegenerateRequest) -> StreamingResponse:
    service = get_chat_service()
    if payload.model:
        service.set_model(payload.model)

    def event_stream() -> Iterator[str]:
        removed_turn: list[dict[str, str]] = []
        yield sse_event({"runtime": get_runtime_state(service)}, event="status")
        try:
            message, removed_turn = service.prepare_regeneration()
            for chunk in service.chat(message):
                yield sse_event({"content": chunk}, event="chunk")
            yield sse_event(
                {
                    "history": service.get_conversation_history(),
                    "runtime": get_runtime_state(service),
                },
                event="done",
            )
        except (ValidationError, AURAPetError) as exc:
            if removed_turn:
                service.restore_turn(removed_turn)
            yield sse_event({"message": str(exc)}, event="error")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
