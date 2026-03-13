"""
Rich output renderers: tables, panels, summaries, etc.
"""

from __future__ import annotations

import logging
from pathlib import Path

from rich import box
from rich.align import Align
from rich.markup import escape
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..scoring import FileMetrics, letter_grade
from .palette import (
    C_AMBER,
    C_CRIMSON,
    C_DIM,
    C_DIM_GREEN,
    C_GREEN,
    C_GREY,
    C_ORANGE,
    C_RED1,
    C_RED5,
    C_RED6,
    C_SKULL,
    C_WHITE,
    _health_icon,
    _human_days,
    _row_style,
    _score_bar,
    _score_color,
    _truncate,
    console,
)

log = logging.getLogger(__name__)


def render_summary(
    results: list[FileMetrics],
    total_scanned: int,
    elapsed: float,
    *,
    repo_score: int = 0,
    repo_score_delta: int | None = None,
    since_ref: str | None = None,
    since_count: int = 0,
    ignored_count: int = 0,
    decaying_count: int = 0,
    lang_counts: dict | None = None,
) -> None:
    """Display the post-scan summary stats panel."""
    critical      = sum(1 for m in results if m.status == "CRITICAL")
    warning       = sum(1 for m in results if m.status == "WARNING")
    fair          = sum(1 for m in results if m.status == "FAIR")
    healthy       = sum(1 for m in results if m.status == "HEALTHY")
    dead_code_ct  = sum(1 for m in results if m.dead_code_count > 0)
    sec_smell_ct  = sum(1 for m in results if m.has_security_smell)
    coupled_ct    = sum(1 for m in results if m.coupling_count >= 5)

    n_cols = 10
    show_decay = decaying_count > 0
    show_langs = bool(lang_counts)
    if show_decay:
        n_cols += 1
    if show_langs:
        n_cols += 1

    grid = Table.grid(expand=True, padding=(0, 2))
    for _ in range(n_cols):
        grid.add_column(justify="center")

    def _stat(icon: str, label: str, value: str, color: str) -> Text:
        t = Text(justify="center")
        t.append(f"{icon}\n", style=f"bold {color}")
        t.append(f"{value}\n", style=f"bold {color}")
        t.append(label, style=f"dim {C_GREY}")
        return t

    grade = letter_grade(repo_score)
    grade_color = _score_color(repo_score)
    delta_str = ""
    if repo_score_delta is not None:
        if repo_score_delta > 0:
            delta_str = f" \u25b2+{repo_score_delta}"
        elif repo_score_delta < 0:
            delta_str = f" \u25bc{repo_score_delta}"
    repo_score_t = Text(justify="center")
    repo_score_t.append("\U0001f4ca\n", style=f"bold {grade_color}")
    repo_score_t.append(f"{grade} ({repo_score}){delta_str}\n", style=f"bold {grade_color}")
    repo_score_t.append("repo score", style=f"dim {C_GREY}")

    row_cells = [
        _stat("\U0001f50d", "scanned",    str(total_scanned), C_WHITE),
        _stat("\U0001f480", "critical",   str(critical),      C_SKULL),
        _stat("\u26a0\ufe0f ", "warning", str(warning),       C_ORANGE),
        _stat("\U0001f321 ", "fair",      str(fair),           C_AMBER),
        _stat("\u2705", "healthy",        str(healthy),        C_GREEN),
        _stat("\U0001f9df", "dead code",  str(dead_code_ct),   C_ORANGE),
        _stat("\U0001f510", "sec smells", str(sec_smell_ct),   C_RED1),
        _stat("\U0001f517", "coupled",    str(coupled_ct),     C_ORANGE),
        _stat("\u23f1 ", "duration",      f"{elapsed:.2f}s",   C_GREY),
        repo_score_t,
    ]

    if show_decay:
        decay_t = Text(justify="center")
        decay_t.append("\U0001f4c9\n", style=f"bold {C_SKULL}")
        decay_t.append(f"{decaying_count}\n", style=f"bold {C_SKULL}")
        decay_t.append("decaying", style=f"dim {C_GREY}")
        row_cells.append(decay_t)

    if show_langs and lang_counts:
        top_langs = sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        langs_str = " ".join(f"{ext}:{n}" for ext, n in top_langs)
        langs_t = Text(justify="center")
        langs_t.append("\U0001f4c1\n", style=f"bold {C_AMBER}")
        langs_t.append(f"{langs_str}\n", style=f"bold {C_AMBER}")
        langs_t.append("languages", style=f"dim {C_GREY}")
        row_cells.append(langs_t)

    grid.add_row(*row_cells)

    subtitles: list[str] = []
    if since_ref:
        subtitles.append(f"PR mode \u2014 {since_count} file(s) changed since {since_ref}")
    if ignored_count > 0:
        subtitles.append(f"{ignored_count} file(s) ignored via .deathbedignore")
    _sep = " \u00b7 "
    panel_subtitle = f"[dim {C_GREY}]{_sep.join(subtitles)}[/]" if subtitles else None

    panel = Panel(
        Padding(grid, (1, 0)),
        title=f"[bold {C_CRIMSON}]  SCAN COMPLETE  [/]",
        subtitle=panel_subtitle,
        border_style=C_RED5,
        box=box.HEAVY,
    )
    console.print(panel)
    console.print()


