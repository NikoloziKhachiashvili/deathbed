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

from .scoring import FileMetrics

# ── Global console ─────────────────────────────────────────────────────────────
# legacy_windows=False forces Rich to use ANSI/VT sequences on Windows 10+
# instead of the old win32 API which cannot render Unicode box-drawing chars.

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

# Row background colours (on dark terminal)
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
) -> None:
    """Display the post-scan summary stats panel."""
    critical      = sum(1 for m in results if m.status == "CRITICAL")
    warning       = sum(1 for m in results if m.status == "WARNING")
    fair          = sum(1 for m in results if m.status == "FAIR")
    healthy       = sum(1 for m in results if m.status == "HEALTHY")
    dead_code_ct  = sum(1 for m in results if m.dead_code_count > 0)
    sec_smell_ct  = sum(1 for m in results if m.has_security_smell)

    grid = Table.grid(expand=True, padding=(0, 2))
    for _ in range(8):
        grid.add_column(justify="center")

    def _stat(icon: str, label: str, value: str, color: str) -> Text:
        t = Text(justify="center")
        t.append(f"{icon}\n", style=f"bold {color}")
        t.append(f"{value}\n", style=f"bold {color}")
        t.append(label, style=f"dim {C_GREY}")
        return t

    grid.add_row(
        _stat("🔍", "scanned",    str(total_scanned), C_WHITE),
        _stat("💀", "critical",   str(critical),      C_SKULL),
        _stat("⚠️ ", "warning",   str(warning),       C_ORANGE),
        _stat("🌡 ", "fair",      str(fair),           C_AMBER),
        _stat("✅", "healthy",    str(healthy),        C_GREEN),
        _stat("🧟", "dead code",  str(dead_code_ct),   C_ORANGE),
        _stat("🔐", "sec smells", str(sec_smell_ct),   C_RED1),
        _stat("⏱ ", "duration",  f"{elapsed:.2f}s",   C_GREY),
    )

    panel = Panel(
        Padding(grid, (1, 0)),
        title=f"[bold {C_CRIMSON}]  SCAN COMPLETE  [/]",
        border_style=C_RED5,
        box=box.HEAVY,
    )
    console.print(panel)
    console.print()


def render_table(results: list[FileMetrics]) -> None:
    """Render the main beautiful results table."""
    if not results:
        console.print(
            Panel(
                f"[bold {C_GREEN}]  No files matched the given thresholds.[/]",
                border_style=C_DIM_GREEN,
            )
        )
        return

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
    table.add_column("LINES",   justify="right",  width=6,  no_wrap=True)
    table.add_column("TOUCHED", justify="right",  width=10, no_wrap=True)
    table.add_column("CHURN",   justify="right",  width=5,  no_wrap=True)
    table.add_column("RECENT",  justify="right",  width=7,  no_wrap=True)  # +1 for arrow
    table.add_column("AUTH",    justify="right",  width=4,  no_wrap=True)
    table.add_column("CPLX",    justify="right",  width=5,  no_wrap=True)
    table.add_column("DIAGNOSIS", justify="left", ratio=1,  no_wrap=True)

    _trend_arrow = {"up": ("▲", C_SKULL), "down": ("▼", C_DIM_GREEN), "stable": ("━", C_DIM)}

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

        # LINES cell
        lines_color = (
            C_SKULL  if m.lines > 1000 else
            C_ORANGE if m.lines > 600  else
            C_AMBER  if m.lines > 300  else
            C_GREEN
        )
        lines_t = Text(f"{m.lines:,}", style=f"bold {lines_color}", justify="right")

        # LAST TOUCHED cell
        age_color = (
            C_SKULL  if m.days_since_commit > 730 else
            C_ORANGE if m.days_since_commit > 365 else
            C_AMBER  if m.days_since_commit > 180 else
            C_GREEN
        )
        age_t = Text(_human_days(m.days_since_commit), style=age_color, justify="right")

        # CHURN cell
        churn_color = (
            C_SKULL  if m.commit_count > 100 else
            C_ORANGE if m.commit_count > 50  else
            C_AMBER  if m.commit_count > 20  else
            C_GREEN
        )
        churn_t = Text(str(m.commit_count), style=churn_color, justify="right")

        # RECENT CHURN cell with trend arrow ▲▼━
        recent_color = (
            C_SKULL  if m.recent_churn > 30 else
            C_ORANGE if m.recent_churn > 15 else
            C_AMBER  if m.recent_churn > 5  else
            C_GREEN
        )
        arrow, arrow_color = _trend_arrow.get(m.churn_trend, ("━", C_DIM))
        recent_t = Text(justify="right")
        recent_t.append(str(m.recent_churn), style=recent_color)
        recent_t.append(f" {arrow}", style=arrow_color)

        # AUTHORS cell
        auth_color = (
            C_SKULL  if m.author_count > 10 else
            C_ORANGE if m.author_count > 6  else
            C_AMBER  if m.author_count > 3  else
            C_GREEN
        )
        auth_t = Text(str(m.author_count), style=auth_color, justify="right")

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

        # DIAGNOSIS cell
        diag_color = (
            C_SKULL     if m.status == "CRITICAL" else
            C_ORANGE    if m.status == "WARNING"  else
            C_AMBER     if m.status == "FAIR"     else
            C_DIM_GREEN
        )
        diag_t = Text(m.diagnosis, style=f"italic {diag_color}")

        table.add_row(
            health_t, file_t, lines_t, age_t,
            churn_t, recent_t, auth_t, cx_t, diag_t,
        )

    console.print(table)
    console.print()


