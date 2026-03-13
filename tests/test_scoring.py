"""Tests for scoring.py — comprehensive coverage of all score functions."""

from __future__ import annotations

import pytest

from deathbed.scoring import (
    WEIGHTS,
    FileMetrics,
    _age_score,
    _author_score,
    _churn_score,
    _complexity_score,
    _coupling_score,
    _dead_code_score,
    _diagnose,
    _recent_churn_score,
    _size_score,
    _status,
    _test_score,
    compute_repo_score,
    compute_scores,
    letter_grade,
)

# ── Weights sanity ─────────────────────────────────────────────────────────────

def test_weights_sum_to_one():
    # Use 1e-6 tolerance — new 9-weight set uses 3-decimal values that may
    # accumulate small float rounding errors, but sum to 1000/1000 = 1.0 exactly.
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-6


# ── Size score ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("lines,expected", [
    (0,    100),
    (150,  100),
    (151,  85),
    (300,  85),
    (301,  60),
    (600,  60),
    (601,  35),
    (1000, 35),
    (1001, max(0, 30 - 1 // 100)),
    (2000, max(0, 30 - 1000 // 100)),
])
def test_size_score(lines, expected):
    assert _size_score(lines) == expected


# ── Age score ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("days,expected", [
    (0,   100),
    (30,  100),
    (31,  85),
    (90,  85),
    (91,  68),
    (180, 68),
    (181, 45),
    (365, 45),
    (366, 22),
    (730, 22),
    (731, max(0, 15 - 1 // 180)),
])
def test_age_score(days, expected):
    assert _age_score(days) == expected


# ── Churn score ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("commits,expected", [
    (0,   100),
    (5,   100),
    (6,   80),
    (20,  80),
    (21,  55),
    (50,  55),
    (51,  30),
    (100, 30),
    (101, max(0, 20 - 1 // 20)),
])
def test_churn_score(commits, expected):
    assert _churn_score(commits) == expected


# ── Recent churn score ────────────────────────────────────────────────────────

@pytest.mark.parametrize("recent,expected", [
    (0,  100),
    (5,  100),
    (6,  70),
    (15, 70),
    (16, 40),
    (30, 40),
    (31, max(0, 20 - (31 - 30))),
    (50, max(0, 20 - (50 - 30))),
])
def test_recent_churn_score(recent, expected):
    assert _recent_churn_score(recent) == expected


# ── Complexity score ──────────────────────────────────────────────────────────

def test_complexity_score_none():
    assert _complexity_score(None) == 75

@pytest.mark.parametrize("avg,expected", [
    (1.0,  100),
    (2.0,  100),
    (2.1,  80),
    (5.0,  80),
    (5.1,  55),
    (10.0, 55),
    (10.1, 30),
    (15.0, 30),
    (15.1, max(0, 20 - int(0.1) * 2)),
])
def test_complexity_score_values(avg, expected):
    assert _complexity_score(avg) == expected


# ── Author score ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("authors,expected", [
    (1,  100),
    (2,  80),
    (3,  80),
    (4,  55),
    (6,  55),
    (7,  30),
    (10, 30),
    (11, max(0, 20 - 2)),
])
def test_author_score(authors, expected):
    assert _author_score(authors) == expected


# ── Test score ────────────────────────────────────────────────────────────────

def test_test_score_no_test():
    assert _test_score(False, False) == 20

def test_test_score_old_test():
    assert _test_score(True, False) == 70

def test_test_score_recent_test():
    assert _test_score(True, True) == 100


# ── Dead code score ───────────────────────────────────────────────────────────

def test_dead_code_score_non_supported():
    # is_supported=False → neutral score of 75 (unsupported file types)
    assert _dead_code_score(0, is_supported=False) == 75
    assert _dead_code_score(10, is_supported=False) == 75

def test_dead_code_score_zero():
    assert _dead_code_score(0, is_supported=True) == 100

@pytest.mark.parametrize("count,expected", [
    (1,  85),
    (3,  85),
    (4,  60),
    (8,  60),
    (9,  35),
    (15, 35),
    (16, max(0, 20 - (16 - 15) // 2)),
])
def test_dead_code_score_supported(count, expected):
    assert _dead_code_score(count, is_supported=True) == expected


# ── Status ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("score,expected", [
    (0,   "CRITICAL"),
    (40,  "CRITICAL"),
    (41,  "WARNING"),
    (65,  "WARNING"),
    (66,  "FAIR"),
    (85,  "FAIR"),
    (86,  "HEALTHY"),
    (100, "HEALTHY"),
])
def test_status(score, expected):
    assert _status(score) == expected


# ── compute_scores ────────────────────────────────────────────────────────────

def _make(path="foo.py", **kwargs) -> FileMetrics:
    defaults = dict(
        lines=100, days_since_commit=10, commit_count=3, author_count=1,
        avg_complexity=2.0, has_test_file=True, test_file_recent=True,
        recent_churn=2, prev_churn=1,
    )
    defaults.update(kwargs)
    return FileMetrics(path=path, **defaults)