def render_table(
    results: list[FileMetrics],
    show_blame: bool = False,
    decay_predictions: dict | None = None,
) -> None:
    """Render the main beautiful results table."""
    if not results:
        console.print(
            Panel(
                f"[bold {C_GREEN}]  No files matched the given thresholds.[/]",
                border_style=C_DIM_GREEN,
            )
        )
        return

    has_trend     = any(m.score_delta is not None for m in results)
    has_coupling  = any(m.coupling_count > 0 for m in results)
    has_decay_col = bool(decay_predictions)

    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style=C_RED6,
        header_style=f"bold {C_CRIMSON}",
        show_edge=True,
        show_lines=False,
        expand=True,
        title=f"[bold {C_CRIMSON}]FILE HEALTH REPORT[/]",
        title_style=f"bold {C_CRIMSON}",
        caption=f"[dim {C_GREY}]{len(results)} files · sorted worst-first[/]",
        caption_style=f"dim {C_GREY}",
        padding=(0, 1),
    )

    table.add_column("HLTH",    justify="center", width=7,  no_wrap=True)
    table.add_column("FILE",    justify="left",   ratio=2,  no_wrap=True)
    if has_trend:
        table.add_column("TREND",  justify="right",  width=7,  no_wrap=True)
    table.add_column("LINES",   justify="right",  width=6,  no_wrap=True)
    table.add_column("TOUCHED", justify="right",  width=10, no_wrap=True)
    table.add_column("CHURN",   justify="right",  width=5,  no_wrap=True)
    table.add_column("RECENT",  justify="right",  width=7,  no_wrap=True)
    table.add_column("AUTH",    justify="right",  width=4,  no_wrap=True)
    table.add_column("CPLX",    justify="right",  width=5,  no_wrap=True)
    if has_coupling:
        table.add_column("COUP",   justify="right",  width=5,  no_wrap=True)
    if has_decay_col:
        table.add_column("ETA",    justify="right",  width=7,  no_wrap=True)
    if show_blame:
        table.add_column("LAST AUTHOR", justify="left", width=14, no_wrap=True)
    table.add_column("DIAGNOSIS", justify="left", ratio=1,  no_wrap=True)

    _churn_arrow = {"up": ("▲", C_SKULL), "down": ("▼", C_DIM_GREEN), "stable": ("━", C_DIM)}

    for m in results:
        style = _row_style(m.status)

        icon     = _health_icon(m.status)
        health_t = Text(justify="center")
        health_t.append(f"{icon} ", style=style)
        health_t.append(str(m.composite_score), style=_score_color(m.composite_score))

        display_path = _truncate(m.path, 60)
        file_t = Text(escape(display_path), style=style, no_wrap=True)

        row_cells: list = [health_t, file_t]

        if has_trend:
            if m.score_delta is not None:
                if m.score_delta > 0:
                    trend_t = Text(f"▲ +{m.score_delta}", style=C_GREEN, justify="right")
                elif m.score_delta < 0:
                    trend_t = Text(f"▼ {m.score_delta}", style=C_SKULL, justify="right")
                else:
                    trend_t = Text("━  0", style=C_DIM, justify="right")
            else:
                trend_t = Text("━", style=C_DIM, justify="right")
            row_cells.append(trend_t)

        lines_color = (
            C_SKULL  if m.lines > 1000 else
            C_ORANGE if m.lines > 600  else
            C_AMBER  if m.lines > 300  else
            C_GREEN
        )
        lines_t = Text(f"{m.lines:,}", style=f"bold {lines_color}", justify="right")
        row_cells.append(lines_t)

        age_color = (
            C_SKULL  if m.days_since_commit > 730 else
            C_ORANGE if m.days_since_commit > 365 else
            C_AMBER  if m.days_since_commit > 180 else
            C_GREEN
        )
        age_t = Text(_human_days(m.days_since_commit), style=age_color, justify="right")
        row_cells.append(age_t)

        churn_color = (
            C_SKULL  if m.commit_count > 100 else
            C_ORANGE if m.commit_count > 50  else
            C_AMBER  if m.commit_count > 20  else
            C_GREEN
        )
        churn_t = Text(str(m.commit_count), style=churn_color, justify="right")
        row_cells.append(churn_t)

        recent_color = (
            C_SKULL  if m.recent_churn > 30 else
            C_ORANGE if m.recent_churn > 15 else
            C_AMBER  if m.recent_churn > 5  else
            C_GREEN
        )
        arrow, arrow_color = _churn_arrow.get(m.churn_trend, ("━", C_DIM))
        recent_t = Text(justify="right")
        recent_t.append(str(m.recent_churn), style=recent_color)
        recent_t.append(f" {arrow}", style=arrow_color)
        row_cells.append(recent_t)

        auth_color = (
            C_SKULL  if m.author_count > 10 else
            C_ORANGE if m.author_count > 6  else
            C_AMBER  if m.author_count > 3  else
            C_GREEN
        )
        auth_t = Text(str(m.author_count), style=auth_color, justify="right")
        row_cells.append(auth_t)

        if m.avg_complexity is not None:
            cx_val   = f"{m.avg_complexity:.1f}"
            cx_color = (
                C_SKULL  if m.avg_complexity > 15 else
                C_ORANGE if m.avg_complexity > 10 else
                C_AMBER  if m.avg_complexity > 5  else
                C_GREEN
            )
        else:
            cx_val   = "N/A"
            cx_color = C_DIM
        cx_t = Text(cx_val, style=cx_color, justify="right")
        row_cells.append(cx_t)

        if has_coupling:
            coup_color = (
                C_SKULL  if m.coupling_count > 15 else
                C_ORANGE if m.coupling_count > 10 else
                C_AMBER  if m.coupling_count > 5  else
                C_GREEN
            )
            coup_t = Text(str(m.coupling_count), style=coup_color, justify="right")
            row_cells.append(coup_t)

        if has_decay_col:
            pred = decay_predictions.get(m.path) if decay_predictions else None
            if pred is not None and pred.eta_days is not None:
                eta_color = C_SKULL if pred.eta_days <= 7 else C_ORANGE if pred.eta_days <= 14 else C_AMBER
                eta_t = Text(f"{pred.eta_days}d", style=eta_color, justify="right")
            else:
                eta_t = Text("—", style=C_DIM, justify="right")
            row_cells.append(eta_t)

        if show_blame:
            author_display = _truncate(m.last_author, 12) if m.last_author else "—"
            author_t = Text(author_display, style=C_GREY, justify="left")
            row_cells.append(author_t)

        diag_color = (
            C_SKULL     if m.status == "CRITICAL" else
            C_ORANGE    if m.status == "WARNING"  else
            C_AMBER     if m.status == "FAIR"     else
            C_DIM_GREEN
        )
        diag_t = Text(m.diagnosis, style=f"italic {diag_color}")
        row_cells.append(diag_t)

        table.add_row(*row_cells)

    console.print(table)
    console.print()


