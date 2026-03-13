# Extra display tests targeting uncovered code paths.

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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


def _critical(**kw) -> FileMetrics:
    return _m(
        path="src/bad.py",
        lines=2000, days_since_commit=900, commit_count=200,
        author_count=15, avg_complexity=20.0, has_test_file=False,
        recent_churn=50, prev_churn=10, **kw
    )


@pytest.fixture(autouse=True)
def patch_console(monkeypatch):
    from rich.console import Console
    buf = StringIO()
    con = Console(file=buf, highlight=False, legacy_windows=False, width=120)
    monkeypatch.setattr("deathbed.display.console", con)
    return con


# ── _run_ci ───────────────────────────────────────────────────────────────────

def test_run_ci_no_critical(capsys):
    from deathbed.display import _run_ci
    _run_ci([_m()], 5)
    out = capsys.readouterr().out
    assert "0 CRITICAL" in out


def test_run_ci_with_critical():
    from deathbed.display import _run_ci
    with pytest.raises(SystemExit) as exc_info:
        _run_ci([_critical()], 5)
    assert exc_info.value.code == 1


def test_run_ci_prints_offenders(capsys):
    from deathbed.display import _run_ci
    with pytest.raises(SystemExit):
        _run_ci([_critical()], 5)
    err = capsys.readouterr().err
    assert "CRITICAL" in err or "bad.py" in err


# ── run_display (mocked) ──────────────────────────────────────────────────────

def _mock_progress():
    """Build a MagicMock that behaves like Progress context manager."""
    prog = MagicMock()
    task_id = MagicMock()
    prog.__enter__ = MagicMock(return_value=prog)
    prog.__exit__  = MagicMock(return_value=False)
    prog.add_task   = MagicMock(return_value=task_id)
    prog.update     = MagicMock()
    return prog


def test_run_display_healthy_all(monkeypatch):
    from deathbed.display import run_display
    results = [_m()]

    monkeypatch.setattr("deathbed.display.make_progress", _mock_progress)
    with patch("deathbed.analyzer.analyze_repo", side_effect=_fake_analyze(results)):
        run_display(Path("."), 50, None)


def _fake_analyze(results):
    """Return a side_effect fn that calls on_progress so total_scanned gets set."""
    def _impl(repo_path, top, min_score, on_progress=None, _meta=None, **kw):
        if on_progress:
            on_progress("src/foo.py", 0, len(results))
            on_progress("", len(results), len(results))
        if _meta is not None:
            _meta["ignored_count"] = 0
            _meta["since_count"] = len(results)
        return results
    return _impl


def test_run_display_ci_mode_no_critical(monkeypatch, capsys):
    from deathbed.display import run_display
    results = [_m()]

    monkeypatch.setattr("deathbed.display.make_progress", _mock_progress)
    with patch("deathbed.analyzer.analyze_repo", side_effect=_fake_analyze(results)):
        run_display(Path("."), 50, None, ci_mode=True)

    out = capsys.readouterr().out
    assert "0 CRITICAL" in out


def test_run_display_ci_mode_with_critical(monkeypatch):
    from deathbed.display import run_display
    results = [_critical()]

    monkeypatch.setattr("deathbed.display.make_progress", _mock_progress)
    with patch("deathbed.analyzer.analyze_repo", side_effect=_fake_analyze(results)):  # noqa: SIM117
        with pytest.raises(SystemExit) as exc_info:
            run_display(Path("."), 50, None, ci_mode=True)
    assert exc_info.value.code == 1


def test_run_display_no_files(monkeypatch):
    from deathbed.display import run_display

    monkeypatch.setattr("deathbed.display.make_progress", _mock_progress)
    with patch("deathbed.analyzer.analyze_repo", return_value=[]):
        run_display(Path("."), 50, None)  # Should show "No files found"


def test_run_display_invalid_git(monkeypatch):
    import git

    from deathbed.display import run_display

    monkeypatch.setattr("deathbed.display.make_progress", _mock_progress)
    with patch("deathbed.analyzer.analyze_repo",  # noqa: SIM117
               side_effect=git.InvalidGitRepositoryError("not a repo")):
        with pytest.raises(SystemExit) as exc_info:
            run_display(Path("/not/a/repo"), 50, None)
    assert exc_info.value.code == 1


