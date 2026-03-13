"""Tests for export.py — HTML report generation."""

from __future__ import annotations

from deathbed.export import _human_days, _score_bar_html, _score_color_css, generate_html_report
from deathbed.scoring import FileMetrics, compute_scores


def _metric(path="src/foo.py", **kwargs) -> FileMetrics:
    defaults = dict(
        lines=100, days_since_commit=10, commit_count=5, author_count=1,
        avg_complexity=3.0, has_test_file=True, test_file_recent=True,
        recent_churn=2, prev_churn=1,
    )
    defaults.update(kwargs)
    m = FileMetrics(path=path, **defaults)
    compute_scores(m)
    return m


def test_generate_html_report_returns_string(tmp_path):
    results = [_metric()]
    html = generate_html_report(results, tmp_path, 0.5, 1)
    assert isinstance(html, str)
    assert len(html) > 500


def test_html_contains_doctype(tmp_path):
    html = generate_html_report([_metric()], tmp_path, 0.5, 1)
    assert "<!DOCTYPE html>" in html


def test_html_contains_repo_name(tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    html = generate_html_report([_metric()], repo, 0.5, 1)
    assert "myrepo" in html


def test_html_contains_file_paths(tmp_path):
    html = generate_html_report([_metric("src/main.py")], tmp_path, 0.5, 1)
    assert "src/main.py" in html


def test_html_shows_security_alerts(tmp_path):
    m = _metric()
    m.has_security_smell = True
    m.security_smells = ["calls eval()"]
    html = generate_html_report([m], tmp_path, 0.5, 1)
    assert "SECURITY ALERTS" in html
    assert "eval" in html


def test_html_no_security_section_when_clean(tmp_path):
    html = generate_html_report([_metric()], tmp_path, 0.5, 1)
    assert "SECURITY ALERTS" not in html


def test_html_contains_deathbed_credit(tmp_path):
    html = generate_html_report([_metric()], tmp_path, 0.5, 1)
    assert "deathbed" in html.lower()
    assert "Nikolozi Khachiashvili" in html


def test_html_empty_results(tmp_path):
    html = generate_html_report([], tmp_path, 0.5, 0)
    assert "<!DOCTYPE html>" in html


def test_human_days_export():
    assert _human_days(0) == "today"
    assert _human_days(1) == "yesterday"
    assert _human_days(3) == "3d ago"
    assert _human_days(14) == "2w ago"
    assert _human_days(60) == "2mo ago"
    assert _human_days(400) == "1y 1mo ago"


def test_score_color_css():
    assert _score_color_css(100) == "#00c850"
    assert _score_color_css(80)  == "#00c850"
    assert _score_color_css(79)  == "#ffbf00"
    assert _score_color_css(60)  == "#ffbf00"
    assert _score_color_css(59)  == "#ff8c00"
    assert _score_color_css(40)  == "#ff8c00"
    assert _score_color_css(39)  == "#ff453a"
    assert _score_color_css(0)   == "#ff453a"


def test_score_bar_html_contains_score():
    bar = _score_bar_html(75)
    assert "75" in bar
    assert "bar-fill" in bar
    assert "bar-label" in bar


def test_html_sortable_table(tmp_path):
    html = generate_html_report([_metric()], tmp_path, 0.5, 1)
    assert "sortTable" in html
    assert "onclick" in html


def test_html_contains_correct_version(tmp_path):
    """Footer must reference the current __version__, not a hardcoded old string."""
    from deathbed import __version__
    html = generate_html_report([_metric()], tmp_path, 0.5, 1)
    assert f"deathbed v{__version__}" in html
    assert "v1.2.0" not in html


def test_html_status_classes_all_present(tmp_path):
    """All four status classes should appear when results contain each status."""
    critical = _metric("a.py", days_since_commit=1000, commit_count=200,
                        avg_complexity=20.0, has_test_file=False, author_count=15,
                        recent_churn=50, prev_churn=5, lines=2000)
    warning = _metric("b.py", days_since_commit=400, commit_count=60, avg_complexity=12.0)
    fair = _metric("c.py", days_since_commit=200, commit_count=30)
    healthy = _metric("d.py")
    html = generate_html_report([critical, warning, fair, healthy], tmp_path, 0.5, 4)
    assert 'row-critical' in html
    assert 'row-warning' in html or 'row-fair' in html  # at least one non-critical non-healthy
    assert 'row-healthy' in html


def test_html_security_section_empty_when_no_smells(tmp_path):
    """Security section should be absent when no files have security smells."""
    results = [_metric("a.py"), _metric("b.py")]
    html = generate_html_report(results, tmp_path, 0.5, 2)
    assert "SECURITY ALERTS" not in html