def render_footer(
    results: list[FileMetrics],
    repo_root: Path,
    show_blame: bool = False,
    decay_predictions: dict | None = None,
) -> None:
    """Render the Most Wanted, Most Coupled, Quick Wins, Tips, and Security Alerts panels."""
    if not results:
        return

    worst_decay = None
    if decay_predictions:
        worst_decay = decay_predictions.get(results[0].path)

    _render_most_wanted(results[0], show_blame=show_blame, decay=worst_decay)
    _render_most_coupled(results)
    _render_quick_wins(results)
    _render_tips(results)
    _render_security_alerts(results)
    if decay_predictions:
        _render_decay_panel(decay_predictions)


# ── Footer helpers ─────────────────────────────────────────────────────────────

def _render_most_wanted(worst: FileMetrics, show_blame: bool = False, decay: object = None) -> None:
    """Detailed breakdown of the single worst file."""
    score_table = Table.grid(expand=True, padding=(0, 1))
    score_table.add_column(justify="left",  width=13)
    score_table.add_column(justify="left",  width=28)
    score_table.add_column("·", justify="center", width=1)
    score_table.add_column(justify="left",  width=16)
    score_table.add_column(justify="left")

    def _row(metric: str, score: int, label: str, val: str) -> None:
        metric_t = Text(metric.upper(), style=f"dim {C_GREY}")
        bar_t    = _score_bar(score)
        dot_t    = Text("│", style=C_DIM)
        label_t  = Text(f"{label}:", style=f"dim {C_GREY}")
        val_t    = Text(val, style=f"bold {_score_color(score)}")
        score_table.add_row(metric_t, bar_t, dot_t, label_t, val_t)

    cx_display = (
        f"{worst.avg_complexity:.1f}"
        if worst.avg_complexity is not None
        else "N/A"
    )
    test_display = (
        ("✅ found" + (" (recent)" if worst.test_file_recent else ""))
        if worst.has_test_file
        else "✗  none found"
    )

    _row("size",      worst.size_score,         "Lines",        f"{worst.lines:,}")
    _row("age",       worst.age_score,           "Last commit",  _human_days(worst.days_since_commit))
    _row("churn",     worst.churn_score,         "Commits",      str(worst.commit_count))
    _row("recent",    worst.recent_churn_score,  "Last 90 days", str(worst.recent_churn))
    _row("complexity",worst.complexity_score,    "Complexity",   cx_display)
    _row("authors",   worst.author_score,        "Authors",      str(worst.author_count))
    _row("tests",     worst.test_score,          "Test file",    test_display)
    _row("coupling",  worst.coupling_score,      "Dependents",   str(worst.coupling_count))

    if worst.path.endswith(".py"):
        dead_display = (
            f"{worst.dead_code_count} unused symbol(s)"
            if worst.dead_code_count > 0
            else "none detected"
        )
        _row("dead code", worst.dead_code_score, "Vulture", dead_display)

    header = Text(justify="left")
    header.append(f"  {escape(worst.path)}", style=f"bold {C_WHITE}")

    if worst.sparkline:
        header.append("   ", style="")
        header.append(worst.sparkline, style=f"bold {_score_color(worst.composite_score)}")

    header.append("\n", style="")
    header.append(f"  \"{worst.diagnosis}\"", style=f"italic dim {C_GREY}")
    header.append(
        f"   {_health_icon(worst.status)} {worst.composite_score}/100",
        style=f"bold {_score_color(worst.composite_score)}",
    )

    if worst.importers:
        header.append("\n", style="")
        importer_list = ", ".join(_truncate(p, 25) for p in worst.importers[:3])
        extra = f" +{len(worst.importers) - 3} more" if len(worst.importers) > 3 else ""
        header.append(
            f"  imported by: {escape(importer_list)}{extra}",
            style=f"dim {C_ORANGE}",
        )

    if show_blame and worst.last_author:
        header.append("\n", style="")
        msg_display = _truncate(worst.last_commit_msg, 60) if worst.last_commit_msg else ""
        header.append(
            f"  last commit by: {escape(worst.last_author)}",
            style=f"dim {C_GREY}",
        )
        if msg_display:
            header.append(f" \u2014 \"{escape(msg_display)}\"", style=f"dim {C_GREY}")

    if decay is not None and getattr(decay, "eta_days", None) is not None:
        eta = decay.eta_days
        target = decay.target_threshold
        slope = decay.slope_per_week
        eta_color = C_SKULL if eta <= 7 else C_ORANGE if eta <= 14 else C_AMBER
        header.append("\n", style="")
        header.append(
            f"  \U0001f4c9 decay alert: score will cross {target} in ~{eta} day(s) "
            f"(slope: {slope:.1f} pts/week)",
            style=f"bold {eta_color}",
        )

    outer = Table.grid(expand=True, padding=(0, 0))
    outer.add_column()
    outer.add_row(header)
    outer.add_row(Text())
    outer.add_row(score_table)

    panel = Panel(
        outer,
        title=f"[bold {C_SKULL}]  🪦  MOST WANTED  [/]",
        border_style=C_RED5,
        box=box.HEAVY,
        padding=(0, 1),
    )
    console.print(panel)
    console.print()


