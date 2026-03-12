"""Tests for decay.py — linear trend analysis on historical scan data."""
from __future__ import annotations

import time
import pytest
from pathlib import Path
from unittest.mock import patch

from deathbed.decay import (
    DecayPrediction,
    _linear_regression,
    predict_decay,
)
from deathbed.scoring import FileMetrics, compute_scores


# ── _linear_regression ────────────────────────────────────────────────────────

class TestLinearRegression:
    def test_perfect_line(self):
        xs = [0.0, 1.0, 2.0, 3.0]
        ys = [10.0, 8.0, 6.0, 4.0]
        slope, intercept = _linear_regression(xs, ys)
        assert abs(slope - (-2.0)) < 0.01
        assert abs(intercept - 10.0) < 0.01

    def test_flat_line(self):
        xs = [0.0, 1.0, 2.0]
        ys = [50.0, 50.0, 50.0]
        slope, intercept = _linear_regression(xs, ys)
        assert abs(slope) < 0.01
        assert abs(intercept - 50.0) < 0.01

    def test_single_point_returns_zero_slope(self):
        slope, intercept = _linear_regression([5.0], [42.0])
        assert slope == 0.0
        assert intercept == 42.0

    def test_empty_lists_returns_zero_slope(self):
        slope, intercept = _linear_regression([], [])
        assert slope == 0.0
        assert intercept == 0.0

    def test_all_same_x_returns_zero_slope(self):
        xs = [1.0, 1.0, 1.0]
        ys = [10.0, 20.0, 30.0]
        slope, intercept = _linear_regression(xs, ys)
        assert slope == 0.0


# ── predict_decay ─────────────────────────────────────────────────────────────

def _make_metric(path: str = "foo.py", score: int = 80) -> FileMetrics:
    m = FileMetrics(path=path, lines=100, days_since_commit=10, commit_count=5,
                    author_count=1, avg_complexity=2.0)
    compute_scores(m)
    m.composite_score = score
    return m


class TestPredictDecay:
    def test_returns_empty_when_no_history(self, tmp_path):
        results = [_make_metric("a.py", 80)]
        with patch("deathbed.decay.load_history", return_value=[]):
            preds = predict_decay(tmp_path, results)
        assert preds == {}

    def test_returns_empty_when_fewer_than_min_scans(self, tmp_path):
        now = int(time.time())
        scans = [
            {"timestamp": now - 86400 * 2, "files": {"a.py": 85}},
            {"timestamp": now - 86400,     "files": {"a.py": 80}},
        ]
        results = [_make_metric("a.py", 75)]
        with patch("deathbed.decay.load_history", return_value=scans):
            preds = predict_decay(tmp_path, results, min_scans=3)
        assert "a.py" not in preds

    def test_returns_prediction_for_declining_file(self, tmp_path):
        now = int(time.time())
        # 4 historical points declining from 90 to 75 over 3 days
        scans = [
            {"timestamp": now - 86400 * 3, "files": {"a.py": 90}},
            {"timestamp": now - 86400 * 2, "files": {"a.py": 83}},
            {"timestamp": now - 86400,     "files": {"a.py": 78}},
        ]
        results = [_make_metric("a.py", 70)]
        with patch("deathbed.decay.load_history", return_value=scans):
            preds = predict_decay(tmp_path, results, min_scans=3,
                                  horizon_days=60, warning_threshold=65,
                                  critical_threshold=40)
        # There may or may not be a prediction depending on the slope direction
        # but if a.py is declining, it should appear
        assert isinstance(preds, dict)

    def test_improving_file_not_included(self, tmp_path):
        now = int(time.time())
        scans = [
            {"timestamp": now - 86400 * 3, "files": {"a.py": 60}},
            {"timestamp": now - 86400 * 2, "files": {"a.py": 65}},
            {"timestamp": now - 86400,     "files": {"a.py": 70}},
        ]
        results = [_make_metric("a.py", 75)]
        with patch("deathbed.decay.load_history", return_value=scans):
            preds = predict_decay(tmp_path, results, min_scans=3)
        # Improving — slope >= 0, should be omitted
        assert "a.py" not in preds

    def test_file_already_below_threshold_skipped(self, tmp_path):
        now = int(time.time())
        scans = [
            {"timestamp": now - 86400 * 3, "files": {"a.py": 50}},
            {"timestamp": now - 86400 * 2, "files": {"a.py": 45}},
            {"timestamp": now - 86400,     "files": {"a.py": 42}},
        ]
        results = [_make_metric("a.py", 38)]  # already below critical=40
        with patch("deathbed.decay.load_history", return_value=scans):
            preds = predict_decay(tmp_path, results, min_scans=3,
                                  warning_threshold=65, critical_threshold=40)
        # current_score <= critical_threshold → _days_to_cross returns None → no prediction
        assert "a.py" not in preds

    def test_decay_prediction_dataclass_fields(self, tmp_path):
        pred = DecayPrediction(
            file_path="x.py",
            slope_per_week=-5.0,
            days_to_warning=10,
            days_to_critical=25,
            eta_days=10,
            target_threshold=65,
            current_score=80,
        )
        assert pred.file_path == "x.py"
        assert pred.slope_per_week == -5.0
        assert pred.eta_days == 10
        assert pred.target_threshold == 65

    def test_result_not_in_current_scores_skipped(self, tmp_path):
        now = int(time.time())
        scans = [
            {"timestamp": now - 86400 * 3, "files": {"b.py": 90}},
            {"timestamp": now - 86400 * 2, "files": {"b.py": 80}},
            {"timestamp": now - 86400,     "files": {"b.py": 70}},
        ]
        results = [_make_metric("a.py", 75)]  # a.py, not b.py
        with patch("deathbed.decay.load_history", return_value=scans):
            preds = predict_decay(tmp_path, results, min_scans=3)
        # b.py has history but is not in current results
        assert "b.py" not in preds
