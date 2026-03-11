# Tests for display.py — verify render functions work without crashing.

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from deathbed.display import (
    _health_icon,
    _human_days,
    _score_bar,
    _score_color,
    _truncate,
    _row_style,
    render_diff,
    render_markdown,
    render_summary,
    render_table,
    render_header,
    render_error,
    render_footer,
    _render_most_wanted,
    _render_quick_wins,
    _render_tips,
    _render_security_alerts,
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


# ── Tiny pure helpers ──────────────────────────────────────────────────────────

def test_health_icon_critical():
    assert _health_icon("CRITICAL") == "💀"

def test_health_icon_warning():
    assert "⚠" in _health_icon("WARNING")

def test_health_icon_fair():
    assert _health_icon("FAIR") == "🌡 "

def test_health_icon_healthy():
    assert _health_icon("HEALTHY") == "✅"

def test_health_icon_unknown():
    assert _health_icon("???") == "·"


def test_score_color_green():
    assert _score_color(80) == "rgb(0,200,80)"

def test_score_color_amber():
    assert _score_color(65) == "rgb(255,191,0)"

def test_score_color_orange():
    assert _score_color(45) == "rgb(255,140,0)"

def test_score_color_red():
    assert _score_color(20) == "rgb(255,69,58)"


def test_truncate_short():
    assert _truncate("hello", 10) == "hello"

def test_truncate_long():
    result = _truncate("a" * 20, 10)
    assert len(result) == 10
    assert result.startswith("…")


def test_human_days_today():
    assert _human_days(0) == "today"

def test_human_days_yesterday():
    assert _human_days(1) == "yesterday"

def test_human_days_days():
    assert _human_days(5) == "5d ago"

def test_human_days_weeks():
    assert _human_days(14) == "2w ago"

def test_human_days_months():
    assert _human_days(60) == "2mo ago"

def test_human_days_year():
    assert "y" in _human_days(400)

def test_human_days_year_with_months():
    assert "1y 1mo ago" == _human_days(400)

def test_human_days_exact_year():
    assert _human_days(365) == "1y ago"


def test_score_bar_returns_text():
    from rich.text import Text
    bar = _score_bar(75)
    assert isinstance(bar, Text)


def test_row_style_critical():
    s = _row_style("CRITICAL")
    assert s.bold is True


def test_row_style_healthy():
    s = _row_style("HEALTHY")
    assert s.bold is not True


# ── Render functions (just verify no crash) ───────────────────────────────────

def _silent_console():
    """Return a patched console that writes to a buffer."""
    from rich.console import Console
    buf = StringIO()
    return Console(file=buf, highlight=False, legacy_windows=False, width=120)


@pytest.fixture(autouse=True)
def patch_console(monkeypatch):
    """Redirect all console output in display.py to a buffer."""
    from rich.console import Console
    buf = StringIO()
    mock_con = Console(file=buf, highlight=False, legacy_windows=False, width=120)
    monkeypatch.setattr("deathbed.display.console", mock_con)
    return mock_con


def test_render_header_no_crash():
    render_header()   # should not raise


def test_render_error_no_crash():
    render_error("Test Error", "Something went wrong")


def test_render_summary_no_crash():
    results = [_m(), _critical()]
    render_summary(results, 10, 1.23)


def test_render_summary_dead_code(monkeypatch):
    m = _m()
    m.dead_code_count = 5
    m.has_security_smell = True
    render_summary([m], 5, 0.5)


def test_render_table_no_crash():
    render_table([_m(), _critical()])


def test_render_table_empty():
    render_table([])


def test_render_table_trend_arrows():
    up   = _m(recent_churn=15, prev_churn=3)
    down = _m(path="src/b.py", recent_churn=4, prev_churn=12)
    render_table([up, down])


def test_render_table_security_smell():
    m = _m()
    m.has_security_smell = True
    m.security_smells = ["calls eval()"]
    render_table([m])


def test_render_table_clone():
    m = _m()
    m.clone_similarity = 0.75
    m.clone_of = "src/other.py"
    render_table([m])


def test_render_most_wanted_python():
    _render_most_wanted(_critical())


def test_render_most_wanted_with_dead_code():
    m = _critical()
    m.dead_code_count = 10
    m.dead_code_score = 35
    _render_most_wanted(m)


def test_render_most_wanted_non_python():
    m = _m(path="src/main.js", avg_complexity=None)
    _render_most_wanted(m)


def test_render_quick_wins_empty():
    _render_quick_wins([_m()])   # all healthy → no wins panel


def test_render_quick_wins_with_files():
    files = [_m(path=f"src/f{i}.py",
                days_since_commit=200, has_test_file=False) for i in range(3)]
    _render_quick_wins(files)


def test_render_quick_wins_security_smell():
    m = _m(days_since_commit=200, has_test_file=False)
    compute_scores(m)
    m.has_security_smell = True
    m.security_smells = ["imports pickle"]
    _render_quick_wins([m])


def test_render_tips_no_crash():
    results = [_critical(), _m()]
    _render_tips(results)


def test_render_tips_empty():
    _render_tips([])


def test_render_tips_multiple_patterns():
    # Create files that each have a different dominant problem
    files = [
        _m(path=f"src/a{i}.py", days_since_commit=900, has_test_file=False)
        for i in range(3)
    ] + [
        _m(path=f"src/b{i}.py", lines=2000, commit_count=200)
        for i in range(3)
    ]
    _render_tips(files)


def test_render_security_alerts_empty():
    _render_security_alerts([_m()])


def test_render_security_alerts_with_files():
    m = _m()
    m.has_security_smell = True
    m.security_smells = ["calls eval()", "imports pickle"]
    _render_security_alerts([m])


def test_render_security_alerts_many_files():
    files = []
    for i in range(20):
        m = _m(path=f"src/f{i}.py")
        m.has_security_smell = True
        m.security_smells = [f"smell_{i}"]
        files.append(m)
    _render_security_alerts(files)


def test_render_footer_no_crash():
    render_footer([_critical()], Path("."))


def test_render_footer_empty():
    render_footer([], Path("."))


def test_render_diff_all_improved():
    current    = [_m("a.py", commit_count=5)]
    historical = [_m("a.py", commit_count=50, days_since_commit=500)]
    render_diff(current, historical, "HEAD~1")


def test_render_diff_all_worsened():
    current    = [_m("a.py", days_since_commit=500, commit_count=200)]
    historical = [_m("a.py", commit_count=2)]
    render_diff(current, historical, "HEAD~1")


def test_render_diff_unchanged():
    m1 = _m("a.py")
    m2 = _m("a.py")
    render_diff([m1], [m2], "HEAD~5")


def test_render_diff_missing_historical():
    current    = [_m("new.py")]
    historical = [_m("other.py")]
    render_diff(current, historical, "HEAD~1")   # no overlap → empty table


def test_render_summary_with_repo_score():
    render_summary([_m()], 5, 0.5, repo_score=78, repo_score_delta=3)


def test_render_summary_with_since_ref():
    render_summary([_m()], 5, 0.5, since_ref="main", since_count=3)


def test_render_summary_with_ignored_count():
    render_summary([_m()], 5, 0.5, ignored_count=2)


def test_render_summary_negative_delta():
    render_summary([_m()], 5, 0.5, repo_score=60, repo_score_delta=-5)


def test_render_table_with_trend():
    m = _m()
    m.score_delta = 3
    render_table([m])


def test_render_table_trend_worsened():
    m = _m()
    m.score_delta = -5
    render_table([m])


def test_render_table_trend_zero():
    m = _m()
    m.score_delta = 0
    render_table([m])


def test_render_table_show_blame():
    m = _m()
    m.last_author = "Alice"
    m.last_commit_msg = "fix the bug"
    render_table([m], show_blame=True)


def test_render_table_show_blame_no_author():
    m = _m()
    render_table([m], show_blame=True)   # last_author="" → shows "—"


def test_render_most_wanted_with_sparkline():
    from deathbed.display import _render_most_wanted
    m = _critical()
    m.sparkline = "▁▂▃▅▇"
    _render_most_wanted(m)


def test_render_most_wanted_with_blame():
    from deathbed.display import _render_most_wanted
    m = _critical()
    m.last_author = "Bob"
    m.last_commit_msg = "refactor: big changes"
    _render_most_wanted(m, show_blame=True)


def test_render_most_wanted_blame_no_author():
    from deathbed.display import _render_most_wanted
    m = _critical()
    _render_most_wanted(m, show_blame=True)  # no author → no crash


def test_render_leaderboard_no_crash():
    from deathbed.display import render_leaderboard
    from deathbed.analyzer import AuthorStats
    authors = [
        AuthorStats("alice", 5, 72.0, 1, 2, "C"),
        AuthorStats("bob",   3, 88.0, 0, 1, "A"),
    ]
    render_leaderboard(authors)


def test_render_leaderboard_empty():
    from deathbed.display import render_leaderboard
    render_leaderboard([])


def test_render_footer_with_blame():
    from deathbed.display import render_footer
    m = _critical()
    m.last_author = "Carol"
    m.last_commit_msg = "wip: stuff"
    render_footer([m], Path("."), show_blame=True)


def test_render_markdown_output(capsys):
    results = [_m("src/foo.py"), _critical()]
    render_markdown(results)
    captured = capsys.readouterr()
    assert "|" in captured.out
    assert "FILE" in captured.out
    assert "src/foo.py" in captured.out