def render_footer(results: list[FileMetrics], repo_root: Path) -> None:
    """Render the Most Wanted, Quick Wins, Tips, and Security Alerts panels."""
    if not results:
        return

    _render_most_wanted(results[0])
    _render_quick_wins(results)
    _render_tips(results)
    _render_security_alerts(results)


# ── Footer helpers ─────────────────────────────────────────────────────────────

def _render_most_wanted(worst: FileMetrics) -> None:
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

    # Dead code row (only meaningful for Python files)
    is_python = worst.path.endswith(".py")
    if is_python:
        dead_display = (
            f"{worst.dead_code_count} unused symbol(s)"
            if worst.dead_code_count > 0
            else "none detected"
        )
        _row("dead code", worst.dead_code_score, "Vulture", dead_display)

    header = Text(justify="left")
    header.append(f"  {escape(worst.path)}\n", style=f"bold {C_WHITE}")
    header.append(f"  \"{worst.diagnosis}\"", style=f"italic dim {C_GREY}")
    header.append(
        f"   {_health_icon(worst.status)} {worst.composite_score}/100",
        style=f"bold {_score_color(worst.composite_score)}",
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
        # If security smell, surface that first
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
        "recent_churn": 0, "complexity": 0, "authors": 0, "test": 0, "dead_code": 0,
    }
    for m in results:
        scores = {
            "size": m.size_score, "age": m.age_score, "churn": m.churn_score,
            "recent_churn": m.recent_churn_score,
            "complexity": m.complexity_score, "authors": m.author_score,
            "test": m.test_score, "dead_code": m.dead_code_score,
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
    }

    # Show top 3 dominant patterns
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

    # Sort: most worsened first (smallest delta first)
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
    table.add_column("FILE",        justify="left",   ratio=2, no_wrap=True)
    table.add_column("BEFORE",      justify="center", width=8, no_wrap=True)
    table.add_column("NOW",         justify="center", width=8, no_wrap=True)
    table.add_column("CHANGE",      justify="center", width=8, no_wrap=True)
    table.add_column("STATUS",      justify="left",   width=9, no_wrap=True)

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

        # Status change label
        if m.status != h.status:
            status_t = Text(f"{h.status}→{m.status}", style=_row_style(m.status))
        else:
            status_t = Text(m.status, style=_row_style(m.status))

        table.add_row(file_t, before_t, now_t, change_t, status_t)

    console.print(table)
    console.print()

    # Summary line
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

    headers = ["FILE", "SCORE", "STATUS", "LINES", "LAST TOUCHED", "CHURN", "AUTHORS", "DIAGNOSIS"]
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
            m.diagnosis,
        ]
        click.echo("| " + " | ".join(row) + " |")


# ── Main entry points ──────────────────────────────────────────────────────────

def run_display(
    repo_path: Path,
    top: int,
    min_score: Optional[int],
    ci_mode: bool = False,
) -> None:
    """Full deathbed run: header → scan → table → footer."""
    from .analyzer import analyze_repo

    if not ci_mode:
        render_header()

    try:
        start = time.monotonic()
        results: list[FileMetrics] = []
        total_scanned = 0

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
            )

        elapsed = time.monotonic() - start

        if total_scanned == 0:
            render_error(
                "No files found",
                "No analysable source files were found in the repository. "
                "Make sure you are inside a git repo with tracked .py / .js / .ts / ... files.",
            )
            return

        if ci_mode:
            _run_ci(results, total_scanned)
            return

        render_summary(results, total_scanned, elapsed)
        render_table(results)

        non_healthy = [m for m in results if m.status != "HEALTHY"]
        if non_healthy:
            render_footer(non_healthy, repo_path)
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
