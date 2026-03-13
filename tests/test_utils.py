"""Tests for utils.py — human_days and score_severity."""

from __future__ import annotations

import pytest

from deathbed.utils import human_days, score_severity

# ── human_days ────────────────────────────────────────────────────────────────

def test_human_days_today():
    assert human_days(0) == "today"


def test_human_days_yesterday():
    assert human_days(1) == "yesterday"


def test_human_days_six():
    assert human_days(6) == "6d ago"


def test_human_days_two_weeks():
    assert human_days(14) == "2w ago"


def test_human_days_two_months():
    assert human_days(60) == "2mo ago"


def test_human_days_one_year_one_month():
    assert human_days(400) == "1y 1mo ago"


def test_human_days_two_years():
    assert human_days(730) == "2y ago"


@pytest.mark.parametrize("days,expected", [
    (0,   "today"),
    (1,   "yesterday"),
    (6,   "6d ago"),
    (7,   "1w ago"),
    (29,  "4w ago"),
    (30,  "1mo ago"),
    (364, "12mo ago"),
    (365, "1y ago"),
    (366, "1y ago"),
    (730, "2y ago"),
    (731, "2y ago"),
    (760, "2y 1mo ago"),
])
def test_human_days_parametrized(days, expected):
    assert human_days(days) == expected


# ── score_severity ────────────────────────────────────────────────────────────

def test_score_severity_healthy_100():
    assert score_severity(100) == "healthy"


def test_score_severity_healthy_86():
    assert score_severity(86) == "healthy"


def test_score_severity_fair_85():
    assert score_severity(85) == "fair"


def test_score_severity_warning_65():
    assert score_severity(65) == "warning"


def test_score_severity_critical_40():
    assert score_severity(40) == "critical"


def test_score_severity_critical_0():
    assert score_severity(0) == "critical"


@pytest.mark.parametrize("score,expected", [
    (100, "healthy"),
    (86,  "healthy"),
    (85,  "fair"),
    (66,  "fair"),
    (65,  "warning"),
    (41,  "warning"),
    (40,  "critical"),
    (0,   "critical"),
])
def test_score_severity_parametrized(score, expected):
    assert score_severity(score) == expected
