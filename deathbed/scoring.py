"""Score calculation and diagnosis generation for each file."""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["FileMetrics", "compute_scores", "compute_repo_score", "letter_grade", "WEIGHTS"]


@dataclass
class FileMetrics:
    # ── Identity ──
    path: str

    # ── Raw metrics (inputs) ──
    lines: int = 0
    days_since_commit: int = 0
    commit_count: int = 0
    author_count: int = 0
    avg_complexity: float | None = None
    has_test_file: bool = False
    test_file_recent: bool = False
    test_has_assertions: bool = True
    recent_churn: int = 0
    prev_churn: int = 0
    dead_code_count: int = 0
    has_security_smell: bool = False
    security_smells: list[str] = field(default_factory=list)
    clone_similarity: float = 0.0
    clone_of: str = ""
    coupling_count: int = 0
    importers: list[str] = field(default_factory=list)

    # ── Individual scores (0–100, higher = healthier) ──
    size_score: int = 100
    age_score: int = 100
    churn_score: int = 100
    complexity_score: int = 100
    author_score: int = 100
    test_score: int = 100
    recent_churn_score: int = 100
    dead_code_score: int = 100
    coupling_score: int = 100

    # ── Derived / display ──
    heating_up: bool = False
    churn_trend: str = "stable"
    composite_score: int = 100
    diagnosis: str = "healthy"
    status: str = "HEALTHY"

    # ── Blame & history (optional, populated by flags) ──
    last_author: str = ""
    last_commit_msg: str = ""
    score_delta: int | None = None
    sparkline: str = ""


# ── Weights (v2.0.0 — coupling at 10%, others reduced proportionally) ─────────

WEIGHTS: dict[str, float] = {
    "size":         0.117,
    "age":          0.117,
    "churn":        0.081,
    "complexity":   0.162,
    "authors":      0.108,
    "test":         0.081,
    "recent_churn": 0.144,
    "dead_code":    0.090,
    "coupling":     0.100,
}
# weights sum ≈ 1.00  (117+117+81+162+108+81+144+90+100 = 1000)


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


def _complexity_score(avg: float | None) -> int:
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


def _test_score(has_test: bool, test_recent: bool, test_has_assertions: bool = True) -> int:
    if not has_test:
        return 20
    if not test_has_assertions:
        return 10  # test theatre: test file exists but has zero assertions
    if test_recent:
        return 100
    return 70


