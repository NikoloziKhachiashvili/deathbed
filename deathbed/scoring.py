"""Score calculation and diagnosis generation for each file."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FileMetrics:
    path: str
    lines: int = 0
    days_since_commit: int = 0
    commit_count: int = 0
    author_count: int = 0
    avg_complexity: Optional[float] = None
    has_test_file: bool = False
    test_file_recent: bool = False
    recent_churn: int = 0   # commits in last 90 days
    prev_churn: int = 0     # commits in prior 90 days (days 91-180)

    # Individual scores (0–100, higher = healthier)
    size_score: int = 100
    age_score: int = 100
    churn_score: int = 100
    complexity_score: int = 100
    author_score: int = 100
    test_score: int = 100
    recent_churn_score: int = 100

    # Derived flag
    heating_up: bool = False

    # Composite
    composite_score: int = 100
    diagnosis: str = "healthy"
    status: str = "HEALTHY"


# ── Weights ───────────────────────────────────────────────────────────────────

WEIGHTS: dict[str, float] = {
    "size": 0.15,
    "age": 0.15,          # reduced from 0.20; recent_churn captures recent signal better
    "churn": 0.10,        # reduced from 0.20; recent_churn subsumes part of this signal
    "complexity": 0.20,
    "authors": 0.15,
    "test": 0.10,
    "recent_churn": 0.15,
}
# weights sum = 1.00


# ── Individual scoring functions ───────────────────────────────────────────────

def _size_score(lines: int) -> int:
    if lines <= 150:
        return 100
    if lines <= 300:
        return 85
    if lines <= 600:
        return 60
    if lines <= 1000:
        return 35
    return max(0, 30 - (lines - 1000) // 100)


def _age_score(days: int) -> int:
    if days <= 30:
        return 100
    if days <= 90:
        return 85
    if days <= 180:
        return 68
    if days <= 365:
        return 45
    if days <= 730:
        return 22
    return max(0, 15 - (days - 730) // 180)


def _churn_score(commits: int) -> int:
    if commits <= 5:
        return 100
    if commits <= 20:
        return 80
    if commits <= 50:
        return 55
    if commits <= 100:
        return 30
    return max(0, 20 - (commits - 100) // 20)


def _recent_churn_score(recent: int) -> int:
    """Score based on commits to the file in the last 90 days."""
    if recent <= 5:
        return 100
    if recent <= 15:
        return 70   # yellow zone
    if recent <= 30:
        return 40   # orange zone
    return max(0, 20 - (recent - 30))  # red zone


def _complexity_score(avg: Optional[float]) -> int:
    if avg is None:
        return 75  # neutral / non-Python file
    if avg <= 2:
        return 100
    if avg <= 5:
        return 80
    if avg <= 10:
        return 55
    if avg <= 15:
        return 30
    return max(0, 20 - int(avg - 15) * 2)


def _author_score(authors: int) -> int:
    if authors <= 1:
        return 100
    if authors <= 3:
        return 80
    if authors <= 6:
        return 55
    if authors <= 10:
        return 30
    return max(0, 20 - (authors - 10) * 2)


def _test_score(has_test: bool, test_recent: bool) -> int:
    if not has_test:
        return 20
    if test_recent:
        return 100
    return 70


# ── Diagnosis ─────────────────────────────────────────────────────────────────

def _diagnose(m: FileMetrics) -> str:
    scores = {
        "size": m.size_score,
        "age": m.age_score,
        "churn": m.churn_score,
        "complexity": m.complexity_score,
        "authors": m.author_score,
        "test": m.test_score,
    }
    worst = min(scores, key=scores.get)  # type: ignore[arg-type]

    if m.composite_score >= 86:
        base = "healthy"
    elif scores["age"] < 35 and scores["complexity"] < 45:
        base = "abandoned and complex"
    elif scores["age"] < 35 and scores["test"] < 35:
        base = "nobody's watching this"
    elif scores["churn"] < 35 and scores["complexity"] < 50:
        base = "churn monster"
    elif scores["size"] < 40 and scores["churn"] < 55:
        base = "growing out of control"
    elif scores["authors"] < 35:
        base = "too many cooks"
    elif scores["complexity"] < 25:
        base = "complexity graveyard"
    elif scores["age"] < 15:
        base = "legacy ghost"
    else:
        mapping = {
            "churn": "churn monster",
            "complexity": "complexity graveyard",
            "age": "legacy ghost",
            "authors": "too many cooks",
            "size": "growing out of control",
            "test": "nobody's watching this",
        }
        base = mapping.get(worst, "needs attention")

    if m.heating_up:
        return base + " 🔥 heating up"
    return base


def _status(score: int) -> str:
    if score <= 40:
        return "CRITICAL"
    if score <= 65:
        return "WARNING"
    if score <= 85:
        return "FAIR"
    return "HEALTHY"


# ── Public API ────────────────────────────────────────────────────────────────

def compute_scores(m: FileMetrics) -> FileMetrics:
    """Fill in all score fields and composite, in-place."""
    m.size_score = _size_score(m.lines)
    m.age_score = _age_score(m.days_since_commit)
    m.churn_score = _churn_score(m.commit_count)
    m.complexity_score = _complexity_score(m.avg_complexity)
    m.author_score = _author_score(m.author_count)
    m.test_score = _test_score(m.has_test_file, m.test_file_recent)
    m.recent_churn_score = _recent_churn_score(m.recent_churn)

    # Heating up: recent activity is 2× or more than the prior 90-day window
    m.heating_up = (
        m.recent_churn > 5
        and m.prev_churn > 0
        and m.recent_churn >= m.prev_churn * 2
    )

    m.composite_score = int(
        m.size_score * WEIGHTS["size"]
        + m.age_score * WEIGHTS["age"]
        + m.churn_score * WEIGHTS["churn"]
        + m.complexity_score * WEIGHTS["complexity"]
        + m.author_score * WEIGHTS["authors"]
        + m.test_score * WEIGHTS["test"]
        + m.recent_churn_score * WEIGHTS["recent_churn"]
    )

    m.status = _status(m.composite_score)
    m.diagnosis = _diagnose(m)
    return m