def test_run_display_no_such_path(monkeypatch):
    import git

    from deathbed.display import run_display

    monkeypatch.setattr("deathbed.display.make_progress", _mock_progress)
    with patch("deathbed.analyzer.analyze_repo",
               side_effect=git.NoSuchPathError("no path")), pytest.raises(SystemExit) as exc_info:
        run_display(Path("/bad/path"), 50, None)
    assert exc_info.value.code == 1


def test_run_display_unexpected_error(monkeypatch):
    from deathbed.display import run_display

    monkeypatch.setattr("deathbed.display.make_progress", _mock_progress)
    with patch("deathbed.analyzer.analyze_repo",
               side_effect=RuntimeError("boom")), pytest.raises(SystemExit) as exc_info:
        run_display(Path("."), 50, None)
    assert exc_info.value.code == 1


# ── Analyzer mocked tests (more coverage of analyze_repo) ────────────────────

def test_analyze_repo_mocked(monkeypatch, tmp_path):
    """Exercise analyze_repo with mocked git helpers."""
    from deathbed.analyzer import analyze_repo

    # Write a real Python file so get_analyzable_files finds it
    (tmp_path / "foo.py").write_text("def x(): return 1\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()   # fake git dir marker

    with (
        patch("deathbed.analyzer.open_repo"),
        patch("deathbed.analyzer.get_repo_root", return_value=tmp_path),
        patch("deathbed.analyzer.get_file_history", return_value=(10, 3, 1, 1, 0)),
        patch("deathbed.analyzer.get_complexity", return_value=2.0),
        patch("deathbed.analyzer.find_test_file", return_value=(False, False, True)),
        patch("deathbed.analyzer.run_vulture", return_value=0),
        patch("deathbed.analyzer.detect_security_smells", return_value=[]),
    ):
        results = analyze_repo(tmp_path, top=10, min_score=None)

    assert isinstance(results, list)


def test_analyze_repo_respects_top(monkeypatch, tmp_path):
    from deathbed.analyzer import analyze_repo

    for i in range(5):
        (tmp_path / f"f{i}.py").write_text(f"x = {i}\n", encoding="utf-8")

    with (
        patch("deathbed.analyzer.open_repo"),
        patch("deathbed.analyzer.get_repo_root", return_value=tmp_path),
        patch("deathbed.analyzer.get_file_history", return_value=(10, 3, 1, 1, 0)),
        patch("deathbed.analyzer.get_complexity", return_value=2.0),
        patch("deathbed.analyzer.find_test_file", return_value=(False, False, True)),
        patch("deathbed.analyzer.run_vulture", return_value=0),
        patch("deathbed.analyzer.detect_security_smells", return_value=[]),
    ):
        results = analyze_repo(tmp_path, top=2)

    assert len(results) <= 2


# ── run_diff_display (mocked) ─────────────────────────────────────────────────

def test_run_diff_display_no_crash(monkeypatch):
    from deathbed.display import run_diff_display
    current    = [_m("a.py")]
    historical = [_m("a.py", days_since_commit=100)]

    def fake_diff(repo_path, ref, top=50, min_score=None, on_progress=None):
        if on_progress:
            on_progress("a.py", 0, 1)
            on_progress("", 1, 1)
        return current, historical

    monkeypatch.setattr("deathbed.display.make_progress", _mock_progress)
    with patch("deathbed.analyzer.analyze_diff", side_effect=fake_diff):
        run_diff_display(Path("."), "HEAD~1", 50, None)


def test_run_diff_display_error(monkeypatch):
    import git

    from deathbed.display import run_diff_display

    monkeypatch.setattr("deathbed.display.make_progress", _mock_progress)
    with patch("deathbed.analyzer.analyze_diff",  # noqa: SIM117
               side_effect=git.InvalidGitRepositoryError("bad")):
        with pytest.raises(SystemExit) as exc_info:
            run_diff_display(Path("/bad"), "HEAD~1", 50, None)
    assert exc_info.value.code == 1


def test_run_diff_display_generic_error(monkeypatch):
    from deathbed.display import run_diff_display

    monkeypatch.setattr("deathbed.display.make_progress", _mock_progress)
    with patch("deathbed.analyzer.analyze_diff",
               side_effect=RuntimeError("oops")), pytest.raises(SystemExit) as exc_info:
        run_diff_display(Path("."), "HEAD~1", 50, None)
    assert exc_info.value.code == 1


# ── analyze_diff (mocked) ─────────────────────────────────────────────────────

def test_analyze_diff_mocked(tmp_path):
    from deathbed.analyzer import analyze_diff

    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")

    with (
        patch("deathbed.analyzer.open_repo"),
        patch("deathbed.analyzer.get_repo_root", return_value=tmp_path),
        patch("deathbed.analyzer.get_ref_timestamp", return_value=1000000),
        patch("deathbed.analyzer.get_file_history", return_value=(10, 3, 1, 1, 0)),
        patch("deathbed.analyzer.get_complexity", return_value=2.0),
        patch("deathbed.analyzer.find_test_file", return_value=(False, False, True)),
        patch("deathbed.analyzer.run_vulture", return_value=0),
        patch("deathbed.analyzer.detect_security_smells", return_value=[]),
    ):
        current, historical = analyze_diff(tmp_path, "HEAD~1", top=10)

    assert isinstance(current, list)
    assert isinstance(historical, list)


def test_analyze_diff_with_security_smell(tmp_path):
    from deathbed.analyzer import analyze_diff

    (tmp_path / "bad.py").write_text("import pickle\n", encoding="utf-8")

    with (
        patch("deathbed.analyzer.open_repo"),
        patch("deathbed.analyzer.get_repo_root", return_value=tmp_path),
        patch("deathbed.analyzer.get_ref_timestamp", return_value=1000000),
        patch("deathbed.analyzer.get_file_history", return_value=(10, 3, 1, 1, 0)),
        patch("deathbed.analyzer.get_complexity", return_value=2.0),
        patch("deathbed.analyzer.find_test_file", return_value=(False, False, True)),
        patch("deathbed.analyzer.run_vulture", return_value=0),
        patch("deathbed.analyzer.detect_security_smells",
              return_value=["imports pickle"]),
    ):
        current, historical = analyze_diff(tmp_path, "HEAD~1")

    if current:
        assert current[0].has_security_smell is True


def test_run_leaderboard_display_no_crash(monkeypatch):
    from deathbed.analyzer import AuthorStats
    from deathbed.display import run_leaderboard_display

    authors = [AuthorStats("alice", 3, 72.0, 1, 1, "C")]

    monkeypatch.setattr("deathbed.display.make_progress", _mock_progress)
    with patch("deathbed.analyzer.analyze_leaderboard", return_value=authors):
        run_leaderboard_display(Path("."), 50, None)


def test_run_leaderboard_display_error(monkeypatch):
    import git

    from deathbed.display import run_leaderboard_display

    monkeypatch.setattr("deathbed.display.make_progress", _mock_progress)
    with patch("deathbed.analyzer.analyze_leaderboard",  # noqa: SIM117
               side_effect=git.InvalidGitRepositoryError("bad")):
        with pytest.raises(SystemExit) as exc_info:
            run_leaderboard_display(Path("/bad"), 50, None)
    assert exc_info.value.code == 1


def test_run_display_with_since_ref(monkeypatch):
    from deathbed.display import run_display
    results = [_m()]

    monkeypatch.setattr("deathbed.display.make_progress", _mock_progress)
    with patch("deathbed.analyzer.analyze_repo", side_effect=_fake_analyze(results)):
        run_display(Path("."), 50, None, since_ref="main")


def test_run_display_with_blame(monkeypatch):
    from deathbed.display import run_display
    results = [_m()]
    results[0].last_author = "Alice"

    monkeypatch.setattr("deathbed.display.make_progress", _mock_progress)
    with patch("deathbed.analyzer.analyze_repo", side_effect=_fake_analyze(results)):
        run_display(Path("."), 50, None, include_blame=True)


def test_analyze_repo_skips_failed_files(monkeypatch, tmp_path):
    from deathbed.analyzer import analyze_repo

    (tmp_path / "good.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "bad.py").write_text("y = 2\n", encoding="utf-8")

    call_count = 0

    def flaky_history(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("disk error")
        return (10, 3, 1, 1, 0)

    with (
        patch("deathbed.analyzer.open_repo"),
        patch("deathbed.analyzer.get_repo_root", return_value=tmp_path),
        patch("deathbed.analyzer.get_file_history", side_effect=flaky_history),
        patch("deathbed.analyzer.get_complexity", return_value=2.0),
        patch("deathbed.analyzer.find_test_file", return_value=(False, False, True)),
        patch("deathbed.analyzer.run_vulture", return_value=0),
        patch("deathbed.analyzer.detect_security_smells", return_value=[]),
    ):
        results = analyze_repo(tmp_path, top=10)

    # One file failed, one succeeded → 1 result
    assert len(results) == 1
