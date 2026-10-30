import io
import wave
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from av_analyzer.config import Settings
from av_analyzer.server import create_app


class StubDescriber:
    """Records calls instead of contacting Gemini."""

    model = "stub-model"

    def __init__(self, text: str = "A stub description.", error: Exception | None = None):
        self.text = text
        self.error = error
        self.calls: list[tuple[Path, dict]] = []

    def describe(self, video_path: Path, audio_summary: dict) -> str:
        self.calls.append((video_path, audio_summary))
        assert video_path.exists()
        if self.error is not None:
            raise self.error
        return self.text


def wav_bytes(seconds: float = 1.0, frequency_hz: float = 440.0, sample_rate: int = 22050) -> bytes:
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    pcm = np.round(0.3 * np.sin(2 * np.pi * frequency_hz * t) * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return buffer.getvalue()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


@pytest.fixture
def make_client(settings: Settings):
    clients = []

    def factory(describer=None, **overrides) -> TestClient:
        effective = Settings(**{**settings.__dict__, **overrides})
        client = TestClient(create_app(effective, describer=describer))
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)