def test_compute_scores_healthy():
    m = _make()
    compute_scores(m)
    assert m.status == "HEALTHY"
    assert m.composite_score >= 86
    assert m.diagnosis == "healthy"


def test_compute_scores_composite_range():
    m = _make(
        lines=2000, days_since_commit=1000, commit_count=200,
        avg_complexity=20.0, has_test_file=False, author_count=15,
        recent_churn=50, prev_churn=5,
    )
    compute_scores(m)
    assert 0 <= m.composite_score <= 100
    assert m.status == "CRITICAL"


def test_heating_up_flag():
    m = _make(recent_churn=20, prev_churn=8)
    compute_scores(m)
    assert m.heating_up is True


def test_no_heating_up_if_prev_zero():
    m = _make(recent_churn=10, prev_churn=0)
    compute_scores(m)
    assert m.heating_up is False


def test_churn_trend_up():
    m = _make(recent_churn=15, prev_churn=5)
    compute_scores(m)
    assert m.churn_trend == "up"


def test_churn_trend_down():
    # Both windows > 3, prev is 3x larger than recent → should be "down"
    m = _make(recent_churn=4, prev_churn=12)
    compute_scores(m)
    assert m.churn_trend == "down"


def test_churn_trend_stable():
    m = _make(recent_churn=4, prev_churn=5)
    compute_scores(m)
    assert m.churn_trend == "stable"


def test_churn_trend_stable_low_activity():
    m = _make(recent_churn=0, prev_churn=0)
    compute_scores(m)
    assert m.churn_trend == "stable"


# ── Diagnoses ─────────────────────────────────────────────────────────────────

def test_diagnosis_security_smell_overrides_all():
    m = _make()
    compute_scores(m)
    m.has_security_smell = True
    m.security_smells = ["calls eval()"]
    m.diagnosis = _diagnose(m)
    assert m.diagnosis == "security smell"


def test_diagnosis_security_smell_with_heating_up():
    m = _make(recent_churn=20, prev_churn=8)
    compute_scores(m)
    m.has_security_smell = True
    m.diagnosis = _diagnose(m)
    assert "security smell" in m.diagnosis
    assert "heating up" in m.diagnosis


def test_diagnosis_clone_risk():
    m = _make()
    compute_scores(m)
    # Force a non-healthy score so clone risk shows
    m.composite_score = 70
    m.status = "FAIR"
    m.clone_similarity = 0.75
    m.clone_of = "other.py"
    m.diagnosis = _diagnose(m)
    assert m.diagnosis.startswith("clone risk")


def test_diagnosis_dead_code_cemetery():
    m = _make()
    compute_scores(m)
    m.dead_code_score = 20
    m.dead_code_count = 20
    m.diagnosis = _diagnose(m)
    assert m.diagnosis.startswith("dead code cemetery")


def test_diagnosis_ownership_void():
    # days_since_commit=400 → age_score=22 (<45), single author, so ownership void triggers
    m = _make(days_since_commit=400, author_count=1, commit_count=5)
    compute_scores(m)
    assert m.diagnosis == "ownership void"


def test_diagnosis_healthy():
    m = _make()
    compute_scores(m)
    assert m.diagnosis == "healthy"


def test_diagnosis_heating_up_suffix():
    m = _make(recent_churn=20, prev_churn=8, days_since_commit=400,
              has_test_file=False, avg_complexity=20.0)
    compute_scores(m)
    assert "heating up" in m.diagnosis


def test_diagnosis_churn_monster():
    m = _make(commit_count=120, avg_complexity=12.0)
    compute_scores(m)
    assert m.composite_score < 86


def test_compute_scores_dead_code_non_python():
    # .js is now a supported language (is_supported=True), so dead_code is scored
    m = _make(path="foo.js", avg_complexity=None, dead_code_count=10)
    compute_scores(m)
    # .js is supported → dead_code_count=10 → score should be < 75
    assert m.dead_code_score < 75

def test_compute_scores_dead_code_unsupported_lang():
    # .css is not a supported language → neutral score of 75
    m = _make(path="foo.css", avg_complexity=None, dead_code_count=10)
    compute_scores(m)
    assert m.dead_code_score == 75  # neutral for unsupported file types


# ── letter_grade ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("score,expected", [
    (100, "A"), (86, "A"), (85, "B"), (70, "B"), (69, "C"),
    (55, "C"), (54, "D"), (40, "D"), (39, "F"), (0, "F"),
])
def test_letter_grade(score, expected):
    assert letter_grade(score) == expected


# ── compute_repo_score ────────────────────────────────────────────────────────

def test_compute_repo_score_empty():
    assert compute_repo_score([]) == 100


def test_compute_repo_score_single():
    m = _make(lines=100)
    compute_scores(m)
    assert compute_repo_score([m]) == m.composite_score


def test_compute_repo_score_weighted_by_lines():
    big   = _make(path="big.py",   lines=1000, days_since_commit=900, commit_count=200,
                  avg_complexity=20.0, has_test_file=False, author_count=15,
                  recent_churn=50, prev_churn=10)
    small = _make(path="small.py", lines=10)
    compute_scores(big)
    compute_scores(small)
    repo = compute_repo_score([big, small])
    # big file's bad score should dominate
    assert repo < small.composite_score


