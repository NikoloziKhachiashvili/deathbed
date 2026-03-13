"""
Main display entry points: run_display, run_watch_display, etc.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import git

from ..scoring import FileMetrics
from ..utils import __version__
from .palette import (
    C_CRIMSON,
    C_DIM_GREEN,
    C_GREEN,
    C_GREY,
    _truncate,
    console,
    make_progress,
    render_error,
    render_header,
    render_org_header,
)
from .renderers import (
    render_diff,
    render_footer,
    render_leaderboard,
    render_org_report,
    render_plan,
    render_summary,
    render_table,
)

log = logging.getLogger(__name__)


def run_display(
    repo_path: Path,
    top: int,
    min_score: int | None,
    ci_mode: bool = False,
    since_ref: str | None = None,
    include_blame: bool = False,
) -> None:
    """Full deathbed run: header → scan → table → footer."""
    from ..analyzer import analyze_repo
    from ..history import enrich_with_history, get_repo_score_delta, save_scan
    from ..scoring import compute_repo_score

    if not ci_mode:
        render_header()

    repo_root = repo_path
    try:
        from ..git_utils import get_repo_root, open_repo
        repo_root = get_repo_root(open_repo(repo_path))
    except Exception as exc:
        log.debug("Could not determine repo root: %s", exc)

    try:
        start = time.monotonic()
        results: list[FileMetrics] = []
        total_scanned = 0
        meta: dict = {}

        with make_progress() as progress:
            task = progress.add_task(
                "Scanning repository",
                total=None,
                color=C_CRIMSON,
                current_file="",
            )

            def on_progress(rel: str, idx: int, total: int) -> None:
                nonlocal total_scanned
                total_scanned = total
                progress.update(
                    task,
                    total=total,
                    completed=idx,
                    current_file=_truncate(rel, 60) if rel else "",
                )

            results = analyze_repo(
                repo_path,
                top=top,
                min_score=min_score,
                on_progress=on_progress,
                since_ref=since_ref,
                include_blame=include_blame,
                _meta=meta,
            )

        elapsed = time.monotonic() - start

        if total_scanned == 0:
            render_error(
                "No files found",
                "No analysable source files were found in the repository. "
                "Make sure you are inside a git repo with tracked .py / .js / .ts / ... files.",
            )
            return

        repo_score       = compute_repo_score(results)
        enrich_with_history(results, repo_root)
        repo_score_delta = get_repo_score_delta(repo_root, repo_score)
        save_scan(repo_root, results, repo_score)

        ignored_count = meta.get("ignored_count", 0)
        since_count   = meta.get("since_count", 0)
        lang_counts   = meta.get("lang_counts", {})

        decay_predictions: dict = {}
        try:
            from ..config import load_config
            from ..decay import predict_decay
            cfg = load_config(repo_root)
            decay_cfg = cfg.get("decay", {})
            thresh_cfg = cfg.get("thresholds", {})
            decay_predictions = predict_decay(
                repo_root,
                results,
                min_scans=decay_cfg.get("min_scans", 3),
                horizon_days=decay_cfg.get("horizon_days", 30),
                warning_threshold=thresh_cfg.get("warning", 65),
                critical_threshold=thresh_cfg.get("critical", 40),
            )
        except Exception as exc:
            log.debug("Decay prediction failed: %s", exc)
            decay_predictions = {}

        decaying_count = len(decay_predictions)

        if ci_mode:
            _run_ci(results, total_scanned)
            return

        render_summary(
            results, total_scanned, elapsed,
            repo_score=repo_score,
            repo_score_delta=repo_score_delta,
            since_ref=since_ref,
            since_count=since_count,
            ignored_count=ignored_count,
            decaying_count=decaying_count,
            lang_counts=lang_counts if lang_counts else None,
        )
        render_table(results, show_blame=include_blame, decay_predictions=decay_predictions or None)

        non_healthy = [m for m in results if m.status != "HEALTHY"]
        if non_healthy:
            render_footer(non_healthy, repo_path, show_blame=include_blame,
                          decay_predictions=decay_predictions or None)
        else:
            console.print(
                Panel(
                    f"[bold {C_GREEN}]  \u2705  All files look healthy. Great work![/]",
                    border_style=C_DIM_GREEN,
                )
            )

    except git.InvalidGitRepositoryError:
        from rich.markup import escape
        render_error(
            "Not a git repository",
            f"'{escape(str(repo_path))}' is not inside a git repository.\n"
            "Run deathbed from within a git repo, or pass --path to a repo directory.",
        )
        sys.exit(1)
    except git.NoSuchPathError:
        from rich.markup import escape
        render_error(
            "Path not found",
            f"The path '{escape(str(repo_path))}' does not exist.",
        )
        sys.exit(1)
    except KeyboardInterrupt:
        console.print(f"\n[dim {C_GREY}]Scan interrupted.[/]")
        sys.exit(0)
    except Exception as exc:
        render_error("Unexpected error", str(exc))
        sys.exit(1)


def _run_ci(results: list[FileMetrics], total_scanned: int) -> None:
    """CI mode: print minimal stats, exit 1 if any CRITICAL files."""
    import click
    critical = [m for m in results if m.status == "CRITICAL"]

    if critical:
        click.echo(
            f"deathbed: {len(critical)} CRITICAL file(s) found out of {total_scanned} scanned.",
            err=True,
        )
        for m in critical:
            click.echo(f"  💀 {m.path}  score={m.composite_score}  [{m.diagnosis}]", err=True)
        sys.exit(1)
    else:
        click.echo(
            f"deathbed: 0 CRITICAL files. {total_scanned} files scanned — all passing CI threshold."
        )


def run_watch_display(
    repo_path: Path,
    top: int,
    min_score: int | None,
    interval: int = 30,
) -> None:
    """Run the full display in a loop, clearing and re-rendering every interval seconds."""
    console.print(
        f"[bold {C_CRIMSON}]Watch mode — refreshing every {interval}s · Ctrl+C to stop[/]"
    )
    try:
        while True:
            console.clear()
            run_display(repo_path, top, min_score)
            console.print(
                f"[dim {C_GREY}]⟳ Next refresh in {interval}s · Ctrl+C to stop[/]"
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print(f"\n[dim {C_GREY}]Watch mode stopped.[/]")
        sys.exit(0)


def run_diff_display(
    repo_path: Path,
    ref: str,
    top: int,
    min_score: int | None,
) -> None:
    """Run the diff analysis and display the comparison table."""
    from ..analyzer import analyze_diff

    render_header()

    try:
        start = time.monotonic()
        total_scanned = 0

        with make_progress() as progress:
            task = progress.add_task(
                f"Comparing HEAD vs {ref}",
                total=None,
                color=C_CRIMSON,
                current_file="",
            )

            def on_progress(rel: str, idx: int, total: int) -> None:
                nonlocal total_scanned
                total_scanned = total
                progress.update(
                    task, total=total, completed=idx,
                    current_file=_truncate(rel, 60) if rel else "",
                )

            current, historical = analyze_diff(
                repo_path, ref,
                top=top, min_score=min_score,
                on_progress=on_progress,
            )

        elapsed = time.monotonic() - start  # noqa: F841

        if total_scanned == 0:
            render_error("No files found", "No analysable source files found.")
            return

        render_diff(current, historical, ref)

    except git.InvalidGitRepositoryError:
        render_error("Not a git repository", str(repo_path))
        sys.exit(1)
    except Exception as exc:
        render_error("Diff failed", str(exc))
        sys.exit(1)


def run_leaderboard_display(
    repo_path: Path,
    top: int,
    min_score: int | None,
) -> None:
    """Run blame-based analysis and display the team leaderboard."""
    from ..analyzer import analyze_leaderboard

    render_header()

    try:
        with make_progress() as progress:
            progress.add_task(
                "Building leaderboard",
                total=None,
                color=C_CRIMSON,
                current_file="",
            )
            authors = analyze_leaderboard(repo_path)

        render_leaderboard(authors)

    except git.InvalidGitRepositoryError:
        render_error("Not a git repository", str(repo_path))
        sys.exit(1)
    except Exception as exc:
        render_error("Leaderboard failed", str(exc))
        sys.exit(1)


def run_org_display(
    org_path: Path,
    top: int,
    min_score: int | None,
    output_format: str = "rich",
) -> None:
    """Scan all repos in org_path and show the org-wide health report."""
    from ..org import analyze_org

    render_org_header()

    try:
        with make_progress() as progress:
            progress.add_task(
                "Scanning repositories",
                total=None,
                color=C_CRIMSON,
                current_file="",
            )
            repos = analyze_org(org_path)

        if output_format == "json":
            import json

            import click
            payload = {
                "version": __version__,
                "org": str(org_path),
                "repos": [
                    {
                        "name":           r.name,
                        "path":           str(r.path),
                        "repo_score":     r.repo_score,
                        "grade":          r.grade,
                        "critical_count": r.critical_count,
                        "warning_count":  r.warning_count,
                        "file_count":     r.file_count,
                        "worst_file":     r.worst_file,
                        "worst_score":    r.worst_score,
                        "error":          r.error,
                    }
                    for r in repos
                ],
            }
            click.echo(json.dumps(payload, indent=2))
            return

        render_org_report(repos, org_path)

    except Exception as exc:
        render_error("Org scan failed", str(exc))
        sys.exit(1)


def run_plan_display(
    repo_path: Path,
    top: int,
    min_score: int | None,
    output_format: str = "rich",
) -> None:
    """Analyse the repo and render the refactoring plan."""
    from ..analyzer import analyze_repo
    from ..git_utils import get_repo_root, open_repo
    from ..planner import generate_plan

    repo_root = repo_path
    try:
        repo_root = get_repo_root(open_repo(repo_path))
    except Exception as exc:
        log.debug("Could not determine repo root: %s", exc)

    if output_format != "markdown":
        render_header()

    try:
        with make_progress() as progress:
            progress.add_task(
                "Analysing for refactor plan",
                total=None,
                color=C_CRIMSON,
                current_file="",
            )
            results = analyze_repo(repo_path, top=0, min_score=min_score)

        plan = generate_plan(results, repo_root)
        render_plan(plan, repo_root, output_format=output_format)

    except git.InvalidGitRepositoryError:
        render_error("Not a git repository", str(repo_path))
        sys.exit(1)
    except Exception as exc:
        render_error("Plan generation failed", str(exc))
        sys.exit(1)


def run_heatmap_display(
    repo_path: Path,
    top: int,
    min_score: int | None,
) -> None:
    """Analyse the repo and render the terminal treemap heatmap."""
    from ..analyzer import analyze_repo
    from ..heatmap import render_heatmap

    render_header()

    try:
        with make_progress() as progress:
            progress.add_task(
                "Scanning for heatmap",
                total=None,
                color=C_CRIMSON,
                current_file="",
            )
            results = analyze_repo(repo_path, top=0, min_score=min_score)

        if not results:
            render_error("No files found", "No analysable source files found.")
            return

        results_by_size = sorted(results, key=lambda m: m.lines, reverse=True)
        render_heatmap(results_by_size)

    except git.InvalidGitRepositoryError:
        render_error("Not a git repository", str(repo_path))
        sys.exit(1)
    except Exception as exc:
        render_error("Heatmap failed", str(exc))
        sys.exit(1)


# ── Panel import at module level for run_display ──────────────────────────────
from rich.panel import Panel  # noqa: E402
