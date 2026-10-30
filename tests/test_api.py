import pytest

from av_analyzer.server import AUDIO_ONLY_NOTICE, NO_KEY_NOTICE

from .conftest import StubDescriber, wav_bytes

FAKE_WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64


def _upload(client, media_type="audio", with_video=False, audio=None, audio_name="clip.wav"):
    files = {"audio": (audio_name, audio if audio is not None else wav_bytes(), "audio/wav")}
    if with_video:
        files["video"] = ("recording.webm", FAKE_WEBM, "video/webm")
    return client.post("/api/upload", files=files, data={"media_type": media_type})


def test_health_reports_gemini_disabled_without_a_key(make_client):
    body = make_client().get("/api/health").json()
    assert body["status"] == "ok"
    assert body["gemini"] == {"enabled": False, "model": None, "notice": NO_KEY_NOTICE}


def test_health_reports_the_configured_model(make_client):
    body = make_client(StubDescriber()).get("/api/health").json()
    assert body["gemini"]["enabled"] is True
    assert body["gemini"]["model"] == "stub-model"


def test_samples_endpoint_lists_bundled_clips(make_client):
    samples = make_client().get("/api/samples").json()["samples"]
    assert len(samples) == 5
    assert {"id", "title", "description", "file"} <= set(samples[0])


def test_sample_analysis_completes_with_gemini_skipped_notice(make_client):
    client = make_client()
    response = client.post("/api/samples/tone-440hz/analyze")
    assert response.status_code == 202
    result = client.get(f"/api/results/{response.json()['analysis_id']}").json()["result"]
    assert result["status"] == "completed"
    assert result["filename"] == "tone-440hz.wav"
    assert result["audio_features"]["classification"]["type"] == "musical"
    assert result["video_analysis"] == {"status": "skipped", "detail": NO_KEY_NOTICE}


def test_unknown_sample_is_404(make_client):
    client = make_client()
    assert client.post("/api/samples/nope/analyze").status_code == 404
    assert client.get("/api/samples/nope/audio").status_code == 404


def test_sample_audio_is_served_as_wav(make_client):
    response = make_client().get("/api/samples/tone-440hz/audio")
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content[:4] == b"RIFF"


def test_audio_upload_with_a_key_marks_gemini_not_applicable(make_client):
    describer = StubDescriber()
    client = make_client(describer)
    analysis_id = _upload(client).json()["analysis_id"]
    result = client.get(f"/api/results/{analysis_id}").json()["result"]
    assert result["status"] == "completed"
    assert result["video_analysis"] == {"status": "not_applicable", "detail": AUDIO_ONLY_NOTICE}
    assert describer.calls == []


def test_video_upload_reaches_the_gemini_step(make_client):
    describer = StubDescriber(text="Two hands clap.")
    client = make_client(describer)
    response = _upload(client, media_type="video", with_video=True)
    assert response.status_code == 202
    result = client.get(f"/api/results/{response.json()['analysis_id']}").json()["result"]
    assert result["media_type"] == "video"
    assert result["filename"] == "recording.webm"
    assert result["video_analysis"]["status"] == "completed"
    assert result["video_analysis"]["analysis"] == "Two hands clap."
    assert result["video_analysis"]["model"] == "stub-model"
    ((video_path, summary),) = describer.calls
    assert video_path.suffix == ".webm"
    assert "classification" in summary


def test_video_upload_without_a_key_is_skipped_with_notice(make_client):
    client = make_client()
    analysis_id = _upload(client, media_type="video", with_video=True).json()["analysis_id"]
    result = client.get(f"/api/results/{analysis_id}").json()["result"]
    assert result["status"] == "completed"
    assert result["video_analysis"]["status"] == "skipped"


def test_gemini_failure_keeps_the_audio_features(make_client):
    client = make_client(StubDescriber(error=RuntimeError("quota")))
    analysis_id = _upload(client, media_type="video", with_video=True).json()["analysis_id"]
    result = client.get(f"/api/results/{analysis_id}").json()["result"]
    assert result["status"] == "completed"
    assert result["audio_features"]["basic_info"]["sample_rate"] == 22050
    assert result["video_analysis"]["status"] == "failed"
    assert "quota" not in result["video_analysis"]["detail"]


def test_video_media_type_needs_a_video_part(make_client):
    assert _upload(make_client(), media_type="video").status_code == 422


def test_unknown_media_type_is_rejected(make_client):
    assert _upload(make_client(), media_type="image").status_code == 422


def test_unsupported_audio_suffix_is_415(make_client):
    assert _upload(make_client(), audio_name="clip.exe").status_code == 415


def test_oversized_upload_is_413_and_leaves_no_files(make_client, settings):
    client = make_client(max_upload_bytes=1024)
    assert _upload(client).status_code == 413
    assert list(settings.upload_dir.iterdir()) == []
    assert client.get("/api/results").json()["count"] == 0


def test_empty_upload_is_400(make_client):
    assert _upload(make_client(), audio=b"").status_code == 400


def test_undecodable_audio_marks_the_run_failed(make_client):
    client = make_client()
    analysis_id = _upload(client, audio=b"RIFF0000garbage").json()["analysis_id"]
    result = client.get(f"/api/results/{analysis_id}").json()["result"]
    assert result["status"] == "failed"
    assert result["error_message"].startswith("Audio analysis failed")


def test_uploads_are_deleted_after_the_run(make_client, settings):
    client = make_client()
    _upload(client)
    assert list(settings.upload_dir.iterdir()) == []


def test_uploads_are_kept_when_configured(make_client, settings):
    client = make_client(keep_uploads=True)
    analysis_id = _upload(client).json()["analysis_id"]
    assert (settings.upload_dir / analysis_id / "audio.wav").exists()


def test_results_are_listed_newest_first(make_client):
    client = make_client()
    first = client.post("/api/samples/white-noise/analyze").json()["analysis_id"]
    second = client.post("/api/samples/chord-a-major/analyze").json()["analysis_id"]
    body = client.get("/api/results").json()
    assert body["count"] == 2
    assert [record["id"] for record in body["results"]] == [second, first]


def test_missing_result_is_404(make_client):
    assert make_client().get("/api/results/does-not-exist").status_code == 404


def test_websocket_receives_progress_and_completion(make_client):
    client = make_client()
    with client.websocket_connect("/ws") as websocket:
        analysis_id = client.post("/api/samples/tone-440hz/analyze").json()["analysis_id"]
        messages = [websocket.receive_json() for _ in range(3)]
    assert [message["type"] for message in messages] == [
        "progress",
        "progress",
        "analysis_complete",
    ]
    assert {message["analysis_id"] for message in messages} == {analysis_id}
    assert messages[1]["message"] == NO_KEY_NOTICE


def test_uploads_are_deleted_when_the_database_insert_fails(make_client, settings):
    client = make_client()

    async def locked(*_args, **_kwargs):
        raise RuntimeError("database is locked")

    client.app.state.av.storage.create = locked
    with pytest.raises(RuntimeError, match="database is locked"):
        _upload(client)
    assert list(settings.upload_dir.iterdir()) == []