def _render_most_coupled(results: list[FileMetrics]) -> None:
    """Show the top 3 most depended-upon files in the codebase."""
    sorted_by_coupling = sorted(results, key=lambda m: m.coupling_count, reverse=True)
    top3 = [m for m in sorted_by_coupling[:3] if m.coupling_count > 0]
    if not top3:
        return

    content = Text()
    for m in top3:
        coup_color = (
            C_SKULL  if m.coupling_count > 15 else
            C_ORANGE if m.coupling_count > 10 else
            C_AMBER  if m.coupling_count > 5  else
            C_GREEN
        )
        content.append("  🔗  ", style=f"bold {coup_color}")
        content.append(f"{_truncate(m.path, 38):<40}", style=C_WHITE)
        content.append(f"  {m.coupling_count} dependent(s)  ", style=f"bold {coup_color}")
        if m.importers:
            importer_list = ", ".join(_truncate(p, 20) for p in m.importers[:3])
            content.append(f"← {importer_list}", style=f"italic dim {C_GREY}")
        content.append("\n")

    panel = Panel(
        content,
        title=f"[bold {C_ORANGE}]  🔗  MOST COUPLED  [/]",
        subtitle=f"[dim {C_GREY}]most depended-upon files — highest change-blast radius[/]",
        border_style=C_ORANGE,
        box=box.HEAVY,
        padding=(0, 0),
    )
    console.print(panel)
    console.print()


