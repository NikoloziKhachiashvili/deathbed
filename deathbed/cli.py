"""CLI entry point for deathbed."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from . import __version__
from .display import console, render_error


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--path", "-p",
    default=".",
    show_default=True,
    help="Path to the git repository to analyse.",
    type=click.Path(file_okay=False, dir_okay=True),
)
@click.option(
    "--top", "-t",
    default=50,
    show_default=True,
    help="Show only the N worst files (0 = all).",
    type=click.IntRange(min=0),
)
@click.option(
    "--format", "-f", "output_format",
    default="rich",
    show_default=True,
    type=click.Choice(["rich", "json"], case_sensitive=False),
    help="Output format.",
)
@click.option(
    "--min-score",
    default=None,
    type=click.IntRange(0, 100),
    help="Only show files with a health score strictly below this value.",
)
@click.version_option(__version__, "--version", "-V", prog_name="deathbed")
def main(
    path: str,
    top: int,
    output_format: str,
    min_score: Optional[int],
) -> None:
    """
    \b
    deathbed — every codebase has files that are dying. find them.

    Analyses a git repository and scores every tracked source file for
    health based on age, complexity, churn, size, authorship, and test
    coverage.  Worst files appear first.

    \b
    Examples:
      deathbed                       # analyse current directory
      deathbed --path /my/repo       # analyse another repo
      deathbed --top 20              # show only the 20 worst files
      deathbed --min-score 65        # show only WARNING / CRITICAL files
      deathbed --format json         # JSON output for CI pipelines
    """
    repo_path = Path(path).resolve()

    if output_format == "json":
        _run_json(repo_path, top, min_score)
    else:
        from .display import run_display
        run_display(repo_path, top, min_score)


def _run_json(repo_path: Path, top: int, min_score: Optional[int]) -> None:
    """Emit JSON output for CI / scripting use."""
    try:
        from .analyzer import analyze_repo

        results = analyze_repo(repo_path, top=top, min_score=min_score, quiet=True)
        payload = {
            "version": __version__,
            "repo": str(repo_path),
            "total": len(results),
            "files": [
                {
                    "file":              m.path,
                    "health_score":      m.composite_score,
                    "status":            m.status,
                    "diagnosis":         m.diagnosis,
                    "lines":             m.lines,
                    "days_since_commit": m.days_since_commit,
                    "commit_count":      m.commit_count,
                    "author_count":      m.author_count,
                    "avg_complexity":    m.avg_complexity,
                    "has_test_file":     m.has_test_file,
                    "scores": {
                        "size":       m.size_score,
                        "age":        m.age_score,
                        "churn":      m.churn_score,
                        "complexity": m.complexity_score,
                        "authors":    m.author_score,
                        "test":       m.test_score,
                    },
                }
                for m in results
            ],
        }
        click.echo(json.dumps(payload, indent=2))
    except Exception as exc:
        render_error("JSON output failed", str(exc))
        sys.exit(1)