def _dead_code_score(count: int, is_supported: bool) -> int:
    """Score based on number of high-confidence unused code items from vulture/dead-code detection."""
    if not is_supported:
        return 75   # neutral for unsupported files
    if count == 0:
        return 100
    if count <= 3:
        return 85
    if count <= 8:
        return 60
    if count <= 15:
        return 35
    return max(0, 20 - (count - 15) // 2)


def _coupling_score(count: int) -> int:
    """Score based on how many other files depend on (import) this file."""
    if count <= 3:
        return 100
    if count <= 6:
        return 80
    if count <= 10:
        return 60
    if count <= 15:
        return 40
    if count <= 20:
        return 20
    return max(0, 10 - (count - 20) // 5)


# ── Diagnosis ─────────────────────────────────────────────────────────────────

def _diagnose(m: FileMetrics) -> str:
    scores = {
        "size":       m.size_score,
        "age":        m.age_score,
        "churn":      m.churn_score,
        "complexity": m.complexity_score,
        "authors":    m.author_score,
        "test":       m.test_score,
    }
    worst = min(scores, key=scores.get)  # type: ignore[arg-type]
    suffix = " 🔥 heating up" if m.heating_up else ""

    # 1. Security smell — always surfaced first (safety concern)
    if m.has_security_smell:
        return "security smell" + suffix

    # 2. God file — highly coupled + complex + large
    if (
        m.coupling_count >= 5
        and m.complexity_score < 45
        and m.size_score < 45
    ):
        return "god file" + suffix

    # 3. Clone risk
    if m.clone_similarity >= 0.4:
        return "clone risk" + suffix

    # 4. Test theatre — test file exists but has zero assertions
    if m.has_test_file and not m.test_has_assertions:
        return "test theatre" + suffix

    # 5. Dead code cemetery
    if m.dead_code_score < 40:
        return "dead code cemetery" + suffix

    # 6. Haunted — 5+ authors, still complex, still churning
    if (
        m.author_count >= 5
        and m.avg_complexity is not None
        and m.avg_complexity > 10
        and (m.churn_trend == "up" or m.recent_churn > 10)
    ):
        return "haunted" + suffix

    # 7. Ownership void: abandoned by a single author
    if m.days_since_commit >= 180 and m.author_count <= 1 and m.commit_count > 0 and m.age_score < 45:
        return "ownership void" + suffix

    if m.composite_score >= 86:
        return "healthy"

    if scores["age"] < 35 and scores["complexity"] < 45:
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
            "churn":      "churn monster",
            "complexity": "complexity graveyard",
            "age":        "legacy ghost",
            "authors":    "too many cooks",
            "size":       "growing out of control",
            "test":       "nobody's watching this",
        }
        base = mapping.get(worst, "needs attention")

    return base + suffix


def letter_grade(score: int) -> str:
    """Convert a 0-100 health score to a letter grade."""
    if score >= 86:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def compute_repo_score(results: list[FileMetrics]) -> int:
    """Weighted average of all file scores, weighted by line count."""
    if not results:
        return 100
    total_weight = sum(max(m.lines, 1) for m in results)
    weighted_sum = sum(m.composite_score * max(m.lines, 1) for m in results)
    return int(weighted_sum / total_weight)


def _status(score: int) -> str:
    if score <= 40:
        return "CRITICAL"
    if score <= 65:
        return "WARNING"
    if score <= 85:
        return "FAIR"
    return "HEALTHY"


# ── Public API ────────────────────────────────────────────────────────────────

def compute_scores(m: FileMetrics) -> None:
    """Fill in all score fields and composite, in-place."""
    from pathlib import Path as _Path
    _suffix = _Path(m.path).suffix.lower()
    is_supported = _suffix in (".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs")

    m.size_score         = _size_score(m.lines)
    m.age_score          = _age_score(m.days_since_commit)
    m.churn_score        = _churn_score(m.commit_count)
    m.complexity_score   = _complexity_score(m.avg_complexity)
    m.author_score       = _author_score(m.author_count)
    m.test_score         = _test_score(m.has_test_file, m.test_file_recent,
                                       m.test_has_assertions)
    m.recent_churn_score = _recent_churn_score(m.recent_churn)
    m.dead_code_score    = _dead_code_score(m.dead_code_count, is_supported)
    m.coupling_score     = _coupling_score(m.coupling_count)

    # Heating up: recent activity is 2× or more than the prior 90-day window
    m.heating_up = (
        m.recent_churn > 5
        and m.prev_churn > 0
        and m.recent_churn >= m.prev_churn * 2
    )

    # Churn trend
    if m.recent_churn > 3 and m.prev_churn > 0:
        if m.recent_churn >= m.prev_churn * 1.5:
            m.churn_trend = "up"
        elif m.prev_churn >= m.recent_churn * 1.5:
            m.churn_trend = "down"
        else:
            m.churn_trend = "stable"
    elif m.recent_churn > 3 and m.prev_churn == 0:
        m.churn_trend = "up"
    elif m.recent_churn == 0 and m.prev_churn > 3:
        m.churn_trend = "down"
    else:
        m.churn_trend = "stable"

    m.composite_score = int(
        m.size_score          * WEIGHTS["size"]
        + m.age_score         * WEIGHTS["age"]
        + m.churn_score       * WEIGHTS["churn"]
        + m.complexity_score  * WEIGHTS["complexity"]
        + m.author_score      * WEIGHTS["authors"]
        + m.test_score        * WEIGHTS["test"]
        + m.recent_churn_score * WEIGHTS["recent_churn"]
        + m.dead_code_score   * WEIGHTS["dead_code"]
        + m.coupling_score    * WEIGHTS["coupling"]
    )

    m.status    = _status(m.composite_score)
    m.diagnosis = _diagnose(m)
