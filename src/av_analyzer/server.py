"""FastAPI app: upload or pick a sample, extract audio features, describe video with Gemini."""

import asyncio
import logging
import shutil
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from av_analyzer.config import Settings
from av_analyzer.features import AudioDecodeError, analyze_file
from av_analyzer.gemini import GeminiVideoAnalyzer, VideoDescriber
from av_analyzer.guards import BodyLimitMiddleware
from av_analyzer.samples import SAMPLES_DIR, find_sample, load_manifest
from av_analyzer.storage import Storage

logger = logging.getLogger(__name__)

AUDIO_SUFFIXES = {".wav", ".flac", ".ogg", ".mp3"}
VIDEO_SUFFIXES = {".webm", ".mp4", ".mov", ".mkv"}
CHUNK_BYTES = 1024 * 1024
# Allowance for multipart boundaries, part headers and the media_type field.
MULTIPART_OVERHEAD_BYTES = 64 * 1024
UPLOAD_PARTS = {"audio": 1, "video": 1, "media_type": 1}
NO_KEY_NOTICE = "GOOGLE_API_KEY is not set. The Gemini video step was skipped."
AUDIO_ONLY_NOTICE = "Audio-only run. The Gemini step describes video and runs only for video."


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        for connection in list(self.connections):
            try:
                await connection.send_json(message)
            except Exception:
                logger.info("dropping a closed WebSocket connection")
                self.disconnect(connection)


@dataclass
class AppState:
    settings: Settings
    storage: Storage
    describer: VideoDescriber | None
    samples_dir: Path
    manager: ConnectionManager = field(default_factory=ConnectionManager)
    analysis_slots: asyncio.Semaphore = field(init=False)

    def __post_init__(self) -> None:
        # Each decoded clip and its spectrograms are held in memory; cap how many run at once.
        self.analysis_slots = asyncio.Semaphore(self.settings.max_concurrent_analyses)

    def gemini_status(self) -> dict[str, Any]:
        if self.describer is None:
            return {"enabled": False, "model": None, "notice": NO_KEY_NOTICE}
        return {"enabled": True, "model": self.describer.model, "notice": None}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _display_name(name: str | None, fallback: str) -> str:
    return (Path(name).name if name else fallback)[:120] or fallback


def _suffix(upload: UploadFile, allowed: set[str], label: str) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(415, f"{label} must be one of {', '.join(sorted(allowed))}")
    return suffix


async def _check_parts(request: Request) -> None:
    """Reject form parts other than one audio, one video and one media_type."""
    form = await request.form()
    for name in set(form.keys()):
        if len(form.getlist(name)) > UPLOAD_PARTS.get(name, 0):
            raise HTTPException(422, f"unexpected or repeated form part: {name[:40]}")


async def _save_upload(upload: UploadFile, target: Path, budget: int) -> int:
    """Stream an upload to disk. Returns bytes written; raises 413 when over budget."""
    written = 0
    with target.open("wb") as handle:
        while chunk := await upload.read(CHUNK_BYTES):
            written += len(chunk)
            if written > budget:
                raise HTTPException(413, "upload exceeds AVA_MAX_UPLOAD_MB")
            handle.write(chunk)
    if written == 0:
        raise HTTPException(400, f"{upload.filename or 'file'} is empty")
    return written


async def _gemini_step(
    state: AppState,
    analysis_id: str,
    media_type: str,
    video_path: Path | None,
    features: dict[str, Any],
) -> dict[str, Any]:
    if state.describer is None:
        notice = {"status": "skipped", "detail": NO_KEY_NOTICE}
    elif media_type != "video" or video_path is None:
        notice = {"status": "not_applicable", "detail": AUDIO_ONLY_NOTICE}
    else:
        notice = None
    if notice is not None:
        await state.manager.broadcast(
            {
                "type": "progress",
                "analysis_id": analysis_id,
                "step": "gemini",
                "message": notice["detail"],
            }
        )
        return notice

    await state.manager.broadcast(
        {
            "type": "progress",
            "analysis_id": analysis_id,
            "step": "gemini",
            "message": f"Describing the video with {state.describer.model}",
        }
    )
    video_info = {
        "file_size_mb": round(video_path.stat().st_size / 1024 / 1024, 3),
        "suffix": video_path.suffix,
    }
    try:
        text = await asyncio.to_thread(state.describer.describe, video_path, features)
    except Exception as exc:
        logger.exception("Gemini step failed for %s", analysis_id)
        return {
            "status": "failed",
            "detail": f"Gemini step failed ({type(exc).__name__})",
            "model": state.describer.model,
            "video_info": video_info,
        }
    return {
        "status": "completed",
        "analysis": text,
        "model": state.describer.model,
        "video_info": video_info,
    }


async def run_analysis(
    state: AppState,
    analysis_id: str,
    media_type: str,
    audio_path: Path,
    video_path: Path | None = None,
    cleanup_dir: Path | None = None,
) -> None:
    try:
        await state.manager.broadcast(
            {
                "type": "progress",
                "analysis_id": analysis_id,
                "step": "audio_features",
                "message": "Extracting audio features",
            }
        )
        try:
            async with state.analysis_slots:
                features = await asyncio.to_thread(
                    analyze_file, audio_path, max_seconds=state.settings.max_audio_seconds
                )
        except AudioDecodeError as exc:
            await _fail(state, analysis_id, f"Audio analysis failed: {exc}")
            return
        except Exception as exc:
            logger.exception("audio analysis failed for %s", analysis_id)
            await _fail(state, analysis_id, f"Audio analysis failed ({type(exc).__name__})")
            return
        video_analysis = await _gemini_step(state, analysis_id, media_type, video_path, features)
        await state.storage.complete(analysis_id, features, video_analysis)
        await state.manager.broadcast(
            {
                "type": "analysis_complete",
                "analysis_id": analysis_id,
                "status": "completed",
                "message": "Analysis completed",
            }
        )
    finally:
        if cleanup_dir is not None and not state.settings.keep_uploads:
            shutil.rmtree(cleanup_dir, ignore_errors=True)


