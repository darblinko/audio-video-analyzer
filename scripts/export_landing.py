"""Analyze the bundled sample clips and write results/sample-features.json and docs/data.json.

Run from the repository root after committing code changes, so the recorded revision matches:

    uv run python scripts/export_landing.py
"""

import json
import subprocess
from datetime import date
from pathlib import Path

from av_analyzer.features import analyze_file
from av_analyzer.samples import SAMPLES_DIR, load_manifest

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results" / "sample-features.json"
DATA = REPO / "docs" / "data.json"
SOURCE = "results/sample-features.json (scripts/export_landing.py)"


def _revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def measure() -> list[dict]:
    rows = []
    for entry in load_manifest():
        features = analyze_file(SAMPLES_DIR / entry["file"])
        rows.append(
            {
                "id": entry["id"],
                "title": entry["title"],
                "expected": entry["expected"],
                "features": features,
            }
        )
    return rows


def _by_id(rows: list[dict]) -> dict[str, dict]:
    return {row["id"]: row["features"] for row in rows}


def build_charts(rows: list[dict]) -> list[dict]:
    features = _by_id(rows)
    tone = features["tone-440hz"]["spectral_features"]["centroid_mean"]
    tempo = features["click-track-120bpm"]["temporal_features"]["tempo_bpm"]
    click_series = features["click-track-120bpm"]["series"]
    speech_series = features["speech-like"]["series"]
    return [
        {
            "name": "known-values",
            "type": "stats",
            "title": "Measured against generated values",
            "source": SOURCE,
            "alt": f"Tone centroid {tone:.1f} Hz for a 440 Hz sine; click tempo {tempo:.1f} BPM "
            "for a 120 BPM track.",
            "tiles": [
                {
                    "label": "Centroid of the 440 Hz tone",
                    "value": f"{tone:.1f} Hz",
                    "note": f"{(tone - 440) / 440:+.1%} from the generated frequency",
                },
                {
                    "label": "Tempo of the 120 BPM click track",
                    "value": f"{tempo:.1f} BPM",
                    "note": f"{(tempo - 120) / 120:+.1%} from the generated tempo",
                },
                {"label": "Bundled clips", "value": str(len(rows)), "note": "5 s each, 22,050 Hz"},
            ],
        },
        {
            "name": "centroid-by-clip",
            "type": "hbar",
            "title": "Mean spectral centroid per sample clip",
            "subtitle": "Hz, librosa spectral_centroid averaged over frames",
            "source": SOURCE,
            "alt": ", ".join(
                f"{row['id']} {features[row['id']]['spectral_features']['centroid_mean']:.0f} Hz"
                for row in rows
            )
            + ".",
            "format": "number",
            "data": [
                {
                    "label": row["id"],
                    "value": round(features[row["id"]]["spectral_features"]["centroid_mean"], 1),
                }
                for row in rows
            ],
        },
        {
            "name": "harmonic-share",
            "type": "hbar",
            "title": "Harmonic share of signal magnitude per sample clip",
            "subtitle": "librosa HPSS, sum of harmonic magnitude over sum of input magnitude",
            "source": SOURCE,
            "alt": ", ".join(
                f"{row['id']} {features[row['id']]['harmonic_percussive']['harmonic_ratio']:.0%}"
                for row in rows
            )
            + ".",
            "format": "percent",
            "max": 1,
            "threshold": {"value": 0.6, "label": "musical tag above 60%"},
            "data": [
                {
                    "label": row["id"],
                    "value": round(features[row["id"]]["harmonic_percussive"]["harmonic_ratio"], 3),
                }
                for row in rows
            ],
        },
        {
            "name": "rms-over-time",
            "type": "line",
            "title": "RMS energy over time, click track and speech-like clip",
            "subtitle": "Frame RMS averaged into 120 points over 5 s",
            "source": SOURCE,
            "alt": "The click track shows 10 evenly spaced peaks; the speech-like clip shows "
            "syllable-length bursts separated by pauses.",
            "format": "decimal3",
            "x": [f"{t:.2f}" for t in click_series["time_s"]],
            "series": [
                {"name": "Click track, 120 BPM", "values": click_series["rms"]},
                {"name": "Speech-like", "values": speech_series["rms"]},
            ],
        },
    ]


def main() -> None:
    rows = measure()
    revision = _revision()
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps({"revision": revision, "clips": rows}, indent=2) + "\n")
    meta = {
        "repo": "audio-video-analyzer",
        "revision": revision,
        "measured": date.today().isoformat(),
    }
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps({"meta": meta, "charts": build_charts(rows)}, indent=2) + "\n")
    print(f"wrote {RESULTS.relative_to(REPO)} and {DATA.relative_to(REPO)} at {revision}")


if __name__ == "__main__":
    main()
