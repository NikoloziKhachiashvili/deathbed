"""Terminal treemap heat map renderer for the codebase."""
from __future__ import annotations

import logging
from pathlib import Path

from rich import box
from rich.panel import Panel
from rich.text import Text

from .scoring import FileMetrics

log = logging.getLogger(__name__)

__all__ = ["render_heatmap"]


# Import palette from display to keep colours consistent
def _get_palette():
    from .display import (
        C_AMBER,
        C_CRIMSON,
        C_DIM,
        C_GREEN,
        C_GREY,
        C_ORANGE,
        C_RED5,
        C_SKULL,
        C_WHITE,
        console,
    )
    return C_GREEN, C_AMBER, C_ORANGE, C_SKULL, C_RED5, C_CRIMSON, C_DIM, C_WHITE, C_GREY, console


def _heatmap_color(score: int) -> str:
    if score >= 86:
        return "rgb(0,200,80)"     # bright green
    if score >= 66:
        return "rgb(200,200,0)"    # yellow
    if score >= 41:
        return "rgb(255,140,0)"    # amber/orange
    return "rgb(255,69,58)"        # bright red


def _heatmap_char(score: int) -> str:
    if score >= 86:
        return "\u2588"   # █
    if score >= 66:
        return "\u2593"   # ▓
    if score >= 41:
        return "\u2592"   # ▒
    return "\u2591"        # ░


def render_heatmap(results: list[FileMetrics]) -> None:
    """
    Render a terminal treemap heatmap of the codebase.
    Each file is a rectangle sized proportional to its line count,
    coloured by health score.
    """
    C_GREEN, C_AMBER, C_ORANGE, C_SKULL, C_RED5, C_CRIMSON, C_DIM, C_WHITE, C_GREY, console = _get_palette()

    if not results:
        return

    term_width = console.width
    if term_width < 80:
        console.print(Panel(
            f"[dim {C_GREY}]Terminal too narrow for heatmap. Minimum 80 columns required "
            f"(current: {term_width}).[/]",
            title=f"[bold {C_CRIMSON}]  \U0001f321  CODEBASE HEAT MAP  [/]",
            border_style=C_RED5,
            box=box.HEAVY,
        ))
        return

    inner_width = term_width - 4  # account for panel border + padding
    total_lines = sum(max(m.lines, 1) for m in results)

    # Build cells: (FileMetrics, char_width)
    cells = []
    for m in results:
        w = max(2, int(m.lines / total_lines * inner_width))
        cells.append((m, w))

    # Pack cells into rows (greedy strip)
    rows = []
    current_row = []
    current_w = 0

    for cell in cells:
        m, w = cell
        if current_w + w > inner_width and current_row:
            rows.append(current_row)
            current_row = [cell]
            current_w = w
        else:
            current_row.append(cell)
            current_w += w

    if current_row:
        rows.append(current_row)

    content = Text()

    for row in rows:
        row_total = sum(w for _, w in row)
        if row_total == 0:
            continue
        scale = inner_width / row_total
        scaled = [(m, max(2, int(w * scale))) for m, w in row]

        # Adjust last cell to fill remainder exactly
        used = sum(w for _, w in scaled)
        if used < inner_width and scaled:
            last_m, last_w = scaled[-1]
            scaled[-1] = (last_m, last_w + (inner_width - used))

        name_row = Text()
        fill_row = Text()

        for m, w in scaled:
            color = _heatmap_color(m.composite_score)
            char  = _heatmap_char(m.composite_score)
            fname = Path(m.path).name
            if len(fname) >= w:
                fname = fname[:max(0, w - 1)]
            padded = (fname + " " * w)[:w]
            name_row.append(padded, style=f"bold {color}")
            fill_row.append(char * w, style=f"bold {color}")

        content.append_text(name_row)
        content.append("\n")
        content.append_text(fill_row)
        content.append("\n")

    # Legend
    content.append("\n")
    legend = Text(justify="center")
    legend.append("  \u25a0 ", style="rgb(0,200,80)")
    legend.append("86-100 HEALTHY  ", style=f"dim {C_GREY}")
    legend.append("\u25a0 ", style="rgb(200,200,0)")
    legend.append("66-85 FAIR  ", style=f"dim {C_GREY}")
    legend.append("\u25a0 ", style="rgb(255,140,0)")
    legend.append("41-65 WARNING  ", style=f"dim {C_GREY}")
    legend.append("\u25a0 ", style="rgb(255,69,58)")
    legend.append("0-40 CRITICAL", style=f"dim {C_GREY}")
    content.append_text(legend)

    panel = Panel(
        content,
        title=f"[bold {C_CRIMSON}]  \U0001f321  CODEBASE HEAT MAP  [/]",
        subtitle=f"[dim {C_GREY}]{len(results)} files \u00b7 size proportional to lines of code[/]",
        border_style=C_RED5,
        box=box.HEAVY,
        padding=(0, 1),
    )
    console.print(panel)
    console.print()