def _render_quick_wins(results: list[FileMetrics]) -> None:
    """Show files that are almost healthy — small fixes, big gains."""
    wins = [
        m for m in results
        if m.status in ("WARNING", "FAIR") and m.composite_score >= 41
    ]
    wins = sorted(wins, key=lambda m: m.composite_score, reverse=True)[:5]

    if not wins:
        return

    content = Text()
    for m in wins:
        if m.has_security_smell:
            smells_short = ", ".join(m.security_smells[:2])
            suggestion = f"fix security smell ({smells_short})"
        else:
            individual = {
                "size":         m.size_score,
                "age":          m.age_score,
                "churn":        m.churn_score,
                "recent_churn": m.recent_churn_score,
                "complexity":   m.complexity_score,
                "authors":      m.author_score,
                "test":         m.test_score,
                "dead_code":    m.dead_code_score,
                "coupling":     m.coupling_score,
            }
            worst_metric = min(individual, key=individual.get)  # type: ignore[arg-type]
            suggestions = {
                "size":         "split into smaller modules",
                "age":          "review and update the code",
                "churn":        "stabilise the interface",
                "recent_churn": "investigate recent surge in activity",
                "complexity":   "reduce cyclomatic complexity",
                "authors":      "assign a clear owner",
                "test":         "add a test file",
                "dead_code":    "remove dead code (vulture detected unused symbols)",
                "coupling":     "reduce coupling — extract an interface or abstraction layer",
            }
            suggestion = suggestions.get(worst_metric, "review it")

        file_t = Text()
        file_t.append("  ●  ", style=f"bold {C_AMBER}")
        file_t.append(f"{_truncate(m.path, 38):<40}", style=C_WHITE)
        file_t.append(f"score: {m.composite_score:2d}  ", style=f"dim {C_GREY}")
        file_t.append(f"→ {suggestion}", style=f"italic {C_AMBER}")
        content.append_text(file_t)
        content.append("\n")

    panel = Panel(
        content,
        title=f"[bold {C_AMBER}]  ⚡  QUICK WINS  [/]",
        subtitle=f"[dim {C_GREY}]files closest to healthy[/]",
        border_style=C_AMBER,
        box=box.HEAVY,
        padding=(0, 0),
    )
    console.print(panel)
    console.print()


def _render_tips(results: list[FileMetrics]) -> None:
    """Multiple actionable tips based on the repo's dominant problems."""
    if not results:
        return

    tally: dict[str, int] = {
        "size": 0, "age": 0, "churn": 0,
        "recent_churn": 0, "complexity": 0, "authors": 0,
        "test": 0, "dead_code": 0, "coupling": 0,
    }
    for m in results:
        scores = {
            "size": m.size_score, "age": m.age_score, "churn": m.churn_score,
            "recent_churn": m.recent_churn_score,
            "complexity": m.complexity_score, "authors": m.author_score,
            "test": m.test_score, "dead_code": m.dead_code_score,
            "coupling": m.coupling_score,
        }
        worst = min(scores, key=scores.get)  # type: ignore[arg-type]
        tally[worst] = tally.get(worst, 0) + 1

    tips = {
        "recent_churn": (
            "🔥  {n} files have high recent activity (last 90 days). "
            "A sudden surge in commits signals an unstable hotspot. "
            "Consider a targeted design review before the churn compounds further."
        ),
        "size": (
            "📏  {n} files are too large. "
            "Apply the Single Responsibility Principle — "
            "aim for files under 300 lines by splitting concerns into separate modules."
        ),
        "age": (
            "🕰   {n} files haven't been touched in over a year. "
            "Schedule a codebase archaeology session — "
            "delete dead code, add comments, or rewrite the worst offenders."
        ),
        "churn": (
            "🔄  {n} files are high-churn. "
            "High churn signals an unstable abstraction. "
            "Consider a design review to stabilise the interface before it entangles more code."
        ),
        "complexity": (
            "🧠  {n} files have critical cyclomatic complexity. "
            "Break large functions into smaller pure helpers. "
            "Aim for an average complexity below 5 per function."
        ),
        "authors": (
            "👥  {n} files have diffused ownership. "
            "Assign a primary owner for each critical file using CODEOWNERS. "
            "No owner means nobody fixes it when it breaks."
        ),
        "test": (
            "🧪  {n} files have no corresponding test file. "
            "Start with the highest-churn files — they change most and need tests most. "
            "Even one happy-path test is infinitely better than none."
        ),
        "dead_code": (
            "🧟  {n} files contain dead code detected by vulture. "
            "Unused functions and classes add cognitive load and hide real bugs. "
            "Run `vulture <file>` on each and remove anything above 80% confidence."
        ),
        "coupling": (
            "🔗  {n} files are highly coupled — many other modules depend on them. "
            "Any change ripples across the codebase. "
            "Introduce interfaces or abstract base classes to reduce direct coupling."
        ),
    }

    sorted_patterns = sorted(
        [(k, v) for k, v in tally.items() if v > 0],
        key=lambda x: x[1],
        reverse=True,
    )[:3]

    if not sorted_patterns:
        return

    content_parts: list[str] = []
    for pattern, count in sorted_patterns:
        tmpl = tips.get(pattern)
        if tmpl:
            content_parts.append(tmpl.replace("{n}", str(count)))

    full_text = "\n\n".join(content_parts)

    panel = Panel(
        f"[{C_WHITE}]{full_text}[/]",
        title=f"[bold {C_AMBER}]  💡  PATTERN DETECTED  [/]",
        border_style=C_AMBER,
        box=box.ROUNDED,
        padding=(0, 2),
    )
    console.print(panel)
    console.print()


