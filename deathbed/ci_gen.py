"""GitHub Actions CI workflow generation and badge utilities."""

from __future__ import annotations

from pathlib import Path

_WORKFLOW_TEMPLATE = """\
name: deathbed code health

on:
  pull_request:
    branches: [ main, master ]

jobs:
  deathbed:
    name: Code Health Check
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install deathbed
        run: pip install deathbed

      - name: Run deathbed (PR mode, CI exit code)
        id: deathbed
        run: |
          deathbed --since main --format markdown > deathbed-report.md || true
          echo "## 🪦 deathbed Code Health Report" >> $GITHUB_STEP_SUMMARY
          cat deathbed-report.md >> $GITHUB_STEP_SUMMARY
          deathbed --since main --ci
"""


def generate_workflow() -> str:
    """Return the GitHub Actions workflow YAML content."""
    return _WORKFLOW_TEMPLATE


def generate_badge_markdown(repo_path: Path) -> str:
    """
    Generate a shields.io badge markdown string for the current repo health.

    Reads the last saved repo score from history if available, otherwise
    runs a quick scan to compute one.
    """
    from .history import load_history
    from .git_utils import open_repo, get_repo_root
    from .scoring import letter_grade

    score = 0
    try:
        repo = open_repo(repo_path)
        root = get_repo_root(repo)
        scans = load_history(root)
        if scans:
            score = int(scans[-1].get("repo_score", 0))
        else:
            from .analyzer import analyze_repo
            from .scoring import compute_repo_score
            results = analyze_repo(repo_path, top=0, quiet=True)
            score = compute_repo_score(results)
    except Exception:
        score = 0

    grade = letter_grade(score)
    color_map = {
        "A": "brightgreen",
        "B": "green",
        "C": "yellow",
        "D": "orange",
        "F": "red",
    }
    color = color_map.get(grade, "lightgrey")

    label = f"deathbed-{grade}%20({score})-{color}"
    badge_url = f"https://img.shields.io/badge/{label}"
    repo_url = "https://github.com/NikoloziKhachiashvili/deathbed"
    return f"[![deathbed grade]({badge_url})]({repo_url})"
