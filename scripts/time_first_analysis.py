"""Time the first feature extraction in a new process, with and without a numba cache.

librosa compiles numba kernels on first use and caches them on disk. Each run below starts
a new Python process that imports av_analyzer.features and analyzes one bundled clip twice.
"Cold" runs point NUMBA_CACHE_DIR at a new empty directory; "warm" runs reuse a directory
that a cold run filled. Writes results/first-run-timing.json. Run from the repository root:

    uv run python scripts/time_first_analysis.py
"""

import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import date
from importlib.metadata import version
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUTPUT = REPO / "results" / "first-run-timing.json"
CLIP = "tone-440hz.wav"
RUNS = 3

CHILD = """
import json, sys, time
started = time.perf_counter()
from av_analyzer.features import analyze_file
from av_analyzer.samples import SAMPLES_DIR
imported = time.perf_counter()
analyze_file(SAMPLES_DIR / sys.argv[1])
first = time.perf_counter()
analyze_file(SAMPLES_DIR / sys.argv[1])
second = time.perf_counter()
print(json.dumps({
    "import_s": round(imported - started, 3),
    "first_analysis_s": round(first - imported, 3),
    "second_analysis_s": round(second - first, 3),
}))
"""


def _run_child(cache_dir: str) -> dict:
    env = {**os.environ, "NUMBA_CACHE_DIR": cache_dir}
    completed = subprocess.run(
        [sys.executable, "-c", CHILD, CLIP], env=env, capture_output=True, text=True, check=True
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _environment() -> dict:
    memory_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    revision = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True
    ).stdout.strip()
    return {
        "revision": revision,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "logical_cpus": os.cpu_count(),
        "memory_gib": round(memory_bytes / 2**30, 1),
        "python": platform.python_version(),
        "packages": {name: version(name) for name in ("librosa", "numba", "numpy", "scipy")},
    }


def main() -> None:
    load_before = os.getloadavg()[0]
    cold, warm = [], []
    for _ in range(RUNS):
        with tempfile.TemporaryDirectory(prefix="numba-cache-") as cache_dir:
            cold.append(_run_child(cache_dir))
            warm.append(_run_child(cache_dir))
    record = {
        "measured": date.today().isoformat(),
        "operation": f"analyze_file on {CLIP} (5 s, 22,050 Hz) in a new Python process",
        "cold": {"cache": "empty NUMBA_CACHE_DIR", "runs": cold},
        "warm": {"cache": "NUMBA_CACHE_DIR filled by the preceding cold run", "runs": warm},
        "environment": _environment(),
        # Other processes change these timings; the load average shows how busy the machine was.
        "load_average_1m": {"before": round(load_before, 2), "after": round(os.getloadavg()[0], 2)},
    }
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"cold": cold, "warm": warm}, indent=2))


if __name__ == "__main__":
    main()