def _render_security_alerts(results: list[FileMetrics]) -> None:
    """Show a red SECURITY ALERTS panel if any files have security smells."""
    security_files = [m for m in results if m.has_security_smell]
    if not security_files:
        return

    content = Text()
    for m in security_files[:15]:
        smells_str = ", ".join(m.security_smells[:3])
        file_t = Text()
        file_t.append("  🔐  ", style=f"bold {C_RED1}")
        file_t.append(f"{_truncate(m.path, 38):<40}", style=C_WHITE)
        file_t.append(f"  {smells_str}", style=f"italic {C_ORANGE}")
        content.append_text(file_t)
        content.append("\n")

    if len(security_files) > 15:
        extra = len(security_files) - 15
        content.append(f"\n  … and {extra} more file(s)", style=f"dim {C_GREY}")

    panel = Panel(
        content,
        title=f"[bold {C_RED1}]  🔐  SECURITY ALERTS  [/]",
        subtitle=f"[dim {C_GREY}]{len(security_files)} file(s) with dangerous patterns[/]",
        border_style=C_RED5,
        box=box.HEAVY,
        padding=(0, 0),
    )
    console.print(panel)
    console.print()


def _render_decay_panel(decay_predictions: dict) -> None:
    """Show a decay forecast panel for files trending toward critical thresholds."""
    if not decay_predictions:
        return

    sorted_preds = sorted(
        [p for p in decay_predictions.values() if p.eta_days is not None],
        key=lambda p: (p.eta_days or 9999),
    )[:10]

    if not sorted_preds:
        return

    content = Text()
    for pred in sorted_preds:
        eta_color = C_SKULL if pred.eta_days <= 7 else C_ORANGE if pred.eta_days <= 14 else C_AMBER
        content.append("  \U0001f4c9  ", style=f"bold {eta_color}")
        content.append(f"{_truncate(pred.file_path, 38):<40}", style=C_WHITE)
        content.append(f"  score: {pred.current_score:3d}  ", style=f"dim {C_GREY}")
        content.append(f"ETA: ~{pred.eta_days}d  ", style=f"bold {eta_color}")
        content.append(
            f"\u2192 will cross {pred.target_threshold} ({pred.slope_per_week:.1f} pts/week)",
            style=f"italic {C_AMBER}",
        )
        content.append("\n")

    panel = Panel(
        content,
        title=f"[bold {C_SKULL}]  \U0001f4c9  DECAY FORECAST  [/]",
        subtitle=f"[dim {C_GREY}]{len(sorted_preds)} file(s) trending toward critical thresholds[/]",
        border_style=C_RED5,
        box=box.HEAVY,
        padding=(0, 0),
    )
    console.print(panel)
    console.print()


# ── Refactor plan renderer ─────────────────────────────────────────────────────

def render_plan(plan: dict, repo_root: Path, output_format: str = "rich") -> None:
    """Render the refactoring roadmap — rich terminal view or markdown."""
    if output_format == "markdown":
        import click

        from ..planner import format_plan_markdown
        click.echo(format_plan_markdown(plan, repo_root))
        return
    _render_plan_rich(plan)


def _render_plan_rich(plan: dict) -> None:
    """Render the plan as styled amber Rich panels with sprint dividers."""
    sprint_configs = [
        ("sprint1", "🔴  SPRINT 1 — DO THIS WEEK",    "CRITICAL",  C_SKULL),
        ("sprint2", "🟡  SPRINT 2 — DO THIS MONTH",   "WARNING",   C_ORANGE),
        ("sprint3", "🟢  SPRINT 3 — DO THIS QUARTER", "FAIR",      C_AMBER),
    ]

    all_empty = all(not plan.get(k, []) for k, _, _, _ in sprint_configs)
    if all_empty:
        console.print(
            Panel(
                f"[bold {C_GREEN}]  ✅  No refactoring needed — all files are healthy![/]",
                title=f"[bold {C_AMBER}]  📋  REFACTOR PLAN  [/]",
                border_style=C_AMBER,
                box=box.HEAVY,
            )
        )
        return

    for sprint_key, sprint_title, sprint_status, sprint_color in sprint_configs:
        items = plan.get(sprint_key, [])
        if not items:
            continue

        content = Text()
        for item in items:
            effort_color = {
                "Small": C_GREEN, "Medium": C_AMBER, "Large": C_SKULL
            }.get(item["effort"], C_GREY)

            content.append("\n  ●  ", style=f"bold {sprint_color}")
            content.append(f"{_truncate(item['file'], 42):<44}", style=C_WHITE)
            content.append(f"score: {item['score']:2d}  ", style=f"dim {C_GREY}")
            content.append(f"[{item['effort']}]", style=f"bold {effort_color}")
            content.append(f"\n     {escape(item['action'])}\n", style=f"italic {C_AMBER}")

        panel = Panel(
            content,
            title=f"[bold {C_AMBER}]  {sprint_title}  [/]",
            subtitle=f"[dim {C_GREY}]{len(items)} file(s) · {sprint_status}[/]",
            border_style=C_AMBER,
            box=box.HEAVY,
            padding=(0, 0),
        )
        console.print(panel)
        console.print()


