"""
deathbed.display — Rich output rendering package.

Re-exports the full public API so all existing imports like:
    from .display import console, render_error, run_display
continue to work with zero changes in other files.
"""

from __future__ import annotations

from .palette import (
    C_AMBER,
    C_CRIMSON,
    C_DIM,
    C_DIM_GREEN,
    C_GREEN,
    C_GREY,
    C_ORANGE,
    C_RED1,
    C_RED2,
    C_RED3,
    C_RED4,
    C_RED5,
    C_RED6,
    C_SKULL,
    C_WHITE,
    ROW_CRITICAL,
    ROW_FAIR,
    ROW_HEALTHY,
    ROW_WARNING,
    _build_logo,
    _health_icon,
    _human_days,
    _row_style,
    _score_bar,
    _score_color,
    _truncate,
    console,
    make_progress,
    render_error,
    render_header,
    render_org_header,
)
from .renderers import (
    _render_decay_panel,
    _render_most_coupled,
    _render_most_wanted,
    _render_plan_rich,
    _render_quick_wins,
    _render_security_alerts,
    _render_tips,
    render_diff,
    render_footer,
    render_leaderboard,
    render_markdown,
    render_org_report,
    render_plan,
    render_summary,
    render_table,
)
from .runners import (
    _run_ci,
    run_diff_display,
    run_display,
    run_heatmap_display,
    run_leaderboard_display,
    run_org_display,
    run_plan_display,
    run_watch_display,
)

__all__ = [
    # Palette
    "console",
    "C_CRIMSON", "C_RED1", "C_RED2", "C_RED3", "C_RED4", "C_RED5", "C_RED6",
    "C_ORANGE", "C_AMBER", "C_GREEN", "C_DIM_GREEN", "C_GREY", "C_WHITE", "C_DIM", "C_SKULL",
    "ROW_CRITICAL", "ROW_WARNING", "ROW_FAIR", "ROW_HEALTHY",
    "_build_logo", "_health_icon", "_row_style", "_score_color", "_score_bar",
    "_human_days", "_truncate",
    "render_header", "render_org_header", "render_error", "make_progress",
    # Renderers
    "render_summary", "render_table", "render_footer",
    "_render_most_wanted", "_render_most_coupled", "_render_quick_wins",
    "_render_tips", "_render_security_alerts", "_render_decay_panel",
    "render_plan", "_render_plan_rich",
    "render_org_report", "render_diff", "render_leaderboard", "render_markdown",
    # Runners
    "run_display", "_run_ci",
    "run_watch_display", "run_diff_display", "run_leaderboard_display",
    "run_org_display", "run_plan_display", "run_heatmap_display",
]
