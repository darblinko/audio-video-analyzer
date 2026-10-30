from types import SimpleNamespace

import pytest

from av_analyzer.gemini import GeminiError, GeminiVideoAnalyzer, build_prompt


def _file(state: str) -> SimpleNamespace:
    return SimpleNamespace(name="files/abc", state=SimpleNamespace(name=state))


class FakeFiles:
    def __init__(self, states: list[str]):
        self.states = list(states)
        self.uploaded: list[tuple[str, dict]] = []
        self.deleted: list[str] = []

    def upload(self, file, config=None):
        self.uploaded.append((file, config))
        return _file(self.states.pop(0))

    def get(self, name):
        return _file(self.states.pop(0))

    def delete(self, name):
        self.deleted.append(name)


class FakeModels:
    def __init__(self, text: str):
        self.text = text
        self.calls: list[dict] = []

    def generate_content(self, model, contents):
        self.calls.append({"model": model, "contents": contents})
        return SimpleNamespace(text=self.text)


def _analyzer(states, text="A person waves.", timeout_s=120.0, clock=None):
    client = SimpleNamespace(files=FakeFiles(states), models=FakeModels(text))
    analyzer = GeminiVideoAnalyzer(
        "",
        "test-model",
        timeout_s=timeout_s,
        client=client,
        sleep=lambda _: None,
        clock=clock or (lambda: 0.0),
    )
    return analyzer, client


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "clip.webm"
    path.write_bytes(b"\x1a\x45\xdf\xa3")
    return path


def test_describe_uploads_polls_generates_and_deletes(video):
    analyzer, client = _analyzer(["PROCESSING", "PROCESSING", "ACTIVE"])
    assert analyzer.describe(video, {}) == "A person waves."
    assert client.files.uploaded == [(str(video), {"mime_type": "video/webm"})]
    assert client.models.calls[0]["model"] == "test-model"
    assert client.files.deleted == ["files/abc"]


def test_failed_processing_raises_and_still_deletes(video):
    analyzer, client = _analyzer(["PROCESSING", "FAILED"])
    with pytest.raises(GeminiError, match="FAILED"):
        analyzer.describe(video, {})
    assert client.files.deleted == ["files/abc"]
    assert client.models.calls == []


def test_processing_timeout_raises(video):
    ticks = iter([0.0, 5.0, 11.0])
    analyzer, client = _analyzer(
        ["PROCESSING", "PROCESSING", "PROCESSING"], timeout_s=10, clock=lambda: next(ticks)
    )
    with pytest.raises(GeminiError, match="exceeded"):
        analyzer.describe(video, {})
    assert client.files.deleted == ["files/abc"]


def test_empty_model_text_raises(video):
    analyzer, _ = _analyzer(["ACTIVE"], text="  ")
    with pytest.raises(GeminiError, match="no text"):
        analyzer.describe(video, {})


def test_missing_key_without_client_raises():
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        GeminiVideoAnalyzer("", "test-model")


def test_prompt_carries_the_audio_context():
    prompt = build_prompt(
        {
            "basic_info": {"duration_seconds": 4.25},
            "classification": {"type": "musical", "energy_level": "high_energy"},
            "temporal_features": {"tempo_bpm": 117.45},
        }
    )
    assert "4.2 s" in prompt
    assert "musical" in prompt
    assert "high_energy" in prompt
    assert "117 BPM" in prompt


def test_prompt_tolerates_missing_features():
    assert "Duration: unknown" in build_prompt({})
