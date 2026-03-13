"""Tests for org.py — multi-repo org analysis."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from deathbed.org import OrgRepoStats, analyze_org, org_combined_score

# ── OrgRepoStats ──────────────────────────────────────────────────────────────

def test_org_repo_stats_defaults():
    r = OrgRepoStats(
        name="myrepo", path=Path("/tmp/myrepo"),
        repo_score=72, grade="C",
        critical_count=2, warning_count=3,
        file_count=10, worst_file="src/bad.py", worst_score=25,
    )
    assert r.error == ""
    assert r.name == "myrepo"


# ── org_combined_score ────────────────────────────────────────────────────────

def test_org_combined_score_empty():
    assert org_combined_score([]) == 0


def test_org_combined_score_single():
    r = OrgRepoStats("a", Path("."), 80, "B", 0, 0, 5, "", 80)
    assert org_combined_score([r]) == 80


def test_org_combined_score_average():
    r1 = OrgRepoStats("a", Path("."), 60, "C", 0, 0, 5, "", 50)
    r2 = OrgRepoStats("b", Path("."), 80, "B", 0, 0, 5, "", 70)
    assert org_combined_score([r1, r2]) == 70


def test_org_combined_score_ignores_errors():
    r1 = OrgRepoStats("a", Path("."), 60, "C", 0, 0, 5, "", 50)
    r2 = OrgRepoStats("b", Path("."), 0, "F", 0, 0, 0, "", 0, error="failed")
    assert org_combined_score([r1, r2]) == 60


# ── analyze_org ───────────────────────────────────────────────────────────────

def test_analyze_org_empty_dir(tmp_path):
    result = analyze_org(tmp_path)
    assert result == []


def test_analyze_org_skips_non_git_subdirs(tmp_path):
    import git
    (tmp_path / "not_a_repo").mkdir()
    with patch("deathbed.org.open_repo", side_effect=git.InvalidGitRepositoryError("nope")):
        result = analyze_org(tmp_path)
    assert result == []


def test_analyze_org_skips_files(tmp_path):
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
    result = analyze_org(tmp_path)
    assert result == []


def test_analyze_org_with_mock_repos(tmp_path):
    repo1 = tmp_path / "repo1"
    repo1.mkdir()
    repo2 = tmp_path / "repo2"
    repo2.mkdir()

    from deathbed.scoring import FileMetrics, compute_scores

    def _make_result(path: str) -> FileMetrics:
        m = FileMetrics(path=path, lines=100, days_since_commit=10, commit_count=3,
                        author_count=1, avg_complexity=2.0, has_test_file=True,
                        test_file_recent=True, recent_churn=1, prev_churn=0)
        compute_scores(m)
        return m

    with (
        patch("deathbed.org.open_repo"),
        patch("deathbed.org.analyze_repo", return_value=[_make_result("a.py")]),
    ):
        results = analyze_org(tmp_path)

    assert len(results) == 2
    # Sorted worst-first — all healthy so scores should be equal
    for r in results:
        assert r.repo_score > 0
        assert r.grade in ("A", "B", "C", "D", "F")
        assert r.error == ""


def test_analyze_org_handles_analysis_error(tmp_path):
    repo1 = tmp_path / "broken"
    repo1.mkdir()

    with (
        patch("deathbed.org.open_repo"),
        patch("deathbed.org.analyze_repo", side_effect=RuntimeError("oops")),
    ):
        results = analyze_org(tmp_path)

    assert len(results) == 1
    assert results[0].error != ""
    assert results[0].grade == "F"


def test_analyze_org_sorted_worst_first(tmp_path):
    repo1 = tmp_path / "good"
    repo2 = tmp_path / "bad"
    repo1.mkdir()
    repo2.mkdir()

    from deathbed.scoring import FileMetrics, compute_scores

    def healthy_result() -> list:
        m = FileMetrics(path="a.py", lines=50, days_since_commit=5, commit_count=2,
                        author_count=1, avg_complexity=1.0, has_test_file=True,
                        test_file_recent=True, recent_churn=0, prev_churn=0)
        compute_scores(m)
        return [m]

    def bad_result() -> list:
        m = FileMetrics(path="bad.py", lines=3000, days_since_commit=800,
                        commit_count=200, author_count=15, avg_complexity=20.0,
                        has_test_file=False, test_file_recent=False,
                        recent_churn=50, prev_churn=10)
        compute_scores(m)
        return [m]

    call_count = [0]

    def mock_analyze(path, **kwargs):
        call_count[0] += 1
        if path.name == "good":
            return healthy_result()
        return bad_result()

    with (
        patch("deathbed.org.open_repo"),
        patch("deathbed.org.analyze_repo", side_effect=mock_analyze),
    ):
        results = analyze_org(tmp_path)

    assert len(results) == 2
    assert results[0].repo_score <= results[1].repo_score
