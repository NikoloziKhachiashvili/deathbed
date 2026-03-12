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
    type=click.Choice(["rich", "json", "markdown"], case_sensitive=False),
    help="Output format.",
)
@click.option(
    "--min-score",
    default=None,
    type=click.IntRange(0, 100),
    help="Only show files with a health score strictly below this value.",
)
@click.option(
    "--watch", "-w",
    is_flag=True,
    default=False,
    help="Live auto-refreshing dashboard — re-runs every 30 seconds.",
)
@click.option(
    "--diff",
    default=None,
    metavar="REF",
    help="Compare health scores between HEAD and REF (e.g. HEAD~1, main).",
)
@click.option(
    "--export",
    "export_format",
    default=None,
    type=click.Choice(["html"], case_sensitive=False),
    help="Export a self-contained report file (html).",
)
@click.option(
    "--ci",
    is_flag=True,
    default=False,
    help="Exit code 1 if any CRITICAL files are found (for CI pipelines).",
)
@click.option(
    "--since",
    default=None,
    metavar="REF",
    help="PR mode — only show files changed since REF (e.g. main, HEAD~5).",
)
@click.option(
    "--blame",
    is_flag=True,
    default=False,
    help="Show last author column in table and blame info in Most Wanted.",
)
@click.option(
    "--leaderboard",
    is_flag=True,
    default=False,
    help="Show team leaderboard grouped by last author (implies --blame).",
)
@click.option(
    "--org",
    default=None,
    metavar="PATH",
    help="Scan a directory of git repos for an org-wide health report.",
    type=click.Path(file_okay=False, dir_okay=True),
)
@click.option(
    "--repo",
    default=None,
    metavar="NAME",
    help="With --org: drill down into a specific repo by directory name.",
)
@click.option(
    "--plan",
    is_flag=True,
    default=False,
    help="Generate a prioritised refactoring roadmap (Sprint 1/2/3).",
)
@click.option(
    "--init-ci",
    is_flag=True,
    default=False,
    help="Write a ready-to-use .github/workflows/deathbed.yml to the current repo.",
)
@click.option(
    "--badge",
    is_flag=True,
    default=False,
    help="Print the Markdown badge for the current repo health score.",
)
@click.version_option(__version__, "--version", "-V", prog_name="deathbed")
def main(
    path: str,
    top: int,
    output_format: str,
    min_score: Optional[int],
    watch: bool,
    diff: Optional[str],
    export_format: Optional[str],
    ci: bool,
    since: Optional[str],
    blame: bool,
    leaderboard: bool,
    org: Optional[str],
    repo: Optional[str],
    plan: bool,
    init_ci: bool,
    badge: bool,
) -> None:
    """
    \b
    deathbed — every codebase has files that are dying. find them.

    Analyses a git repository and scores every tracked source file for
    health based on age, complexity, churn, size, authorship, test
    coverage, coupling, dead code, security patterns, and clone risk.

    \b
    Examples:
      deathbed                          # analyse current directory
      deathbed --path /my/repo          # analyse another repo
      deathbed --top 20                 # show only the 20 worst files
      deathbed --min-score 65           # show only WARNING / CRITICAL files
      deathbed --format json            # JSON output for scripting
      deathbed --format markdown        # Markdown table output
      deathbed --watch                  # live auto-refreshing dashboard
      deathbed --diff HEAD~1            # compare health vs last commit
      deathbed --export html            # export HTML report
      deathbed --ci                     # exit 1 if any CRITICAL files (CI use)
      deathbed --since main             # PR mode — only changed files
      deathbed --blame                  # show last author in table
      deathbed --leaderboard            # team view by last author
      deathbed --org /projects          # org-wide health report
      deathbed --org /projects --repo myrepo  # drill into one repo
      deathbed --plan                   # generate refactoring roadmap
      deathbed --plan --format markdown # export roadmap as markdown
      deathbed --init-ci                # create GitHub Actions workflow
      deathbed --badge                  # print shields.io badge markdown
    """
    repo_path = Path(path).resolve()

    # ── Standalone utility modes ──────────────────────────────────────────────
    if init_ci:
        _run_init_ci(repo_path)
        return

    if badge:
        _run_badge(repo_path)
        return

    # ── Org-wide scan ─────────────────────────────────────────────────────────
    if org is not None:
        org_path = Path(org).resolve()
        if repo is not None:
            # Drill down into one repo within the org directory
            drill_path = org_path / repo
            from .display import run_display
            run_display(drill_path, top, min_score, ci_mode=ci,
                        since_ref=since, include_blame=blame or leaderboard)
            return
        from .display import run_org_display
        run_org_display(org_path, top, min_score, output_format=output_format)
        return

    # ── Refactor plan ─────────────────────────────────────────────────────────
    if plan:
        from .display import run_plan_display
        run_plan_display(repo_path, top, min_score, output_format=output_format)
        return

    # ── Mutually exclusive mode dispatch ──────────────────────────────────────
    if leaderboard:
        from .display import run_leaderboard_display
        run_leaderboard_display(repo_path, top, min_score)
        return

    if diff is not None:
        from .display import run_diff_display
        run_diff_display(repo_path, diff, top, min_score)
        return

    if export_format == "html":
        _run_html_export(repo_path, top, min_score)
        return

    if watch:
        from .display import run_watch_display
        run_watch_display(repo_path, top, min_score)
        return

    if output_format == "json":
        _run_json(repo_path, top, min_score)
        return

    if output_format == "markdown":
        _run_markdown(repo_path, top, min_score)
        return

    # Default: rich terminal display (ci flag modifies exit behaviour)
    from .display import run_display
    run_display(repo_path, top, min_score, ci_mode=ci, since_ref=since, include_blame=blame)


