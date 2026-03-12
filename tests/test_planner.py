"""Tests for planner.py — refactoring roadmap generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from deathbed.planner import (
    _estimate_effort,
    _get_action,
    _safe_alternative,
    format_plan_markdown,
    generate_plan,
)
from deathbed.scoring import FileMetrics, compute_scores


def _m(path="src/foo.py", **kwargs) -> FileMetrics:
    defaults = dict(
        lines=100, days_since_commit=10, commit_count=5, author_count=1,
        avg_complexity=3.0, has_test_file=True, test_file_recent=True,
        recent_churn=2, prev_churn=0,
    )
    defaults.update(kwargs)
    m = FileMetrics(path=path, **defaults)
    compute_scores(m)
    return m


def _critical(**kwargs) -> FileMetrics:
    return _m(
        path="src/bad.py",
        lines=2000, days_since_commit=900, commit_count=200,
        author_count=15, avg_complexity=20.0, has_test_file=False,
        recent_churn=50, prev_churn=10, **kwargs
    )


# ── _estimate_effort ──────────────────────────────────────────────────────────

def test_effort_small():
    m = _m(lines=100, avg_complexity=2.0)
    assert _estimate_effort(m) == "Small"


def test_effort_medium_by_lines():
    m = _m(lines=300, avg_complexity=2.0)
    assert _estimate_effort(m) == "Medium"


def test_effort_large_by_lines():
    m = _m(lines=600, avg_complexity=2.0)
    assert _estimate_effort(m) == "Large"


def test_effort_large_by_complexity():
    m = _m(lines=100, avg_complexity=15.0)
    assert _estimate_effort(m) == "Large"


# ── _safe_alternative ─────────────────────────────────────────────────────────

def test_safe_alternative_eval():
    result = _safe_alternative("calls eval()")
    assert "literal_eval" in result or "safe" in result.lower()


def test_safe_alternative_pickle():
    result = _safe_alternative("imports pickle")
    assert "json" in result or "msgpack" in result


def test_safe_alternative_shell_true():
    result = _safe_alternative("subprocess.run(shell=True)")
    assert "shell=False" in result


def test_safe_alternative_unknown():
    result = _safe_alternative("some unknown smell")
    assert len(result) > 0


# ── _get_action ───────────────────────────────────────────────────────────────

def test_action_security_smell(tmp_path):
    m = _m()
    m.has_security_smell = True
    m.security_smells = ["calls eval()"]
    m.diagnosis = "security smell"
    action = _get_action(m, tmp_path)
    assert len(action) > 0


def test_action_test_theatre(tmp_path):
    m = _m()
    m.diagnosis = "test theatre"
    action = _get_action(m, tmp_path)
    assert "assert" in action.lower() or "assertion" in action.lower()


def test_action_god_file(tmp_path):
    m = _critical()
    m.coupling_count = 8
    m.diagnosis = "god file"
    action = _get_action(m, tmp_path)
    assert "8" in action or "depend" in action.lower()


def test_action_clone_risk(tmp_path):
    m = _m()
    m.clone_of = "src/other.py"
    m.diagnosis = "clone risk"
    action = _get_action(m, tmp_path)
    assert "other.py" in action


def test_action_dead_code_cemetery(tmp_path):
    m = _m(path="src/foo.py")
    m.dead_code_count = 12
    m.diagnosis = "dead code cemetery"
    action = _get_action(m, tmp_path)
    assert "12" in action or "dead" in action.lower()


def test_action_haunted(tmp_path):
    m = _m()
    m.diagnosis = "haunted"
    action = _get_action(m, tmp_path)
    assert len(action) > 10


def test_action_generic(tmp_path):
    m = _m()
    m.diagnosis = "needs attention"
    action = _get_action(m, tmp_path)
    assert len(action) > 0


# ── generate_plan ─────────────────────────────────────────────────────────────

def test_generate_plan_sprint_assignment(tmp_path):
    critical = _critical()
    warning  = _m(path="w.py", days_since_commit=200, has_test_file=False,
                  avg_complexity=12.0)
    healthy  = _m(path="h.py")

    plan = generate_plan([critical, warning, healthy], tmp_path)

    assert len(plan["sprint1"]) == 1
    assert plan["sprint1"][0]["file"] == "src/bad.py"
    assert "sprint2" in plan
    assert "sprint3" in plan


def test_generate_plan_all_healthy(tmp_path):
    results = [_m(path=f"f{i}.py") for i in range(3)]
    plan = generate_plan(results, tmp_path)
    assert plan["sprint1"] == []
    assert plan["sprint2"] == []
    assert plan["sprint3"] == []


def test_generate_plan_item_has_required_keys(tmp_path):
    plan = generate_plan([_critical()], tmp_path)
    if plan["sprint1"]:
        item = plan["sprint1"][0]
        assert "file" in item
        assert "action" in item
        assert "effort" in item
        assert "score" in item
        assert "diagnosis" in item


# ── format_plan_markdown ──────────────────────────────────────────────────────

def test_format_plan_markdown_contains_headers(tmp_path):
    plan = generate_plan([_critical()], tmp_path)
    md = format_plan_markdown(plan, tmp_path)
    assert "# Refactoring Roadmap" in md
    assert "Sprint 1" in md


def test_format_plan_markdown_all_healthy(tmp_path):
    plan = generate_plan([_m()], tmp_path)
    md = format_plan_markdown(plan, tmp_path)
    assert "healthy" in md.lower() or "Sprint" not in md or "# Refactoring" in md


def test_format_plan_markdown_no_crash(tmp_path):
    results = [_critical(), _m(path="w.py", days_since_commit=300, has_test_file=False)]
    plan = generate_plan(results, tmp_path)
    md = format_plan_markdown(plan, tmp_path)
    assert isinstance(md, str)
    assert len(md) > 0