# ── Org-wide report renderer ───────────────────────────────────────────────────

def render_org_report(repos: list, org_path: Path) -> None:
    """Render the org-wide health table, sorted worst-first."""
    from ..org import org_combined_score
    from ..scoring import letter_grade

    if not repos:
        console.print(Panel(
            f"[bold {C_AMBER}]  No git repositories found in {escape(str(org_path))}[/]",
            border_style=C_AMBER,
        ))
        return

    org_score = org_combined_score(repos)
    org_grade = letter_grade(org_score)
    grade_color = _score_color(org_score)

    org_summary = Text(justify="center")
    org_summary.append("ORG SCORE  ", style=f"dim {C_GREY}")
    org_summary.append(f"{org_grade} ({org_score})", style=f"bold {grade_color}")
    org_summary.append(f"  ·  {len(repos)} repositories scanned", style=f"dim {C_GREY}")
    from rich.padding import Padding as _Padding
    console.print(
        Panel(
            _Padding(org_summary, (0, 2)),
            border_style=grade_color,
            box=box.HEAVY,
        )
    )
    console.print()

    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style=C_RED6,
        header_style=f"bold {C_CRIMSON}",
        show_edge=True,
        expand=True,
        title=f"[bold {C_CRIMSON}]ORG HEALTH REPORT[/]",
        title_style=f"bold {C_CRIMSON}",
        caption=f"[dim {C_GREY}]{len(repos)} repos · sorted worst-first[/]",
        caption_style=f"dim {C_GREY}",
        padding=(0, 1),
    )

    table.add_column("GRADE",    justify="center", width=6,  no_wrap=True)
    table.add_column("REPO",     justify="left",   ratio=2,  no_wrap=True)
    table.add_column("SCORE",    justify="center", width=7,  no_wrap=True)
    table.add_column("CRITICAL", justify="right",  width=8,  no_wrap=True)
    table.add_column("WARNING",  justify="right",  width=7,  no_wrap=True)
    table.add_column("FILES",    justify="right",  width=5,  no_wrap=True)
    table.add_column("WORST FILE",       justify="left",  ratio=2, no_wrap=True)
    table.add_column("WORST SCORE",      justify="center", width=11, no_wrap=True)

    for r in repos:
        if r.error:
            table.add_row(
                Text("?", style=C_DIM),
                Text(escape(r.name), style=C_GREY),
                Text("—",   style=C_DIM, justify="center"),
                Text("—",   style=C_DIM, justify="right"),
                Text("—",   style=C_DIM, justify="right"),
                Text("—",   style=C_DIM, justify="right"),
                Text(f"error: {_truncate(r.error, 40)}", style=f"italic {C_GREY}"),
                Text("—",   style=C_DIM),
            )
            continue

        repo_color = _score_color(r.repo_score)
        crit_color = C_SKULL  if r.critical_count > 0 else C_DIM_GREEN
        warn_color = C_ORANGE if r.warning_count  > 0 else C_DIM

        table.add_row(
            Text(r.grade,             style=f"bold {repo_color}", justify="center"),
            Text(escape(r.name),      style=f"bold {C_WHITE}"),
            Text(str(r.repo_score),   style=repo_color, justify="center"),
            Text(str(r.critical_count), style=crit_color, justify="right"),
            Text(str(r.warning_count),  style=warn_color, justify="right"),
            Text(str(r.file_count),   style=C_GREY, justify="right"),
            Text(_truncate(r.worst_file, 40) if r.worst_file else "—",
                 style=C_GREY),
            Text(str(r.worst_score) if r.worst_file else "—",
                 style=_score_color(r.worst_score) if r.worst_file else C_DIM,
                 justify="center"),
        )

    console.print(table)
    console.print()


# ── Diff renderer ──────────────────────────────────────────────────────────────

