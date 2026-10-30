"""Clip-level audio features and frame series computed with librosa."""

from itertools import pairwise
from pathlib import Path
from typing import Any

import librosa
import numpy as np

SAMPLE_RATE = 22050
SERIES_POINTS = 120
_EPS = 1e-10


class AudioDecodeError(ValueError):
    """The file could not be decoded as audio."""


def _check_duration(path: str | Path, max_seconds: float) -> None:
    """Reject a clip whose header reports more than max_seconds, before decoding it."""
    try:
        duration = librosa.get_duration(path=str(path))
    except Exception:
        # librosa.load below reports undecodable files; its duration cap still applies.
        return
    if duration > max_seconds:
        raise AudioDecodeError(
            f"{Path(path).name} is {duration:.0f} s long; "
            f"AVA_MAX_AUDIO_SECONDS allows {max_seconds:.0f} s"
        )


def load_audio(
    path: str | Path, sample_rate: int = SAMPLE_RATE, max_seconds: float | None = None
) -> np.ndarray:
    """Decode a file to mono float32 at sample_rate. WAV, FLAC and OGG need no ffmpeg.

    With max_seconds set, a longer clip is rejected from its header and decoding never reads
    more than max_seconds of audio, so memory use is bounded even when the header is wrong.
    """
    if max_seconds is not None:
        _check_duration(path, max_seconds)
    try:
        samples, _ = librosa.load(str(path), sr=sample_rate, mono=True, duration=max_seconds)
    except Exception as exc:
        raise AudioDecodeError(f"cannot decode {Path(path).name}") from exc
    if samples.size == 0:
        raise AudioDecodeError(f"{Path(path).name} contains no samples")
    return samples


def analyze_file(
    path: str | Path, sample_rate: int = SAMPLE_RATE, max_seconds: float | None = None
) -> dict[str, Any]:
    return extract_features(load_audio(path, sample_rate, max_seconds), sample_rate)


def _downsample(values: np.ndarray, points: int) -> list[float]:
    if values.size <= points:
        return [round(float(v), 6) for v in values]
    edges = np.linspace(0, values.size, points + 1).astype(int)
    return [round(float(values[a:b].mean()), 6) for a, b in pairwise(edges)]


def _series(rms: np.ndarray, centroid: np.ndarray, sample_rate: int) -> dict[str, list[float]]:
    times = librosa.frames_to_time(np.arange(rms.size), sr=sample_rate)
    return {
        "time_s": _downsample(times, SERIES_POINTS),
        "rms": _downsample(rms, SERIES_POINTS),
        "centroid_hz": _downsample(centroid, SERIES_POINTS),
    }


def extract_features(samples: np.ndarray, sample_rate: int) -> dict[str, Any]:
    centroid = librosa.feature.spectral_centroid(y=samples, sr=sample_rate)[0]
    rolloff = librosa.feature.spectral_rolloff(y=samples, sr=sample_rate)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=samples, sr=sample_rate)[0]
    zcr = librosa.feature.zero_crossing_rate(samples)[0]
    mfccs = librosa.feature.mfcc(y=samples, sr=sample_rate, n_mfcc=13)
    tempo, beats = librosa.beat.beat_track(y=samples, sr=sample_rate)
    rms = librosa.feature.rms(y=samples)[0]
    chroma = librosa.feature.chroma_stft(y=samples, sr=sample_rate)
    harmonic, percussive = librosa.effects.hpss(samples)
    total_abs = float(np.sum(np.abs(samples))) + _EPS

    features: dict[str, Any] = {
        "basic_info": {
            "duration_seconds": float(samples.size / sample_rate),
            "sample_rate": int(sample_rate),
            "total_samples": int(samples.size),
            "channels": 1,
        },
        "spectral_features": {
            "centroid_mean": float(np.mean(centroid)),
            "centroid_std": float(np.std(centroid)),
            "rolloff_mean": float(np.mean(rolloff)),
            "bandwidth_mean": float(np.mean(bandwidth)),
            "bandwidth_std": float(np.std(bandwidth)),
        },
        "temporal_features": {
            "zero_crossing_rate_mean": float(np.mean(zcr)),
            "zero_crossing_rate_std": float(np.std(zcr)),
            "tempo_bpm": float(np.atleast_1d(tempo)[0]),
            "beat_count": len(beats),
        },
        "energy_features": {
            "rms_mean": float(np.mean(rms)),
            "rms_std": float(np.std(rms)),
            "rms_max": float(np.max(rms)),
            "dynamic_range_db": float(20 * np.log10(np.max(rms) / (np.mean(rms) + _EPS) + _EPS)),
        },
        "mfcc_features": {f"mfcc_{i}_mean": float(np.mean(mfccs[i])) for i in range(5)},
        "harmonic_percussive": {
            "harmonic_ratio": float(np.sum(np.abs(harmonic)) / total_abs),
            "percussive_ratio": float(np.sum(np.abs(percussive)) / total_abs),
        },
        "chroma_features": {
            "chroma_mean": float(np.mean(chroma)),
            "chroma_std": float(np.std(chroma)),
        },
        "series": _series(rms, centroid, sample_rate),
    }
    features["classification"] = classify(features)
    return features


def classify(features: dict[str, Any]) -> dict[str, str]:
    """Fixed-threshold tags. These are heuristics, not a trained classifier."""
    harmonic_ratio = features["harmonic_percussive"]["harmonic_ratio"]
    rms_mean = features["energy_features"]["rms_mean"]
    tempo = features["temporal_features"]["tempo_bpm"]

    if harmonic_ratio > 0.6:
        audio_type = "musical"
    elif harmonic_ratio < 0.4:
        audio_type = "speech_or_noise"
    else:
        audio_type = "mixed"

    if rms_mean > 0.1:
        energy = "high_energy"
    elif rms_mean > 0.05:
        energy = "medium_energy"
    else:
        energy = "low_energy"

    if tempo > 120:
        tempo_category = "fast_tempo"
    elif tempo > 80:
        tempo_category = "moderate_tempo"
    else:
        tempo_category = "slow_tempo"

    return {
        "type": audio_type,
        "energy_level": energy,
        "tempo_category": tempo_category,
        "all_tags": ", ".join([audio_type, energy, tempo_category]),
    }
