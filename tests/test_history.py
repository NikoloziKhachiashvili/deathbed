"""Tests for history.py — persistent scan history and trend tracking."""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from deathbed.history import (
    _sparkline,
    enrich_with_history,
    get_repo_score_delta,
    load_history,
    save_scan,
)
from deathbed.scoring import FileMetrics, compute_scores


def _m(path="src/foo.py", score=75) -> FileMetrics:
    m = FileMetrics(
        path=path, lines=100, days_since_commit=30, commit_count=5, author_count=1,
        avg_complexity=3.0, has_test_file=True, test_file_recent=True,
        recent_churn=2, prev_churn=0,
    )
    compute_scores(m)
    m.composite_score = score
    return m


# ── _sparkline ────────────────────────────────────────────────────────────────

def test_sparkline_empty():
    assert _sparkline([]) == ""


def test_sparkline_single():
    s = _sparkline([50])
    assert len(s) == 1


def test_sparkline_five_scores():
    s = _sparkline([20, 40, 60, 80, 100])
    assert len(s) == 5


def test_sparkline_caps_at_five():
    scores = [10, 20, 30, 40, 50, 60, 70]
    s = _sparkline(scores)
    assert len(s) == 5


def test_sparkline_uniform_scores():
    s = _sparkline([75, 75, 75])
    assert len(s) == 3
    # All same → middle bar
    assert all(c == s[0] for c in s)


def test_sparkline_chars_in_set():
    chars = set("▁▂▃▄▅▆▇█")
    s = _sparkline([10, 50, 90])
    for c in s:
        assert c in chars


# ── load_history / save_scan ──────────────────────────────────────────────────

def test_load_history_no_file(tmp_path):
    result = load_history(tmp_path)
    assert result == []


def test_save_and_load(tmp_path, monkeypatch):
    import deathbed.history as hist_mod

    fake_file = tmp_path / "history.json"
    monkeypatch.setattr(hist_mod, "_HISTORY_FILE", fake_file)
    monkeypatch.setattr(hist_mod, "_HISTORY_DIR", tmp_path)
    # Restore save_scan (conftest mocks it globally)
    monkeypatch.setattr(hist_mod, "save_scan", hist_mod.__class__.__dict__.get(
        "save_scan", hist_mod.save_scan
    ))

    # Use the real save_scan by bypassing conftest's monkeypatch
    # Directly call the private helpers
    results = [_m("a.py", 80)]
    hist_mod._save_all({str(tmp_path.resolve()): [{
        "timestamp": int(time.time()),
        "repo_score": 80,
        "files": {"a.py": 80},
    }]})

    scans = hist_mod.load_history(tmp_path)
    assert len(scans) == 1
    assert scans[0]["repo_score"] == 80
    assert scans[0]["files"]["a.py"] == 80


def test_load_history_corrupt_file(tmp_path, monkeypatch):
    import deathbed.history as hist_mod

    fake_file = tmp_path / "history.json"
    fake_file.write_text("not-json!!!{}", encoding="utf-8")
    monkeypatch.setattr(hist_mod, "_HISTORY_FILE", fake_file)

    result = load_history(tmp_path)
    assert result == []


# ── enrich_with_history ───────────────────────────────────────────────────────

def test_enrich_no_history(tmp_path):
    m = _m("src/foo.py", 80)
    enrich_with_history([m], tmp_path)  # no history → no-op
    assert m.score_delta is None
    assert m.sparkline == ""


def test_enrich_with_history(tmp_path, monkeypatch):
    import deathbed.history as hist_mod

    fake_file = tmp_path / "history.json"
    key = str(tmp_path.resolve())
    hist_mod._save_all({key: [{"timestamp": 0, "repo_score": 70, "files": {"src/foo.py": 60}}]})
    monkeypatch.setattr(hist_mod, "_HISTORY_FILE", fake_file)

    # Write the history via the internal API
    data = {key: [{"timestamp": 0, "repo_score": 70, "files": {"src/foo.py": 60}}]}
    fake_file.write_text(json.dumps(data), encoding="utf-8")

    m = _m("src/foo.py", 75)
    enrich_with_history([m], tmp_path)

    assert m.score_delta == 75 - 60
    assert len(m.sparkline) > 0


def test_enrich_missing_file_no_crash(tmp_path, monkeypatch):
    import deathbed.history as hist_mod

    fake_file = tmp_path / "history.json"
    key = str(tmp_path.resolve())
    data = {key: [{"timestamp": 0, "repo_score": 70, "files": {"other.py": 50}}]}
    fake_file.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(hist_mod, "_HISTORY_FILE", fake_file)

    m = _m("src/foo.py", 75)  # file not in history
    enrich_with_history([m], tmp_path)  # should not crash
    assert m.score_delta is None


# ── get_repo_score_delta ──────────────────────────────────────────────────────

def test_get_repo_score_delta_no_history(tmp_path):
    assert get_repo_score_delta(tmp_path, 75) is None


def test_get_repo_score_delta_with_history(tmp_path, monkeypatch):
    import deathbed.history as hist_mod

    fake_file = tmp_path / "history.json"
    key = str(tmp_path.resolve())
    data = {key: [{"timestamp": 0, "repo_score": 60, "files": {}}]}
    fake_file.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(hist_mod, "_HISTORY_FILE", fake_file)

    delta = get_repo_score_delta(tmp_path, 70)
    assert delta == 10


def test_get_repo_score_delta_negative(tmp_path, monkeypatch):
    import deathbed.history as hist_mod

    fake_file = tmp_path / "history.json"
    key = str(tmp_path.resolve())
    data = {key: [{"timestamp": 0, "repo_score": 80, "files": {}}]}
    fake_file.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(hist_mod, "_HISTORY_FILE", fake_file)

    delta = get_repo_score_delta(tmp_path, 70)
    assert delta == -10
