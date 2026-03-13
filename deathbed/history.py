"""Persistent per-repo scan history for trend and sparkline tracking."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .scoring import FileMetrics

log = logging.getLogger(__name__)

__all__ = ["load_history", "save_scan", "enrich_with_history", "get_repo_score_delta"]

_HISTORY_DIR = Path.home() / ".deathbed"
_HISTORY_FILE = _HISTORY_DIR / "history.json"
_MAX_SCANS = 10

_SPARKLINE_CHARS = "▁▂▃▄▅▆▇█"


def _sparkline(scores: list[int]) -> str:
    """Convert a list of up-to-5 scores (0-100) into a sparkline string."""
    if not scores:
        return ""
    recent = scores[-5:]
    lo, hi = min(recent), max(recent)
    rng = hi - lo
    chars = []
    for s in recent:
        idx = 4 if rng == 0 else round((s - lo) / rng * 7)
        chars.append(_SPARKLINE_CHARS[idx])
    return "".join(chars)


def _load_all() -> dict:
    try:
        if _HISTORY_FILE.is_file():
            return json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.debug("Could not load history file: %s", exc)
    return {}


def _save_all(data: dict) -> None:
    try:
        _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        _HISTORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        log.debug("Could not save history file: %s", exc)


def _history_key(repo_root: Path) -> str:
    return str(repo_root.resolve())


def load_history(repo_root: Path) -> list[dict]:
    """Return the list of historical scans for this repo (oldest first)."""
    return _load_all().get(_history_key(repo_root), [])


def save_scan(repo_root: Path, results: list[FileMetrics], repo_score: int) -> None:
    """Append a scan record to history, capping at _MAX_SCANS per repo."""
    entry: dict = {
        "timestamp": int(time.time()),
        "repo_score": repo_score,
        "files": {m.path: m.composite_score for m in results},
    }
    all_data = _load_all()
    key = _history_key(repo_root)
    scans = all_data.get(key, [])
    scans.append(entry)
    all_data[key] = scans[-_MAX_SCANS:]
    _save_all(all_data)


def enrich_with_history(results: list[FileMetrics], repo_root: Path) -> None:
    """Set score_delta and sparkline on each FileMetrics in-place using history."""
    scans = load_history(repo_root)
    if not scans:
        return

    file_history: dict[str, list[int]] = {}
    for scan in scans:
        for path, score in scan.get("files", {}).items():
            file_history.setdefault(path, []).append(score)

    for m in results:
        hist = file_history.get(m.path, [])
        if hist:
            m.score_delta = m.composite_score - hist[-1]
            m.sparkline = _sparkline(hist + [m.composite_score])


def get_repo_score_delta(repo_root: Path, current_score: int) -> int | None:
    """Return current_score minus last saved repo_score, or None if no history."""
    scans = load_history(repo_root)
    if not scans:
        return None
    last_repo_score = scans[-1].get("repo_score")
    if last_repo_score is None:
        return None
    return current_score - last_repo_score
