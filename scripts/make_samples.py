"""Generate the bundled synthetic demo clips.

Every clip is computed from numpy with a fixed seed: tones, a click track, white noise and a
speech-like signal built from harmonics shaped by vowel formants. No recording of a person is
used. Run from the repository root:

    uv run python scripts/make_samples.py
"""

import argparse
import json
import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 22050
DURATION_S = 5.0
SEED = 20261030
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "src" / "av_analyzer" / "samples"

# F1, F2, F3 in Hz: adult male averages from Peterson and Barney (1952).
VOWEL_FORMANTS = {"a": (730, 1090, 2440), "i": (270, 2290, 3010), "u": (300, 870, 2240)}


def _time() -> np.ndarray:
    return np.arange(int(SAMPLE_RATE * DURATION_S)) / SAMPLE_RATE


def tone(frequency_hz: float = 440.0, amplitude: float = 0.3) -> np.ndarray:
    return amplitude * np.sin(2 * np.pi * frequency_hz * _time())


def chord(amplitude: float = 0.3) -> np.ndarray:
    t = _time()
    signal = np.zeros_like(t)
    for root in (220.0, 277.18, 329.63):
        for harmonic, weight in ((1, 1.0), (2, 0.5), (3, 0.25)):
            signal += weight * np.sin(2 * np.pi * root * harmonic * t)
    swell = 0.75 + 0.25 * np.sin(2 * np.pi * 0.4 * t)
    return amplitude * swell * signal / np.max(np.abs(signal))


def click_track(rng: np.random.Generator, bpm: float = 120.0) -> np.ndarray:
    t = _time()
    signal = np.zeros_like(t)
    click_len = int(0.03 * SAMPLE_RATE)
    click_t = np.arange(click_len) / SAMPLE_RATE
    decay = np.exp(-click_t / 0.006)
    for onset in np.arange(0.0, DURATION_S, 60.0 / bpm):
        start = int(onset * SAMPLE_RATE)
        end = min(start + click_len, t.size)
        burst = np.sin(2 * np.pi * 2000 * click_t) + 0.3 * rng.standard_normal(click_len)
        signal[start:end] += 0.6 * (decay * burst)[: end - start]
    return signal


def white_noise(rng: np.random.Generator, sigma: float = 0.1) -> np.ndarray:
    return np.clip(sigma * rng.standard_normal(_time().size), -1.0, 1.0)


def _vowel(rng: np.random.Generator, n: int, vowel: str) -> np.ndarray:
    t = np.arange(n) / SAMPLE_RATE
    f0 = 120 + 15 * np.sin(2 * np.pi * rng.uniform(1.5, 3.0) * t) + rng.uniform(-10, 10)
    phase = 2 * np.pi * np.cumsum(f0) / SAMPLE_RATE
    signal = np.zeros(n)
    for k in range(1, 30):
        frequency = k * float(np.mean(f0))
        if frequency > 4000:
            break
        gain = sum(np.exp(-(((frequency - f) / 90.0) ** 2)) for f in VOWEL_FORMANTS[vowel])
        signal += (gain + 0.02) * np.sin(k * phase) / k**0.5
    return signal


def speech_like(rng: np.random.Generator) -> np.ndarray:
    total = _time().size
    signal = np.zeros(total)
    position = int(0.2 * SAMPLE_RATE)
    vowels = list(VOWEL_FORMANTS)
    while position < total - SAMPLE_RATE // 5:
        length = int(rng.uniform(0.12, 0.28) * SAMPLE_RATE)
        length = min(length, total - position)
        envelope = np.sin(np.pi * np.arange(length) / length) ** 2
        syllable = envelope * _vowel(rng, length, vowels[int(rng.integers(len(vowels)))])
        signal[position : position + length] += syllable
        position += length
        if rng.random() < 0.35:
            fricative_len = int(0.06 * SAMPLE_RATE)
            noise = np.diff(rng.standard_normal(fricative_len + 1)) * 0.15
            end = min(position + fricative_len, total)
            signal[position:end] += noise[: end - position]
            position = end
        position += int(rng.uniform(0.03, 0.12) * SAMPLE_RATE)
        if rng.random() < 0.15:
            position += int(0.35 * SAMPLE_RATE)
    return 0.35 * signal / np.max(np.abs(signal))


def build_samples(seed: int = SEED) -> list[dict]:
    rng = np.random.default_rng(seed)
    return [
        {
            "id": "tone-440hz",
            "title": "Sine tone, 440 Hz",
            "description": "Pure 440 Hz sine at amplitude 0.3.",
            "expected": {"frequency_hz": 440.0},
            "signal": tone(),
        },
        {
            "id": "chord-a-major",
            "title": "A major chord",
            "description": "220, 277.18 and 329.63 Hz with two overtones each and a 0.4 Hz swell.",
            "expected": {},
            "signal": chord(),
        },
        {
            "id": "click-track-120bpm",
            "title": "Click track, 120 BPM",
            "description": "30 ms decaying 2 kHz clicks with noise, one every 0.5 s.",
            "expected": {"tempo_bpm": 120.0},
            "signal": click_track(rng),
        },
        {
            "id": "white-noise",
            "title": "White noise",
            "description": "Gaussian white noise, standard deviation 0.1.",
            "expected": {},
            "signal": white_noise(rng),
        },
        {
            "id": "speech-like",
            "title": "Speech-like synthetic signal",
            "description": "Harmonics of a 95 to 145 Hz pitch shaped by /a/, /i/ and /u/ formants, "
            "syllable envelopes, noise bursts and pauses. Not a recording.",
            "expected": {},
            "signal": speech_like(rng),
        },
    ]


def write_wav(path: Path, signal: np.ndarray) -> None:
    pcm = np.round(np.clip(signal, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm.tobytes())


def write_samples(out_dir: Path, seed: int = SEED) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for sample in build_samples(seed):
        filename = f"{sample['id']}.wav"
        write_wav(out_dir / filename, sample["signal"])
        entry = {key: value for key, value in sample.items() if key != "signal"}
        manifest.append({**entry, "file": filename})
    payload = {
        "seed": seed,
        "sample_rate": SAMPLE_RATE,
        "duration_s": DURATION_S,
        "generator": "scripts/make_samples.py",
        "samples": manifest,
    }
    (out_dir / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    for entry in write_samples(args.out, args.seed):
        print(f"wrote {args.out / entry['file']}")


if __name__ == "__main__":
    main()
