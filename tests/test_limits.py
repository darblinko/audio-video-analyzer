import asyncio
import threading
import time
from pathlib import Path

from av_analyzer import features, server
from av_analyzer.config import Settings
from av_analyzer.server import MULTIPART_OVERHEAD_BYTES
from av_analyzer.storage import Storage

from .conftest import wav_bytes

BOUNDARY = "testboundary"


def _multipart(parts: list[tuple[str, str, bytes]]) -> bytes:
    body = b""
    for name, filename, payload in parts:
        body += (
            (
                f"--{BOUNDARY}\r\n"
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode()
            + payload
            + b"\r\n"
        )
    return body + f"--{BOUNDARY}--\r\n".encode()


def _post_raw(client, body, headers=None):
    return client.post(
        "/api/upload",
        content=body,
        headers={"content-type": f"multipart/form-data; boundary={BOUNDARY}", **(headers or {})},
    )


def test_declared_body_over_the_limit_is_413_before_parsing(make_client, settings):
    client = make_client(max_upload_bytes=1024)
    body = _multipart([("audio", "clip.wav", b"\x00" * (MULTIPART_OVERHEAD_BYTES + 2048))])
    assert _post_raw(client, body).status_code == 413
    assert list(settings.upload_dir.iterdir()) == []


def test_chunked_body_over_the_limit_is_413(make_client, settings):
    client = make_client(max_upload_bytes=1024)
    body = _multipart([("audio", "clip.wav", b"\x00" * (MULTIPART_OVERHEAD_BYTES + 2048))])

    def chunks():
        for start in range(0, len(body), 4096):
            yield body[start : start + 4096]

    response = _post_raw(client, chunks())
    assert response.status_code == 413
    assert list(settings.upload_dir.iterdir()) == []


def test_unexpected_file_parts_are_rejected(make_client, settings):
    client = make_client()
    body = _multipart([("audio", "clip.wav", wav_bytes()), ("extra", "more.wav", wav_bytes())])
    assert _post_raw(client, body).status_code == 422
    assert list(settings.upload_dir.iterdir()) == []


def test_repeated_audio_parts_are_rejected(make_client):
    client = make_client()
    body = _multipart([("audio", "a.wav", wav_bytes()), ("audio", "b.wav", wav_bytes())])
    assert _post_raw(client, body).status_code == 422


def test_audio_longer_than_the_limit_fails_before_full_decode(make_client):
    client = make_client(max_audio_seconds=1.0)
    files = {"audio": ("long.wav", wav_bytes(seconds=3.0), "audio/wav")}
    analysis_id = client.post("/api/upload", files=files).json()["analysis_id"]
    result = client.get(f"/api/results/{analysis_id}").json()["result"]
    assert result["status"] == "failed"
    assert "AVA_MAX_AUDIO_SECONDS" in result["error_message"]


def test_load_audio_never_decodes_past_the_limit(tmp_path, monkeypatch):
    path = tmp_path / "clip.wav"
    path.write_bytes(wav_bytes(seconds=3.0))
    # A header that understates the length must not lift the cap on decoded samples.
    monkeypatch.setattr(features.librosa, "get_duration", lambda path: 0.5)
    samples = features.load_audio(path, max_seconds=1.0)
    assert samples.size == features.SAMPLE_RATE


def test_concurrent_analyses_are_bounded(tmp_path, monkeypatch):
    lock = threading.Lock()
    active = {"now": 0, "peak": 0}

    def slow_analysis(path, **_):
        with lock:
            active["now"] += 1
            active["peak"] = max(active["peak"], active["now"])
        time.sleep(0.05)
        with lock:
            active["now"] -= 1
        return {"classification": {}}

    monkeypatch.setattr(server, "analyze_file", slow_analysis)
    settings = Settings(data_dir=tmp_path, max_concurrent_analyses=2)
    state = server.AppState(settings, Storage(settings.db_path), None, tmp_path)

    async def run_all() -> None:
        await state.storage.init()
        ids = [f"run-{index}" for index in range(5)]
        for analysis_id in ids:
            await state.storage.create(analysis_id, "clip.wav", "audio", "2026-10-30")
        await asyncio.gather(
            *(
                server.run_analysis(state, analysis_id, "audio", Path("clip.wav"))
                for analysis_id in ids
            )
        )

    asyncio.run(run_all())
    assert active["peak"] == 2
