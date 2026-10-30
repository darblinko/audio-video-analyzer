"""Video description with a Gemini multimodal model through the google-genai SDK."""

import logging
import mimetypes
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 2.0


class VideoDescriber(Protocol):
    model: str

    def describe(self, video_path: Path, audio_summary: dict[str, Any]) -> str: ...


class GeminiError(RuntimeError):
    """The Gemini file upload or generation step did not produce a description."""


def build_prompt(audio_summary: dict[str, Any]) -> str:
    """Prompt that gives the model the clip-level audio features as context."""
    basic = audio_summary.get("basic_info", {})
    classification = audio_summary.get("classification", {})
    temporal = audio_summary.get("temporal_features", {})
    duration = basic.get("duration_seconds")
    tempo = temporal.get("tempo_bpm")
    duration_text = f"{duration:.1f} s" if isinstance(duration, int | float) else "unknown"
    tempo_text = f"{tempo:.0f} BPM" if isinstance(tempo, int | float) else "unknown"
    return (
        "An audio feature extractor reported the following for this clip:\n"
        f"- Duration: {duration_text}\n"
        f"- Audio type tag: {classification.get('type', 'unknown')}\n"
        f"- Energy tag: {classification.get('energy_level', 'unknown')}\n"
        f"- Estimated tempo: {tempo_text}\n\n"
        "Describe the video in plain prose:\n"
        "1. What is visible and what happens.\n"
        "2. Whether the visual content is consistent with the audio tags above.\n"
        "3. Visible events that line up with changes in the audio.\n"
        "State uncertainty where the video does not show enough to decide."
    )


def _state_name(file_obj: Any) -> str:
    state = getattr(file_obj, "state", None)
    return getattr(state, "name", str(state))


class GeminiVideoAnalyzer:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_s: float = 120.0,
        client: Any = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        if not api_key and client is None:
            raise ValueError("GOOGLE_API_KEY is not set")
        if client is None:
            from google import genai

            client = genai.Client(api_key=api_key)
        self.client = client
        self.model = model
        self.timeout_s = timeout_s
        self._sleep = sleep
        self._clock = clock

    def _wait_until_active(self, file_obj: Any) -> Any:
        deadline = self._clock() + self.timeout_s
        while _state_name(file_obj) == "PROCESSING":
            if self._clock() >= deadline:
                raise GeminiError(f"file processing exceeded {self.timeout_s:.0f} s")
            self._sleep(POLL_INTERVAL_S)
            file_obj = self.client.files.get(name=file_obj.name)
        if _state_name(file_obj) != "ACTIVE":
            raise GeminiError(f"file processing ended in state {_state_name(file_obj)}")
        return file_obj

    def describe(self, video_path: Path, audio_summary: dict[str, Any]) -> str:
        mime_type = mimetypes.guess_type(video_path.name)[0] or "video/webm"
        logger.info(
            "uploading %s (%d bytes) to the Gemini Files API",
            video_path.name,
            video_path.stat().st_size,
        )
        uploaded = self.client.files.upload(file=str(video_path), config={"mime_type": mime_type})
        try:
            active = self._wait_until_active(uploaded)
            response = self.client.models.generate_content(
                model=self.model, contents=[active, build_prompt(audio_summary)]
            )
            text = (getattr(response, "text", None) or "").strip()
            if not text:
                raise GeminiError("model returned no text")
            return text
        finally:
            try:
                self.client.files.delete(name=uploaded.name)
            except Exception:
                logger.warning("could not delete Gemini file %s", uploaded.name, exc_info=True)
