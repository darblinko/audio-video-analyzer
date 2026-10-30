import importlib.util
import wave
from pathlib import Path

import numpy as np
import pytest

from av_analyzer.features import (
    SERIES_POINTS,
    AudioDecodeError,
    analyze_file,
    classify,
)
from av_analyzer.samples import SAMPLES_DIR, load_manifest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def sample_features() -> dict[str, dict]:
    return {entry["id"]: analyze_file(SAMPLES_DIR / entry["file"]) for entry in load_manifest()}


def test_manifest_lists_five_clips_that_exist():
    entries = load_manifest()
    assert [entry["id"] for entry in entries] == [
        "tone-440hz",
        "chord-a-major",
        "click-track-120bpm",
        "white-noise",
        "speech-like",
    ]
    for entry in entries:
        assert (SAMPLES_DIR / entry["file"]).stat().st_size > 0


def test_tone_centroid_is_within_two_percent_of_440_hz(sample_features):
    centroid = sample_features["tone-440hz"]["spectral_features"]["centroid_mean"]
    assert centroid == pytest.approx(440.0, rel=0.02)


def test_tone_is_tagged_musical(sample_features):
    tone = sample_features["tone-440hz"]
    assert tone["harmonic_percussive"]["harmonic_ratio"] > 0.9
    assert tone["classification"]["type"] == "musical"


def test_click_track_tempo_is_within_five_percent_of_120_bpm(sample_features):
    tempo = sample_features["click-track-120bpm"]["temporal_features"]["tempo_bpm"]
    assert tempo == pytest.approx(120.0, rel=0.05)


def test_click_track_is_percussive(sample_features):
    ratios = sample_features["click-track-120bpm"]["harmonic_percussive"]
    assert ratios["percussive_ratio"] > ratios["harmonic_ratio"]


def test_white_noise_has_high_centroid_and_zero_crossing_rate(sample_features):
    noise = sample_features["white-noise"]
    assert noise["spectral_features"]["centroid_mean"] > 4000
    assert noise["temporal_features"]["zero_crossing_rate_mean"] > 0.4


def test_speech_like_clip_has_more_dynamics_than_the_tone(sample_features):
    speech = sample_features["speech-like"]["energy_features"]["dynamic_range_db"]
    tone = sample_features["tone-440hz"]["energy_features"]["dynamic_range_db"]
    assert speech > tone + 3


def test_series_are_aligned_and_downsampled(sample_features):
    for features in sample_features.values():
        series = features["series"]
        assert len(series["time_s"]) == len(series["rms"]) == len(series["centroid_hz"])
        assert 0 < len(series["rms"]) <= SERIES_POINTS
        assert series["time_s"] == sorted(series["time_s"])


def test_basic_info_matches_the_clip(sample_features):
    info = sample_features["tone-440hz"]["basic_info"]
    assert info["sample_rate"] == 22050
    assert info["duration_seconds"] == pytest.approx(5.0)


@pytest.mark.parametrize(
    ("harmonic", "rms", "tempo", "expected"),
    [
        (0.7, 0.2, 130.0, ("musical", "high_energy", "fast_tempo")),
        (0.5, 0.07, 100.0, ("mixed", "medium_energy", "moderate_tempo")),
        (0.3, 0.01, 60.0, ("speech_or_noise", "low_energy", "slow_tempo")),
    ],
)
def test_classify_threshold_branches(harmonic, rms, tempo, expected):
    tags = classify(
        {
            "harmonic_percussive": {"harmonic_ratio": harmonic},
            "energy_features": {"rms_mean": rms},
            "temporal_features": {"tempo_bpm": tempo},
        }
    )
    assert (tags["type"], tags["energy_level"], tags["tempo_category"]) == expected
    assert tags["all_tags"] == ", ".join(expected)


def test_undecodable_file_raises_audio_decode_error(tmp_path):
    bogus = tmp_path / "bogus.wav"
    bogus.write_bytes(b"not audio at all")
    with pytest.raises(AudioDecodeError):
        analyze_file(bogus)


def _read_pcm(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        return np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2").astype(int)


def test_sample_generator_reproduces_the_bundled_clips(tmp_path):
    spec = importlib.util.spec_from_file_location("make_samples", REPO / "scripts/make_samples.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.write_samples(tmp_path)
    assert (tmp_path / "manifest.json").read_text() == (SAMPLES_DIR / "manifest.json").read_text()
    for entry in load_manifest():
        regenerated = _read_pcm(tmp_path / entry["file"])
        bundled = _read_pcm(SAMPLES_DIR / entry["file"])
        assert regenerated.shape == bundled.shape
        assert np.max(np.abs(regenerated - bundled)) <= 1
