"""Interactive TUI for deathbed using Textual (optional dependency)."""
from __future__ import annotations

from pathlib import Path


def run_interactive(
    repo_path: Path,
    top: int,
    min_score: int | None,
    since_ref: str | None = None,
    include_blame: bool = False,
    org_path: Path | None = None,
) -> None:
    """Launch the interactive TUI. Falls back to rich display if textual unavailable."""
    try:
        import textual  # noqa: F401
    except ImportError:
        from rich import box
        from rich.panel import Panel

        from .display import console
        console.print(Panel(
            "[bold rgb(255,191,0)]  textual is not installed.\n\n"
            "  Install it with:\n"
            "    pip install deathbed[interactive]\n"
            "  or\n"
            "    pip install textual\n\n"
            "  Falling back to standard rich output...[/]",
            title="[bold rgb(255,191,0)]  \U0001f4e6  OPTIONAL DEPENDENCY MISSING  [/]",
            border_style="rgb(255,191,0)",
            box=box.HEAVY,
            padding=(1, 2),
        ))
        from .display import run_display
        run_display(repo_path, top, min_score, since_ref=since_ref, include_blame=include_blame)
        return

    _run_textual_app(repo_path, top, min_score, since_ref, include_blame, org_path)


def _run_textual_app(
    repo_path: Path,
    top: int,
    min_score: int | None,
    since_ref: str | None,
    include_blame: bool,
    org_path: Path | None,
) -> None:
    """Launch the full Textual TUI app."""
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.screen import Screen
    from textual.widgets import DataTable, Footer, Input, Static

    from .analyzer import analyze_repo
    from .display import _health_icon, _human_days, _truncate
    from .git_utils import get_repo_root, open_repo
    from .history import enrich_with_history, save_scan
    from .scoring import FileMetrics, compute_repo_score, letter_grade

    # Pre-scan
    try:
        repo_root = get_repo_root(open_repo(repo_path))
    except Exception:
        repo_root = repo_path

    results = analyze_repo(
        repo_path, top=top, min_score=min_score,
        since_ref=since_ref, include_blame=include_blame,
    )
    repo_score = compute_repo_score(results)
    enrich_with_history(results, repo_root)
    save_scan(repo_root, results, repo_score)

    _LOGO = (
        "\u2588\u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2557  \u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2557 \n"
        "\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2550\u2550\u255d\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u255a\u2550\u2550\u2588\u2588\u2554\u2550\u2550\u255d\u2588\u2588\u2551  \u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2550\u2550\u255d\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\n"
        "\u2588\u2588\u2551  \u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2557  \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2551   \u2588\u2588\u2551   \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2588\u2588\u2588\u2557  \u2588\u2588\u2551  \u2588\u2588\u2551\n"
        "\u2588\u2588\u2551  \u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u255d  \u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2551   \u2588\u2588\u2551   \u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u255d  \u2588\u2588\u2551  \u2588\u2588\u2551\n"
        "\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2551  \u2588\u2588\u2551   \u2588\u2588\u2551   \u2588\u2588\u2551  \u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\n"
        "\u255a\u2550\u2550\u2550\u2550\u2550\u255d \u255a\u2550\u2550\u2550\u2550\u2550\u2550\u255d\u255a\u2550\u255d  \u255a\u2550\u255d   \u255a\u2550\u255d   \u255a\u2550\u255d  \u255a\u2550\u255d\u255a\u2550\u2550\u2550\u2550\u2550\u255d \u255a\u2550\u2550\u2550\u2550\u2550\u2550\u255d\u255a\u2550\u2550\u2550\u2550\u2550\u255d "
    )

    SORT_OPTIONS = ["score", "lines", "churn", "coupling", "complexity"]

    TUI_CSS = """
App {
    background: #0d0000;
}
Screen {
    background: #0d0000;
}
#banner {
    background: #1a0000;
    color: rgb(220, 20, 60);
    text-align: center;
    padding: 0 1;
    height: 7;
}
#stats {
    background: #1a0000;
    color: rgb(255, 191, 0);
    padding: 0 2;
    height: 1;
}
#search {
    background: #0d0000;
    border: solid rgb(220, 20, 60);
    height: 3;
    display: none;
}
#search.visible {
    display: block;
}
DataTable {
    background: #0d0000;
    color: rgb(230, 230, 230);
    height: 1fr;
}
DataTable > .datatable--header {
    background: #2a0000;
    color: rgb(220, 20, 60);
    text-style: bold;
}
DataTable > .datatable--cursor {
    background: #3a1000;
    color: rgb(255, 191, 0);
}
Footer {
    background: #1a0000;
    color: rgb(120, 120, 120);
}
#detail_content {
    background: #0d0000;
    color: rgb(230, 230, 230);
    padding: 1 2;
}
#plan_content {
    background: #0d0000;
    color: rgb(255, 191, 0);
    padding: 1 2;
}
"""

    class DetailScreen(Screen):
        BINDINGS = [Binding("q", "app.pop_screen", "Back"), Binding("escape", "app.pop_screen", "Back")]

        def __init__(self, m: FileMetrics) -> None:
            super().__init__()
            self._m = m

        def compose(self) -> ComposeResult:
            m = self._m
            cx = f"{m.avg_complexity:.1f}" if m.avg_complexity is not None else "N/A"
            test_str = "\u2705 found" if m.has_test_file else "\u2717  none"

            def bar(score: int) -> str:
                filled = score // 10
                return "\u2588" * filled + "\u2591" * (10 - filled)

            lines = [
                f"  {m.path}",
                f"  \"{m.diagnosis}\"   {_health_icon(m.status)} {m.composite_score}/100",
                "",
                f"  SIZE        {bar(m.size_score):<10}  {m.size_score:3d}   Lines: {m.lines:,}",
                f"  AGE         {bar(m.age_score):<10}  {m.age_score:3d}   Last commit: {_human_days(m.days_since_commit)}",
                f"  CHURN       {bar(m.churn_score):<10}  {m.churn_score:3d}   Total commits: {m.commit_count}",
                f"  RECENT      {bar(m.recent_churn_score):<10}  {m.recent_churn_score:3d}   Last 90d: {m.recent_churn}",
                f"  COMPLEXITY  {bar(m.complexity_score):<10}  {m.complexity_score:3d}   Avg: {cx}",
                f"  AUTHORS     {bar(m.author_score):<10}  {m.author_score:3d}   Count: {m.author_count}",
                f"  TESTS       {bar(m.test_score):<10}  {m.test_score:3d}   {test_str}",
                f"  COUPLING    {bar(m.coupling_score):<10}  {m.coupling_score:3d}   Dependents: {m.coupling_count}",
                f"  DEAD CODE   {bar(m.dead_code_score):<10}  {m.dead_code_score:3d}   Count: {m.dead_code_count}",
            ]
            if m.importers:
                lines.append("")
                lines.append(f"  Imported by: {', '.join(_truncate(p, 25) for p in m.importers[:5])}")
            if m.last_author:
                lines.append("")
                lines.append(f"  Last author: {m.last_author}  \u2014  {_truncate(m.last_commit_msg, 60)}")

            yield Static("\n".join(lines), id="detail_content")
            yield Footer()

    class PlanScreen(Screen):
        BINDINGS = [Binding("q", "app.pop_screen", "Back"), Binding("escape", "app.pop_screen", "Back")]

        def __init__(self, plan: dict) -> None:
            super().__init__()
            self._plan = plan

        def compose(self) -> ComposeResult:
            plan = self._plan
            lines = ["  REFACTORING PLAN\n  " + "=" * 60]
            for sprint, label in [
                ("sprint1", "SPRINT 1 \u2014 DO THIS WEEK"),
                ("sprint2", "SPRINT 2 \u2014 DO THIS MONTH"),
                ("sprint3", "SPRINT 3 \u2014 DO THIS QUARTER"),
            ]:
                items = plan.get(sprint, [])
                if not items:
                    continue
                lines.append(f"\n  {label}  ({len(items)} file(s))")
                for item in items:
                    lines.append(f"\n  \u25cf  {_truncate(item['file'], 50):<52} [{item['effort']}]")
                    lines.append(f"     \u2192 {item['action']}")
            yield Static("\n".join(lines), id="plan_content")
            yield Footer()

    class DeathbedApp(App):
        CSS = TUI_CSS

        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("escape", "back_or_quit", "Back/Quit"),
            Binding("j", "move_down", "Down", show=False),
            Binding("down", "move_down", "Down", show=False),
            Binding("k", "move_up", "Up", show=False),
            Binding("up", "move_up", "Up", show=False),
            Binding("enter", "show_detail", "Detail"),
            Binding("p", "toggle_plan", "Plan"),
            Binding("slash", "open_search", "Search"),
            Binding("s", "cycle_sort", "Sort"),
            Binding("b", "toggle_blame", "Blame"),
        ]

        def __init__(self, all_results: list, rroot: Path, rscore: int) -> None:
            super().__init__()
            self._all_results = list(all_results)
            self._filtered = list(all_results)
            self._repo_root = rroot
            self._repo_score = rscore
            self._sort_idx = 0
            self._show_blame = include_blame

        def compose(self) -> ComposeResult:
            yield Static(_LOGO, id="banner")
            yield Static(self._stats_text(), id="stats")
            yield Input(placeholder="Filter by filename, diagnosis, or status... (press / to open)", id="search")
            yield DataTable(id="main_table")
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one(DataTable)
            table.add_column("HLTH", key="hlth", width=8)
            table.add_column("FILE", key="file", width=50)
            table.add_column("LINES", key="lines", width=7)
            table.add_column("TOUCHED", key="touched", width=10)
            table.add_column("CHURN", key="churn", width=6)
            table.add_column("CPLX", key="cplx", width=6)
            table.add_column("COUP", key="coup", width=5)
            table.add_column("DIAGNOSIS", key="diagnosis", width=30)
            self._populate_table()

        def _stats_text(self) -> str:
            r = self._filtered
            crit = sum(1 for m in r if m.status == "CRITICAL")
            warn = sum(1 for m in r if m.status == "WARNING")
            fair = sum(1 for m in r if m.status == "FAIR")
            hlth = sum(1 for m in r if m.status == "HEALTHY")
            grade = letter_grade(self._repo_score)
            return (
                f"  \U0001f480 {crit} critical  "
                f"\u26a0\ufe0f  {warn} warning  "
                f"\U0001f321 {fair} fair  "
                f"\u2705 {hlth} healthy  "
                f"  \U0001f4ca {grade} ({self._repo_score}) repo score  "
                f"  {len(r)}/{len(self._all_results)} files shown"
            )

        def _populate_table(self) -> None:
            table = self.query_one(DataTable)
            table.clear()
            for m in self._filtered:
                cx = f"{m.avg_complexity:.1f}" if m.avg_complexity is not None else "N/A"
                table.add_row(
                    f"{_health_icon(m.status)} {m.composite_score}",
                    _truncate(m.path, 48),
                    str(m.lines),
                    _human_days(m.days_since_commit),
                    str(m.commit_count),
                    cx,
                    str(m.coupling_count),
                    _truncate(m.diagnosis, 28),
                    key=m.path,
                )

        def _update_filter(self, text: str) -> None:
            t = text.lower()
            if not t:
                self._filtered = list(self._all_results)
            else:
                self._filtered = [
                    m for m in self._all_results
                    if (t in m.path.lower() or t in m.diagnosis.lower() or t in m.status.lower())
                ]
            self._populate_table()
            self.query_one("#stats", Static).update(self._stats_text())

        def on_input_changed(self, event: Input.Changed) -> None:
            if event.input.id == "search":
                self._update_filter(event.value)

        def action_quit(self) -> None:
            self.exit()

        def action_back_or_quit(self) -> None:
            if len(self.screen_stack) > 1:
                self.pop_screen()
            else:
                self.exit()

        def action_move_down(self) -> None:
            table = self.query_one(DataTable)
            table.move_cursor(row=table.cursor_row + 1)

        def action_move_up(self) -> None:
            table = self.query_one(DataTable)
            table.move_cursor(row=max(0, table.cursor_row - 1))

        def action_show_detail(self) -> None:
            table = self.query_one(DataTable)
            if table.cursor_row < len(self._filtered):
                m = self._filtered[table.cursor_row]
                self.push_screen(DetailScreen(m))

        def action_toggle_plan(self) -> None:
            from .planner import generate_plan
            plan = generate_plan(self._all_results, self._repo_root)
            self.push_screen(PlanScreen(plan))

        def action_open_search(self) -> None:
            search = self.query_one("#search", Input)
            search.toggle_class("visible")
            if search.has_class("visible"):
                search.focus()

        def action_cycle_sort(self) -> None:
            self._sort_idx = (self._sort_idx + 1) % len(SORT_OPTIONS)
            col = SORT_OPTIONS[self._sort_idx]
            sort_keys = {
                "score":      lambda m: m.composite_score,
                "lines":      lambda m: -m.lines,
                "churn":      lambda m: -m.commit_count,
                "coupling":   lambda m: -m.coupling_count,
                "complexity": lambda m: -(m.avg_complexity or 0.0),
            }
            key_fn = sort_keys.get(col, lambda m: m.composite_score)
            self._filtered.sort(key=key_fn)
            self._all_results.sort(key=key_fn)
            self._populate_table()
            self.notify(f"Sorted by {col}", timeout=1.5)

        def action_toggle_blame(self) -> None:
            self._show_blame = not self._show_blame
            self.notify(f"Blame {'on' if self._show_blame else 'off'}", timeout=1.5)

    app = DeathbedApp(results, repo_root, repo_score)
    app.run()
