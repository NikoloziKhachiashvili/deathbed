"""
Color palette, console instance, logo, and small helpers.
"""

from __future__ import annotations

import logging
import sys

# ── Windows UTF-8 fix ─────────────────────────────────────────────────────────
# Must happen before the Console is created so Rich sees the right encoding.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

from rich.align import Align
from rich.console import Console
from rich.markup import escape
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
from rich.text import Text

log = logging.getLogger(__name__)

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


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else "…" + s[-(n - 1):]


def _human_days(days: int) -> str:
    """Delegate to utils.human_days — kept here for re-export and tui.py compatibility."""
    from ..utils import human_days
    return human_days(days)


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