def render_diff(
    current: list[FileMetrics],
    historical: list[FileMetrics],
    ref: str,
) -> None:
    """Show score changes between the current state and a historical ref."""
    hist_map = {m.path: m for m in historical}

    entries: list[tuple[FileMetrics, FileMetrics, int]] = []
    for m in current:
        if m.path in hist_map:
            h     = hist_map[m.path]
            delta = m.composite_score - h.composite_score
            entries.append((m, h, delta))

    entries.sort(key=lambda x: x[2])

    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style=C_RED6,
        header_style=f"bold {C_CRIMSON}",
        show_edge=True,
        expand=True,
        title=f"[bold {C_CRIMSON}]HEALTH DIFF: HEAD vs {escape(ref)}[/]",
        caption=f"[dim {C_GREY}]▼ worsened · ▲ improved · ━ unchanged[/]",
        padding=(0, 1),
    )
    table.add_column("FILE",   justify="left",   ratio=2, no_wrap=True)
    table.add_column("BEFORE", justify="center", width=8, no_wrap=True)
    table.add_column("NOW",    justify="center", width=8, no_wrap=True)
    table.add_column("CHANGE", justify="center", width=8, no_wrap=True)
    table.add_column("STATUS", justify="left",   width=9, no_wrap=True)

    improved = worsened = unchanged = 0

    for m, h, delta in entries:
        if delta > 0:
            arrow, arrow_color = "▲", C_GREEN
            improved += 1
        elif delta < 0:
            arrow, arrow_color = "▼", C_SKULL
            worsened += 1
        else:
            arrow, arrow_color = "━", C_GREY
            unchanged += 1

        file_t   = Text(_truncate(m.path, 60), style=_row_style(m.status))
        before_t = Text(str(h.composite_score), style=_score_color(h.composite_score), justify="center")
        now_t    = Text(str(m.composite_score), style=_score_color(m.composite_score),  justify="center")
        change_t = Text(f"{arrow} {abs(delta):+d}" if delta != 0 else "━  0", style=arrow_color, justify="center")

        if m.status != h.status:
            status_t = Text(f"{h.status}→{m.status}", style=_row_style(m.status))
        else:
            status_t = Text(m.status, style=_row_style(m.status))

        table.add_row(file_t, before_t, now_t, change_t, status_t)

    console.print(table)
    console.print()

    summary = Text(justify="center")
    summary.append(f"▲ {improved} improved  ", style=C_GREEN)
    summary.append(f"▼ {worsened} worsened  ", style=C_SKULL)
    summary.append(f"━ {unchanged} unchanged",  style=C_GREY)
    console.print(Align(summary, align="center"))
    console.print()


# ── Markdown renderer ──────────────────────────────────────────────────────────

def render_markdown(results: list[FileMetrics]) -> None:
    """Output a GitHub-Flavored Markdown table to stdout."""
    import click

    headers = ["FILE", "SCORE", "STATUS", "LINES", "LAST TOUCHED", "CHURN", "AUTHORS", "COUPLING", "DIAGNOSIS"]
    click.echo("| " + " | ".join(headers) + " |")
    click.echo("| " + " | ".join(["---"] * len(headers)) + " |")
    for m in results:
        row = [
            f"`{m.path}`",
            str(m.composite_score),
            m.status,
            str(m.lines),
            _human_days(m.days_since_commit),
            str(m.commit_count),
            str(m.author_count),
            str(m.coupling_count),
            m.diagnosis,
        ]
        click.echo("| " + " | ".join(row) + " |")


# ── Leaderboard renderer ───────────────────────────────────────────────────────

def render_leaderboard(authors: list) -> None:
    """Render the team leaderboard table (authors sorted by most-at-risk first)."""
    if not authors:
        console.print(
            Panel(
                f"[bold {C_AMBER}]  No author data found. "
                f"Try running with --blame in a repo with git history.[/]",
                border_style=C_AMBER,
            )
        )
        return

    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style=C_RED6,
        header_style=f"bold {C_CRIMSON}",
        show_edge=True,
        expand=True,
        title=f"[bold {C_CRIMSON}]TEAM LEADERBOARD[/]",
        title_style=f"bold {C_CRIMSON}",
        caption=f"[dim {C_GREY}]sorted by most files needing support — framed as opportunity, not blame[/]",
        caption_style=f"dim {C_GREY}",
        padding=(0, 1),
    )
    table.add_column("AUTHOR",    justify="left",   ratio=1,  no_wrap=True)
    table.add_column("FILES",     justify="right",  width=6,  no_wrap=True)
    table.add_column("AVG SCORE", justify="center", width=10, no_wrap=True)
    table.add_column("CRITICAL",  justify="right",  width=8,  no_wrap=True)
    table.add_column("WARNING",   justify="right",  width=7,  no_wrap=True)
    table.add_column("GRADE",     justify="center", width=6,  no_wrap=True)

    for a in authors:
        grade_color = _score_color(int(a.avg_score))
        crit_color  = C_SKULL  if a.critical_count > 0 else C_DIM_GREEN
        warn_color  = C_ORANGE if a.warning_count  > 0 else C_DIM

        table.add_row(
            Text(escape(a.author),           style=C_WHITE),
            Text(str(a.files_owned),         style=C_GREY,        justify="right"),
            Text(f"{a.avg_score:.0f}",       style=grade_color,   justify="center"),
            Text(str(a.critical_count),      style=crit_color,    justify="right"),
            Text(str(a.warning_count),       style=warn_color,    justify="right"),
            Text(a.grade,                    style=f"bold {grade_color}", justify="center"),
        )

    console.print(table)
    console.print()

    note = Text(justify="center")
    note.append(
        "💡  Use this table to prioritise code review support, not to rank developers.",
        style=f"italic dim {C_GREY}",
    )
    console.print(Align(note, align="center"))
    console.print()
