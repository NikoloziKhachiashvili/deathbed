"""Decay prediction: linear trend analysis on historical scan data."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .history import load_history


@dataclass
class DecayPrediction:
    file_path: str
    slope_per_week: float           # points per week (negative = declining)
    days_to_warning: Optional[int]  # days until score crosses warning_threshold
    days_to_critical: Optional[int] # days until score crosses critical_threshold
    eta_days: Optional[int]         # min(days_to_warning, days_to_critical)
    target_threshold: Optional[int] # threshold it will cross first
    current_score: int


def _linear_regression(xs: list, ys: list) -> tuple:
    """Return (slope, intercept) of the least-squares line."""
    n = len(xs)
    if n < 2:
        return 0.0, (ys[0] if ys else 0.0)
    sum_x  = sum(xs)
    sum_y  = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_xx = sum(x * x for x in xs)
    denom  = n * sum_xx - sum_x ** 2
    if denom == 0.0:
        return 0.0, sum_y / n
    slope     = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


def predict_decay(
    repo_root: Path,
    results: list,
    *,
    min_scans: int = 3,
    horizon_days: int = 30,
    warning_threshold: int = 65,
    critical_threshold: int = 40,
) -> dict:
    """
    For each file with >=min_scans historical data points, fit a linear
    trend and extrapolate to find when score will cross a threshold.
    Returns dict: file_path -> DecayPrediction. Improving files are omitted.
    """
    scans = load_history(repo_root)
    if not scans:
        return {}

    file_history: dict = {}
    for scan in scans:
        ts = scan.get("timestamp", 0)
        for path, score in scan.get("files", {}).items():
            file_history.setdefault(path, []).append((ts, score))

    current_scores: dict = {m.path: m.composite_score for m in results}
    now = int(time.time())
    predictions: dict = {}

    for file_path, history in file_history.items():
        if len(history) < min_scans:
            continue
        current_score = current_scores.get(file_path)
        if current_score is None:
            continue

        history_sorted = sorted(history, key=lambda x: x[0])
        t0 = history_sorted[0][0]
        xs = [(ts - t0) / 86400.0 for ts, _ in history_sorted]
        ys = [float(s) for _, s in history_sorted]
        xs.append((now - t0) / 86400.0)
        ys.append(float(current_score))

        if len(xs) < min_scans:
            continue

        slope, intercept = _linear_regression(xs, ys)
        slope_per_week = slope * 7.0

        if slope >= 0.0:
            continue  # improving or flat

        now_x = (now - t0) / 86400.0

        def _days_to_cross(threshold: int) -> Optional[int]:
            if current_score <= threshold:
                return None
            d = (threshold - intercept - slope * now_x) / slope
            if d <= 0:
                return None
            days = int(d)
            return days if days <= horizon_days else None

        d_warn = _days_to_cross(warning_threshold)
        d_crit = _days_to_cross(critical_threshold)

        if d_warn is None and d_crit is None:
            continue

        candidates = []
        if d_warn is not None:
            candidates.append((d_warn, warning_threshold))
        if d_crit is not None:
            candidates.append((d_crit, critical_threshold))

        eta_days, target = min(candidates, key=lambda x: x[0])

        predictions[file_path] = DecayPrediction(
            file_path=file_path,
            slope_per_week=slope_per_week,
            days_to_warning=d_warn,
            days_to_critical=d_crit,
            eta_days=eta_days,
            target_threshold=target,
            current_score=current_score,
        )

    return predictions
