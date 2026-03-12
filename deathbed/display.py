"""
display.py — the crown jewel of deathbed.

Every panel, color, and layout decision lives here.
Rich is used to its absolute fullest.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

# ── Windows UTF-8 fix ─────────────────────────────────────────────────────────
# Must happen before the Console is created so Rich sees the right encoding.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

import git
from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.markup import escape
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text

from .scoring import FileMetrics, letter_grade

# ── Global console ─────────────────────────────────────────────────────────────
console = Console(highlight=False, legacy_windows=False)

# ── Palette ───────────────────────────────────────────────────────────────────

C_CRIMSON   = "rgb(220,20,60)"
C_RED1      = "rgb(255,69,58)"
C_RED2      = "rgb(240,50,40)"
C_RED3      = "rgb(220,30,20)"
C_RED4      = "rgb(200,15,10)"
C_RED5      = "rgb(178,0,0)"
C_RED6      = "rgb(139,0,0)"
C_ORANGE    = "rgb(255,140,0)"
C_AMBER     = "rgb(255,191,0)"
C_GREEN     = "rgb(0,200,80)"
C_DIM_GREEN = "rgb(0,120,50)"
C_GREY      = "rgb(120,120,120)"
C_WHITE     = "rgb(230,230,230)"
C_DIM       = "rgb(80,80,80)"
C_SKULL     = "rgb(255,69,58)"

ROW_CRITICAL = Style(color="rgb(255,100,100)", bold=True)
ROW_WARNING  = Style(color="rgb(255,180,50)",  bold=True)
ROW_FAIR     = Style(color="rgb(230,215,80)")
ROW_HEALTHY  = Style(color="rgb(100,210,130)", dim=True)

# ── ASCII art logo ─────────────────────────────────────────────────────────────

_LOGO_LINES = [
    "██████╗ ███████╗ █████╗ ████████╗██╗  ██╗██████╗ ███████╗██████╗ ",
    "██╔══██╗██╔════╝██╔══██╗╚══██╔══╝██║  ██║██╔══██╗██╔════╝██╔══██╗",
    "██║  ██║█████╗  ███████║   ██║   ███████║██████╔╝█████╗  ██║  ██║",
    "██║  ██║██╔══╝  ██╔══██║   ██║   ██╔══██║██╔══██╗██╔══╝  ██║  ██║",
    "██████╔╝███████╗██║  ██║   ██║   ██║  ██║██████╔╝███████╗██████╔╝",
    "╚═════╝ ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═════╝ ╚══════╝╚═════╝ ",
]

_LOGO_COLORS = [C_RED1, C_RED2, C_RED3, C_RED4, C_RED5, C_RED6]

_TAGLINE = "every codebase has files that are dying.  find them."


def _build_logo() -> Text:
    logo = Text(justify="center")
    for i, (line, color) in enumerate(zip(_LOGO_LINES, _LOGO_COLORS)):
        if i > 0:
            logo.append("\n")
        logo.append(line, style=f"bold {color}")
    return logo


# ── Small helpers ──────────────────────────────────────────────────────────────

def _health_icon(status: str) -> str:
    return {"CRITICAL": "💀", "WARNING": "⚠️ ", "FAIR": "🌡 ", "HEALTHY": "✅"}.get(status, "·")


def _row_style(status: str) -> Style:
    return {
        "CRITICAL": ROW_CRITICAL,
        "WARNING":  ROW_WARNING,
        "FAIR":     ROW_FAIR,
        "HEALTHY":  ROW_HEALTHY,
    }.get(status, ROW_HEALTHY)


def _score_color(score: int) -> str:
    if score >= 80:
        return C_GREEN
    if score >= 60:
        return C_AMBER
    if score >= 40:
        return C_ORANGE
    return C_SKULL


def _score_bar(score: int, width: int = 18) -> Text:
    """A compact coloured block progress bar for a 0-100 score."""
    filled = round(score / 100 * width)
    empty  = width - filled
    color  = _score_color(score)
    bar = Text()
    bar.append("█" * filled, style=f"bold {color}")
    bar.append("░" * empty,  style=C_DIM)
    bar.append(f"  {score:3d}", style=color)
    return bar


def _human_days(days: int) -> str:
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days}d ago"
    if days < 30:
        weeks = days // 7
        return f"{weeks}w ago"
    if days < 365:
        months = days // 30
        return f"{months}mo ago"
    years    = days // 365
    leftover = (days % 365) // 30
    return f"{years}y {leftover}mo ago" if leftover else f"{years}y ago"


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else "…" + s[-(n - 1):]


# ── Public render functions ────────────────────────────────────────────────────

def render_header() -> None:
    """Print the big crimson DEATHBED logo + tagline."""
    console.print()
    logo = _build_logo()
    console.print(Align(logo, align="center"))
    console.print()
    tagline = Text(_TAGLINE, style=f"italic dim {C_GREY}", justify="center")
    console.print(Align(tagline, align="center"))
    console.print()


def render_org_header() -> None:
    """Print the DEATHBED logo with an ORG SCAN subtitle."""
    console.print()
    logo = _build_logo()
    console.print(Align(logo, align="center"))
    console.print()
    org_rule = Rule(
        title=f"[bold {C_RED1}]  🏢  O R G   S C A N  [/]",
        style=C_RED5,
        characters="═",
    )
    console.print(org_rule)
    console.print()
    tagline = Text(
        "scanning your entire organisation — one repo at a time.",
        style=f"italic dim {C_GREY}",
        justify="center",
    )
    console.print(Align(tagline, align="center"))
    console.print()


def render_error(title: str, message: str) -> None:
    """Display a styled error panel — no raw tracebacks ever."""
    panel = Panel(
        f"[bold {C_RED1}]{escape(message)}[/]",
        title=f"[bold {C_RED1}]✗  {escape(title)}[/]",
        border_style=C_RED5,
        padding=(1, 2),
    )
    console.print(panel)


def make_progress() -> Progress:
    """Return a beautiful progress bar for the scanning phase."""
    return Progress(
        SpinnerColumn(spinner_name="dots2", style=f"bold {C_CRIMSON}"),
        TextColumn(
            "[bold {task.fields[color]}]{task.description}[/]",
            justify="left",
        ),
        BarColumn(
            bar_width=36,
            style=C_RED6,
            complete_style=C_CRIMSON,
            finished_style=C_DIM_GREEN,
        ),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TextColumn("[dim]{task.fields[current_file]}[/]", justify="left"),
        console=console,
        transient=True,
    )


def render_summary(
    results: list[FileMetrics],
    total_scanned: int,
    elapsed: float,
    *,
    repo_score: int = 0,
    repo_score_delta: Optional[int] = None,
    since_ref: Optional[str] = None,
    since_count: int = 0,
    ignored_count: int = 0,
) -> None:
    """Display the post-scan summary stats panel."""
    critical      = sum(1 for m in results if m.status == "CRITICAL")
    warning       = sum(1 for m in results if m.status == "WARNING")
    fair          = sum(1 for m in results if m.status == "FAIR")
    healthy       = sum(1 for m in results if m.status == "HEALTHY")
    dead_code_ct  = sum(1 for m in results if m.dead_code_count > 0)
    sec_smell_ct  = sum(1 for m in results if m.has_security_smell)
    coupled_ct    = sum(1 for m in results if m.coupling_count >= 5)

    grid = Table.grid(expand=True, padding=(0, 2))
    for _ in range(10):
        grid.add_column(justify="center")

    def _stat(icon: str, label: str, value: str, color: str) -> Text:
        t = Text(justify="center")
        t.append(f"{icon}\n", style=f"bold {color}")
        t.append(f"{value}\n", style=f"bold {color}")
        t.append(label, style=f"dim {C_GREY}")
        return t

    # Repo score cell with grade and optional delta
    grade = letter_grade(repo_score)
    grade_color = _score_color(repo_score)
    delta_str = ""
    if repo_score_delta is not None:
        if repo_score_delta > 0:
            delta_str = f" ▲+{repo_score_delta}"
        elif repo_score_delta < 0:
            delta_str = f" ▼{repo_score_delta}"
    repo_score_t = Text(justify="center")
    repo_score_t.append("📊\n", style=f"bold {grade_color}")
    repo_score_t.append(f"{grade} ({repo_score}){delta_str}\n", style=f"bold {grade_color}")
    repo_score_t.append("repo score", style=f"dim {C_GREY}")

    grid.add_row(
        _stat("🔍", "scanned",    str(total_scanned), C_WHITE),
        _stat("💀", "critical",   str(critical),      C_SKULL),
        _stat("⚠️ ", "warning",   str(warning),       C_ORANGE),
        _stat("🌡 ", "fair",      str(fair),           C_AMBER),
        _stat("✅", "healthy",    str(healthy),        C_GREEN),
        _stat("🧟", "dead code",  str(dead_code_ct),   C_ORANGE),
        _stat("🔐", "sec smells", str(sec_smell_ct),   C_RED1),
        _stat("🔗", "coupled",    str(coupled_ct),     C_ORANGE),
        _stat("⏱ ", "duration",  f"{elapsed:.2f}s",   C_GREY),
        repo_score_t,
    )

    subtitles: list[str] = []
    if since_ref:
        subtitles.append(f"PR mode — {since_count} file(s) changed since {since_ref}")
    if ignored_count > 0:
        subtitles.append(f"{ignored_count} file(s) ignored via .deathbedignore")
    panel_subtitle = f"[dim {C_GREY}]{' · '.join(subtitles)}[/]" if subtitles else None

    panel = Panel(
        Padding(grid, (1, 0)),
        title=f"[bold {C_CRIMSON}]  SCAN COMPLETE  [/]",
        subtitle=panel_subtitle,
        border_style=C_RED5,
        box=box.HEAVY,
    )
    console.print(panel)
    console.print()


def render_table(results: list[FileMetrics], show_blame: bool = False) -> None:
    """Render the main beautiful results table."""
    if not results:
        console.print(
            Panel(
                f"[bold {C_GREEN}]  No files matched the given thresholds.[/]",
                border_style=C_DIM_GREEN,
            )
        )
        return

    has_trend    = any(m.score_delta is not None for m in results)
    has_coupling = any(m.coupling_count > 0 for m in results)

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
    if show_blame:
        table.add_column("LAST AUTHOR", justify="left", width=14, no_wrap=True)
    table.add_column("DIAGNOSIS", justify="left", ratio=1,  no_wrap=True)

    _churn_arrow = {"up": ("▲", C_SKULL), "down": ("▼", C_DIM_GREEN), "stable": ("━", C_DIM)}

    for m in results:
        style = _row_style(m.status)

        # HEALTH cell
        icon     = _health_icon(m.status)
        health_t = Text(justify="center")
        health_t.append(f"{icon} ", style=style)
        health_t.append(str(m.composite_score), style=Style(bold=True, color=_score_color(m.composite_score)))

        # FILE cell
        display_path = _truncate(m.path, 60)
        file_t = Text(escape(display_path), style=style, no_wrap=True)

        row_cells: list = [health_t, file_t]

        # TREND cell
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

        # LINES cell
        lines_color = (
            C_SKULL  if m.lines > 1000 else
            C_ORANGE if m.lines > 600  else
            C_AMBER  if m.lines > 300  else
            C_GREEN
        )
        lines_t = Text(f"{m.lines:,}", style=f"bold {lines_color}", justify="right")
        row_cells.append(lines_t)

        # LAST TOUCHED cell
        age_color = (
            C_SKULL  if m.days_since_commit > 730 else
            C_ORANGE if m.days_since_commit > 365 else
            C_AMBER  if m.days_since_commit > 180 else
            C_GREEN
        )
        age_t = Text(_human_days(m.days_since_commit), style=age_color, justify="right")
        row_cells.append(age_t)

        # CHURN cell
        churn_color = (
            C_SKULL  if m.commit_count > 100 else
            C_ORANGE if m.commit_count > 50  else
            C_AMBER  if m.commit_count > 20  else
            C_GREEN
        )
        churn_t = Text(str(m.commit_count), style=churn_color, justify="right")
        row_cells.append(churn_t)

        # RECENT CHURN cell
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

        # AUTHORS cell
        auth_color = (
            C_SKULL  if m.author_count > 10 else
            C_ORANGE if m.author_count > 6  else
            C_AMBER  if m.author_count > 3  else
            C_GREEN
        )
        auth_t = Text(str(m.author_count), style=auth_color, justify="right")
        row_cells.append(auth_t)

        # COMPLEXITY cell
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

        # COUPLING cell
        if has_coupling:
            coup_color = (
                C_SKULL  if m.coupling_count > 15 else
                C_ORANGE if m.coupling_count > 10 else
                C_AMBER  if m.coupling_count > 5  else
                C_GREEN
            )
            coup_t = Text(str(m.coupling_count), style=coup_color, justify="right")
            row_cells.append(coup_t)

        # LAST AUTHOR cell (blame mode)
        if show_blame:
            author_display = _truncate(m.last_author, 12) if m.last_author else "—"
            author_t = Text(author_display, style=C_GREY, justify="left")
            row_cells.append(author_t)

        # DIAGNOSIS cell
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
) -> None:
    """Render the Most Wanted, Most Coupled, Quick Wins, Tips, and Security Alerts panels."""
    if not results:
        return

    _render_most_wanted(results[0], show_blame=show_blame)
    _render_most_coupled(results)
    _render_quick_wins(results)
    _render_tips(results)
    _render_security_alerts(results)


# ── Footer helpers ─────────────────────────────────────────────────────────────

def _render_most_wanted(worst: FileMetrics, show_blame: bool = False) -> None:
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

    # Dead code row (only meaningful for Python files)
    if worst.path.endswith(".py"):
        dead_display = (
            f"{worst.dead_code_count} unused symbol(s)"
            if worst.dead_code_count > 0
            else "none detected"
        )
        _row("dead code", worst.dead_code_score, "Vulture", dead_display)

    # Build header
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

    # Importers line (if coupling data available)
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
            header.append(f" — \"{escape(msg_display)}\"", style=f"dim {C_GREY}")

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


# ── Refactor plan renderer ─────────────────────────────────────────────────────

def render_plan(plan: dict, repo_root: Path, output_format: str = "rich") -> None:
    """Render the refactoring roadmap — rich terminal view or markdown."""
    if output_format == "markdown":
        import click
        from .planner import format_plan_markdown
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
    from .org import org_combined_score
    from .scoring import letter_grade

    if not repos:
        console.print(Panel(
            f"[bold {C_AMBER}]  No git repositories found in {escape(str(org_path))}[/]",
            border_style=C_AMBER,
        ))
        return

    org_score = org_combined_score(repos)
    org_grade = letter_grade(org_score)
    grade_color = _score_color(org_score)

    # Org score summary
    org_summary = Text(justify="center")
    org_summary.append("ORG SCORE  ", style=f"dim {C_GREY}")
    org_summary.append(f"{org_grade} ({org_score})", style=f"bold {grade_color}")
    org_summary.append(f"  ·  {len(repos)} repositories scanned", style=f"dim {C_GREY}")
    console.print(
        Panel(
            Padding(org_summary, (0, 2)),
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


# ── Main entry points ──────────────────────────────────────────────────────────

def run_display(
    repo_path: Path,
    top: int,
    min_score: Optional[int],
    ci_mode: bool = False,
    since_ref: Optional[str] = None,
    include_blame: bool = False,
) -> None:
    """Full deathbed run: header → scan → table → footer."""
    from .analyzer import analyze_repo
    from .history import enrich_with_history, get_repo_score_delta, save_scan
    from .scoring import compute_repo_score

    if not ci_mode:
        render_header()

    repo_root = repo_path
    try:
        from .git_utils import open_repo as _or, get_repo_root as _grr
        repo_root = _grr(_or(repo_path))
    except Exception:
        pass

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
        )
        render_table(results, show_blame=include_blame)

        non_healthy = [m for m in results if m.status != "HEALTHY"]
        if non_healthy:
            render_footer(non_healthy, repo_path, show_blame=include_blame)
        else:
            console.print(
                Panel(
                    f"[bold {C_GREEN}]  ✅  All files look healthy. Great work![/]",
                    border_style=C_DIM_GREEN,
                )
            )

    except git.InvalidGitRepositoryError:
        render_error(
            "Not a git repository",
            f"'{escape(str(repo_path))}' is not inside a git repository.\n"
            "Run deathbed from within a git repo, or pass --path to a repo directory.",
        )
        sys.exit(1)
    except git.NoSuchPathError:
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
    critical = [m for m in results if m.status == "CRITICAL"]
    import click

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
    min_score: Optional[int],
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
    min_score: Optional[int],
) -> None:
    """Run the diff analysis and display the comparison table."""
    from .analyzer import analyze_diff

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

        elapsed = time.monotonic() - start

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
    min_score: Optional[int],
) -> None:
    """Run blame-based analysis and display the team leaderboard."""
    from .analyzer import analyze_leaderboard

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
    min_score: Optional[int],
    output_format: str = "rich",
) -> None:
    """Scan all repos in org_path and show the org-wide health report."""
    from .org import analyze_org

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
                "version": "2.0.0",
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
    min_score: Optional[int],
    output_format: str = "rich",
) -> None:
    """Analyse the repo and render the refactoring plan."""
    from .analyzer import analyze_repo
    from .planner import generate_plan
    from .git_utils import open_repo as _or, get_repo_root as _grr

    repo_root = repo_path
    try:
        repo_root = _grr(_or(repo_path))
    except Exception:
        pass

    if output_format != "markdown":
        render_header()

    try:
        with make_progress() as progress:
            task = progress.add_task(
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
