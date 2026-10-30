"""Bundled synthetic clips written by scripts/make_samples.py."""

import json
from pathlib import Path
from typing import Any

SAMPLES_DIR = Path(__file__).parent / "samples"


def load_manifest(samples_dir: Path = SAMPLES_DIR) -> list[dict[str, Any]]:
    manifest = json.loads((samples_dir / "manifest.json").read_text())
    return manifest["samples"]


def find_sample(sample_id: str, samples_dir: Path = SAMPLES_DIR) -> tuple[dict[str, Any], Path]:
    for entry in load_manifest(samples_dir):
        if entry["id"] == sample_id:
            return entry, samples_dir / entry["file"]
    raise KeyError(sample_id)
