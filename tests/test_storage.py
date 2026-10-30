import asyncio

import pytest

from av_analyzer.config import DEFAULT_GEMINI_MODEL, Settings
from av_analyzer.storage import Storage


def _run(coroutine):
    return asyncio.run(coroutine)


@pytest.fixture
def storage(tmp_path):
    store = Storage(tmp_path / "nested" / "analyzer.db")
    _run(store.init())
    return store


def test_init_creates_the_database_file(storage):
    assert storage.db_path.exists()


def test_create_then_complete_round_trips_json(storage):
    _run(storage.create("a1", "clip.wav", "audio", "2026-10-30T00:00:00+00:00"))
    assert _run(storage.get("a1"))["status"] == "processing"
    _run(storage.complete("a1", {"basic_info": {"sample_rate": 22050}}, {"status": "skipped"}))
    record = _run(storage.get("a1"))
    assert record["status"] == "completed"
    assert record["audio_features"] == {"basic_info": {"sample_rate": 22050}}
    assert record["video_analysis"] == {"status": "skipped"}
    assert record["error_message"] is None


def test_fail_records_the_message(storage):
    _run(storage.create("a2", "clip.wav", "audio", "2026-10-30T00:00:00+00:00"))
    _run(storage.fail("a2", "Audio analysis failed: cannot decode clip.wav"))
    record = _run(storage.get("a2"))
    assert record["status"] == "failed"
    assert record["audio_features"] is None
    assert record["error_message"] == "Audio analysis failed: cannot decode clip.wav"


def test_list_orders_by_timestamp_descending(storage):
    _run(storage.create("old", "a.wav", "audio", "2026-10-29T00:00:00+00:00"))
    _run(storage.create("new", "b.wav", "video", "2026-10-30T00:00:00+00:00"))
    assert [record["id"] for record in _run(storage.list())] == ["new", "old"]


def test_get_missing_returns_none(storage):
    assert _run(storage.get("missing")) is None


def test_settings_defaults_and_overrides():
    defaults = Settings.from_env({})
    assert defaults.gemini_model == DEFAULT_GEMINI_MODEL
    assert defaults.google_api_key == ""
    assert defaults.keep_uploads is False
    custom = Settings.from_env(
        {
            "GEMINI_MODEL": "gemini-x",
            "AVA_KEEP_UPLOADS": "1",
            "AVA_MAX_UPLOAD_MB": "2",
            "AVA_CORS_ORIGINS": "http://a, http://b",
        }
    )
    assert custom.gemini_model == "gemini-x"
    assert custom.keep_uploads is True
    assert custom.max_upload_bytes == 2 * 1024 * 1024
    assert custom.cors_origins == ("http://a", "http://b")


def test_settings_reject_a_non_positive_upload_limit():
    with pytest.raises(ValueError):
        Settings.from_env({"AVA_MAX_UPLOAD_MB": "0"})