# ── Sub-runners ───────────────────────────────────────────────────────────────

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
                    "file":               m.path,
                    "health_score":       m.composite_score,
                    "status":             m.status,
                    "diagnosis":          m.diagnosis,
                    "lines":              m.lines,
                    "days_since_commit":  m.days_since_commit,
                    "commit_count":       m.commit_count,
                    "author_count":       m.author_count,
                    "avg_complexity":     m.avg_complexity,
                    "has_test_file":      m.has_test_file,
                    "test_has_assertions": m.test_has_assertions,
                    "dead_code_count":    m.dead_code_count,
                    "has_security_smell": m.has_security_smell,
                    "security_smells":    m.security_smells,
                    "clone_similarity":   round(m.clone_similarity, 3),
                    "clone_of":           m.clone_of,
                    "coupling_count":     m.coupling_count,
                    "importers":          m.importers,
                    "scores": {
                        "size":         m.size_score,
                        "age":          m.age_score,
                        "churn":        m.churn_score,
                        "complexity":   m.complexity_score,
                        "authors":      m.author_score,
                        "test":         m.test_score,
                        "recent_churn": m.recent_churn_score,
                        "dead_code":    m.dead_code_score,
                        "coupling":     m.coupling_score,
                    },
                }
                for m in results
            ],
        }
        click.echo(json.dumps(payload, indent=2))
    except Exception as exc:
        render_error("JSON output failed", str(exc))
        sys.exit(1)


def _run_markdown(repo_path: Path, top: int, min_score: Optional[int]) -> None:
    """Emit a Markdown table to stdout."""
    try:
        from .analyzer import analyze_repo
        from .display import render_markdown

        results = analyze_repo(repo_path, top=top, min_score=min_score, quiet=True)
        render_markdown(results)
    except Exception as exc:
        render_error("Markdown output failed", str(exc))
        sys.exit(1)


def _run_html_export(repo_path: Path, top: int, min_score: Optional[int]) -> None:
    """Analyse repo and write a self-contained HTML report to disk."""
    import time

    from .analyzer import analyze_repo
    from .display import console, make_progress, render_error, render_header, _truncate
    from .export import generate_html_report

    render_header()

    try:
        start = time.monotonic()
        total_scanned = 0

        with make_progress() as progress:
            task = progress.add_task(
                "Scanning for HTML export",
                total=None,
                color="rgb(220,20,60)",
                current_file="",
            )

            def on_progress(rel: str, idx: int, total: int) -> None:
                nonlocal total_scanned
                total_scanned = total
                progress.update(
                    task, total=total, completed=idx,
                    current_file=_truncate(rel, 60) if rel else "",
                )

            results = analyze_repo(
                repo_path, top=top, min_score=min_score,
                on_progress=on_progress,
            )

        elapsed = time.monotonic() - start

        if total_scanned == 0:
            render_error("No files found", "No analysable source files found.")
            return

        html = generate_html_report(results, repo_path, elapsed, total_scanned)
        out_path = Path("deathbed-report.html")
        out_path.write_text(html, encoding="utf-8")

        from rich.panel import Panel
        from .display import C_GREEN, C_DIM_GREEN
        console.print(
            Panel(
                f"[bold {C_GREEN}]  ✅  Report saved to {out_path.resolve()}[/]",
                border_style=C_DIM_GREEN,
            )
        )
    except Exception as exc:
        render_error("HTML export failed", str(exc))
        sys.exit(1)


def _run_init_ci(repo_path: Path) -> None:
    """Write a GitHub Actions workflow file for deathbed."""
    from .ci_gen import generate_workflow
    from .display import C_GREEN, C_DIM_GREEN, C_AMBER, C_RED1
    from rich.panel import Panel

    workflow_dir = repo_path / ".github" / "workflows"
    workflow_file = workflow_dir / "deathbed.yml"

    if workflow_file.exists():
        click.echo(
            f"⚠️  {workflow_file} already exists. Remove it first or edit it manually.",
            err=True,
        )
        sys.exit(1)

    try:
        workflow_dir.mkdir(parents=True, exist_ok=True)
        workflow_file.write_text(generate_workflow(), encoding="utf-8")
        console.print(
            Panel(
                f"[bold {C_GREEN}]  ✅  Created {workflow_file}\n\n"
                f"  Add this to your README:\n"
                f"  deathbed --badge\n[/]",
                title=f"[bold {C_GREEN}]  🚀  CI WORKFLOW CREATED  [/]",
                border_style=C_DIM_GREEN,
            )
        )
    except Exception as exc:
        render_error("init-ci failed", str(exc))
        sys.exit(1)


def _run_badge(repo_path: Path) -> None:
    """Print the shields.io Markdown badge for this repo."""
    from .ci_gen import generate_badge_markdown

    try:
        badge = generate_badge_markdown(repo_path)
        click.echo(badge)
    except Exception as exc:
        render_error("badge failed", str(exc))
        sys.exit(1)