def test_compute_repo_score_range():
    files = [_make() for _ in range(5)]
    for f in files:
        compute_scores(f)
    score = compute_repo_score(files)
    assert 0 <= score <= 100


def test_compute_scores_dead_code_python():
    m = _make(path="foo.py", dead_code_count=10)
    compute_scores(m)
    assert m.dead_code_score == 35


# ── v2.0.0: coupling score ─────────────────────────────────────────────────────

@pytest.mark.parametrize("count,expected", [
    (0,  100),
    (3,  100),
    (4,  80),
    (6,  80),
    (7,  60),
    (10, 60),
    (11, 40),
    (15, 40),
    (16, 20),
    (20, 20),
    (21, max(0, 10 - 1 // 5)),
])
def test_coupling_score(count, expected):
    assert _coupling_score(count) == expected


# ── v2.0.0: test_score with assertions ────────────────────────────────────────

def test_test_score_no_assertions():
    """Test file exists but has zero assertions → test theatre → score 10."""
    assert _test_score(True, True, test_has_assertions=False) == 10

def test_test_score_with_assertions_recent():
    assert _test_score(True, True, test_has_assertions=True) == 100

def test_test_score_with_assertions_old():
    assert _test_score(True, False, test_has_assertions=True) == 70


# ── v2.0.0: new diagnoses ─────────────────────────────────────────────────────

def test_diagnosis_test_theatre():
    m = _make(has_test_file=True, test_file_recent=True)
    compute_scores(m)
    m.test_has_assertions = False
    m.test_score = _test_score(True, True, False)
    m.diagnosis = _diagnose(m)
    assert m.diagnosis == "test theatre"


def test_diagnosis_haunted():
    m = _make(author_count=6, avg_complexity=15.0, recent_churn=20, prev_churn=5)
    compute_scores(m)
    assert m.churn_trend == "up"
    assert m.diagnosis.startswith("haunted")


def test_diagnosis_god_file():
    m = _make(lines=800, avg_complexity=20.0)
    compute_scores(m)
    m.coupling_count = 10
    m.coupling_score = _coupling_score(10)
    m.diagnosis = _diagnose(m)
    assert m.diagnosis == "god file"


def test_diagnosis_god_file_requires_all_conditions():
    # coupling >= 5 but complexity fine → not god file
    m = _make(lines=100, avg_complexity=2.0)
    compute_scores(m)
    m.coupling_count = 10
    m.coupling_score = 60
    m.diagnosis = _diagnose(m)
    assert m.diagnosis != "god file"


def test_version_is_3():
    from deathbed import __version__
    assert __version__.startswith("3.")


# ── Boundary / property tests ──────────────────────────────────────────────────

@pytest.mark.parametrize("lines", [0, 1, 150, 300, 600, 1000, 2000, 5000])
def test_size_score_in_range(lines):
    assert 0 <= _size_score(lines) <= 100


@pytest.mark.parametrize("days", [0, 1, 30, 90, 180, 365, 730, 1500])
def test_age_score_in_range(days):
    assert 0 <= _age_score(days) <= 100


@pytest.mark.parametrize("commits", [0, 1, 5, 20, 50, 100, 200, 500])
def test_churn_score_in_range(commits):
    assert 0 <= _churn_score(commits) <= 100


@pytest.mark.parametrize("recent", [0, 1, 5, 15, 30, 50, 100])
def test_recent_churn_score_in_range(recent):
    assert 0 <= _recent_churn_score(recent) <= 100


@pytest.mark.parametrize("avg", [None, 0.0, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 50.0])
def test_complexity_score_in_range(avg):
    assert 0 <= _complexity_score(avg) <= 100


@pytest.mark.parametrize("authors", [0, 1, 3, 6, 10, 15, 30])
def test_author_score_in_range(authors):
    assert 0 <= _author_score(authors) <= 100


@pytest.mark.parametrize("count", [0, 1, 3, 8, 15, 20, 50])
def test_dead_code_score_in_range(count):
    assert 0 <= _dead_code_score(count, is_supported=True) <= 100
    assert 0 <= _dead_code_score(count, is_supported=False) <= 100


@pytest.mark.parametrize("count", [0, 3, 6, 10, 15, 20, 30])
def test_coupling_score_in_range(count):
    assert 0 <= _coupling_score(count) <= 100


def test_compute_scores_status_valid():
    valid_statuses = {"CRITICAL", "WARNING", "FAIR", "HEALTHY"}
    m = _make()
    compute_scores(m)
    assert m.status in valid_statuses


def test_compute_scores_composite_in_range():
    m = _make(
        lines=2000, days_since_commit=1000, commit_count=200,
        avg_complexity=20.0, has_test_file=False, author_count=15,
        recent_churn=50, prev_churn=5,
    )
    compute_scores(m)
    assert 0 <= m.composite_score <= 100


def test_letter_grade_valid_values():
    valid_grades = {"A", "B", "C", "D", "F"}
    for score in range(0, 101):
        assert letter_grade(score) in valid_grades