async def _fail(state: AppState, analysis_id: str, message: str) -> None:
    await state.storage.fail(analysis_id, message)
    await state.manager.broadcast(
        {
            "type": "analysis_error",
            "analysis_id": analysis_id,
            "status": "failed",
            "message": message,
        }
    )


def _default_describer(settings: Settings) -> VideoDescriber | None:
    if not settings.google_api_key:
        return None
    return GeminiVideoAnalyzer(
        settings.google_api_key, settings.gemini_model, timeout_s=settings.gemini_timeout_s
    )


def create_app(
    settings: Settings | None = None,
    describer: VideoDescriber | None = None,
    samples_dir: Path = SAMPLES_DIR,
) -> FastAPI:
    if settings is None:
        load_dotenv()
        settings = Settings.from_env()
        describer = describer or _default_describer(settings)
    state = AppState(settings, Storage(settings.db_path), describer, samples_dir)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        await state.storage.init()
        gemini = state.gemini_status()
        logger.info(
            "database %s; Gemini %s",
            settings.db_path,
            gemini["model"] if gemini["enabled"] else "disabled (no GOOGLE_API_KEY)",
        )
        yield

    app = FastAPI(title="Audio/Video Analyzer API", version="0.2.0", lifespan=lifespan)
    app.state.av = state
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.add_middleware(
        BodyLimitMiddleware,
        limit=settings.max_upload_bytes + MULTIPART_OVERHEAD_BYTES,
        paths=["/api/upload"],
    )
    _register_routes(app, state)
    return app


def _register_routes(app: FastAPI, state: AppState) -> None:
    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "timestamp": _now(), "gemini": state.gemini_status()}

    @app.get("/api/samples")
    async def list_samples() -> dict[str, Any]:
        return {"samples": load_manifest(state.samples_dir)}

    def _sample_or_404(sample_id: str) -> tuple[dict[str, Any], Path]:
        try:
            return find_sample(sample_id, state.samples_dir)
        except KeyError:
            raise HTTPException(404, "sample not found") from None

    @app.get("/api/samples/{sample_id}/audio")
    async def sample_audio(sample_id: str) -> FileResponse:
        _, path = _sample_or_404(sample_id)
        return FileResponse(path, media_type="audio/wav")

    @app.post("/api/samples/{sample_id}/analyze", status_code=202)
    async def analyze_sample(sample_id: str, background: BackgroundTasks) -> dict[str, Any]:
        entry, path = _sample_or_404(sample_id)
        analysis_id = str(uuid.uuid4())
        await state.storage.create(analysis_id, entry["file"], "audio", _now())
        background.add_task(run_analysis, state, analysis_id, "audio", path)
        return {"analysis_id": analysis_id, "status": "processing"}

    @app.post("/api/upload", status_code=202)
    async def upload(
        request: Request,
        background: BackgroundTasks,
        audio: Annotated[UploadFile, File()],
        media_type: Annotated[Literal["audio", "video"], Form()] = "audio",
        video: Annotated[UploadFile | None, File()] = None,
    ) -> dict[str, Any]:
        await _check_parts(request)
        if media_type == "video" and video is None:
            raise HTTPException(422, "media_type video needs a video file part")
        audio_suffix = _suffix(audio, AUDIO_SUFFIXES, "audio")
        video_suffix = _suffix(video, VIDEO_SUFFIXES, "video") if video is not None else None
        analysis_id = str(uuid.uuid4())
        run_dir = state.settings.upload_dir / analysis_id
        run_dir.mkdir(parents=True)
        try:
            budget = state.settings.max_upload_bytes
            audio_path = run_dir / f"audio{audio_suffix}"
            budget -= await _save_upload(audio, audio_path, budget)
            video_path = None
            if video is not None and media_type == "video":
                video_path = run_dir / f"video{video_suffix}"
                await _save_upload(video, video_path, budget)
        except BaseException:
            shutil.rmtree(run_dir, ignore_errors=True)
            raise
        primary = video if video_path is not None else audio
        filename = _display_name(primary.filename, f"recording{video_suffix or audio_suffix}")
        await state.storage.create(analysis_id, filename, media_type, _now())
        await state.manager.broadcast(
            {
                "type": "status_update",
                "analysis_id": analysis_id,
                "status": "processing",
                "message": "Upload received",
            }
        )
        background.add_task(
            run_analysis, state, analysis_id, media_type, audio_path, video_path, run_dir
        )
        return {"analysis_id": analysis_id, "status": "processing"}

    @app.get("/api/results")
    async def results() -> dict[str, Any]:
        records = await state.storage.list()
        return {"count": len(records), "results": records}

    @app.get("/api/results/{analysis_id}")
    async def result(analysis_id: str) -> dict[str, Any]:
        record = await state.storage.get(analysis_id)
        if record is None:
            raise HTTPException(404, "analysis not found")
        return {"result": record}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await state.manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            state.manager.disconnect(websocket)
