"""Tests for ci_gen.py — workflow generation and badge utilities."""

from __future__ import annotations

from unittest.mock import patch

from deathbed.ci_gen import generate_badge_markdown, generate_workflow

# ── generate_workflow ─────────────────────────────────────────────────────────

def test_generate_workflow_returns_string():
    result = generate_workflow()
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_workflow_contains_key_steps():
    wf = generate_workflow()
    assert "actions/checkout" in wf
    assert "pip install deathbed" in wf
    assert "deathbed --since main --ci" in wf


def test_generate_workflow_valid_yaml_structure():
    wf = generate_workflow()
    assert "name:" in wf
    assert "on:" in wf
    assert "jobs:" in wf
    assert "steps:" in wf


def test_generate_workflow_triggers_on_pr():
    wf = generate_workflow()
    assert "pull_request" in wf


def test_generate_workflow_github_summary():
    wf = generate_workflow()
    assert "GITHUB_STEP_SUMMARY" in wf


# ── generate_badge_markdown ───────────────────────────────────────────────────

def test_generate_badge_returns_string(tmp_path):
    with (
        patch("deathbed.git_utils.open_repo"),
        patch("deathbed.git_utils.get_repo_root", return_value=tmp_path),
        patch("deathbed.history.load_history", return_value=[{"repo_score": 85}]),
    ):
        badge = generate_badge_markdown(tmp_path)
    assert isinstance(badge, str)
    assert len(badge) > 0


def test_generate_badge_contains_shields_url(tmp_path):
    with (
        patch("deathbed.git_utils.open_repo"),
        patch("deathbed.git_utils.get_repo_root", return_value=tmp_path),
        patch("deathbed.history.load_history", return_value=[{"repo_score": 72}]),
    ):
        badge = generate_badge_markdown(tmp_path)
    assert "shields.io" in badge or "img.shields" in badge


def test_generate_badge_grade_a(tmp_path):
    with (
        patch("deathbed.git_utils.open_repo"),
        patch("deathbed.git_utils.get_repo_root", return_value=tmp_path),
        patch("deathbed.history.load_history", return_value=[{"repo_score": 90}]),
    ):
        badge = generate_badge_markdown(tmp_path)
    assert "brightgreen" in badge


def test_generate_badge_grade_f(tmp_path):
    with (
        patch("deathbed.git_utils.open_repo"),
        patch("deathbed.git_utils.get_repo_root", return_value=tmp_path),
        patch("deathbed.history.load_history", return_value=[{"repo_score": 20}]),
    ):
        badge = generate_badge_markdown(tmp_path)
    assert "red" in badge


def test_generate_badge_no_history_falls_back(tmp_path):
    from deathbed.scoring import FileMetrics, compute_scores

    m = FileMetrics(path="a.py", lines=50, days_since_commit=5, commit_count=2,
                    author_count=1, avg_complexity=1.0, has_test_file=True,
                    test_file_recent=True, recent_churn=0, prev_churn=0)
    compute_scores(m)

    with (
        patch("deathbed.git_utils.open_repo"),
        patch("deathbed.git_utils.get_repo_root", return_value=tmp_path),
        patch("deathbed.history.load_history", return_value=[]),
        patch("deathbed.analyzer.analyze_repo", return_value=[m]),
    ):
        badge = generate_badge_markdown(tmp_path)
    assert "![" in badge


def test_generate_badge_graceful_on_error(tmp_path):
    with patch("deathbed.git_utils.open_repo", side_effect=Exception("no repo")):
        badge = generate_badge_markdown(tmp_path)
    # Should still return a valid badge with score 0
    assert isinstance(badge, str)
    assert "shields.io" in badge or "img.shields" in badge


def test_generate_badge_is_markdown_image(tmp_path):
    with (
        patch("deathbed.git_utils.open_repo"),
        patch("deathbed.git_utils.get_repo_root", return_value=tmp_path),
        patch("deathbed.history.load_history", return_value=[{"repo_score": 78}]),
    ):
        badge = generate_badge_markdown(tmp_path)
    assert badge.startswith("[![")
