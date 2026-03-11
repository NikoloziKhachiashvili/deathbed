"""HTML report generation — self-contained, no external dependencies."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .scoring import FileMetrics


def _score_color_css(score: int) -> str:
    if score >= 80:
        return "#00c850"
    if score >= 60:
        return "#ffbf00"
    if score >= 40:
        return "#ff8c00"
    return "#ff453a"


def _status_class(status: str) -> str:
    return {"CRITICAL": "critical", "WARNING": "warning", "FAIR": "fair"}.get(
        status, "healthy"
    )


def _human_days(days: int) -> str:
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days}d ago"
    if days < 30:
        return f"{days // 7}w ago"
    if days < 365:
        return f"{days // 30}mo ago"
    years = days // 365
    leftover = (days % 365) // 30
    return f"{years}y {leftover}mo ago" if leftover else f"{years}y ago"


def _score_bar_html(score: int) -> str:
    color = _score_color_css(score)
    pct   = score
    return (
        f'<div class="bar-wrap">'
        f'<div class="bar-fill" style="width:{pct}%;background:{color}"></div>'
        f'<span class="bar-label" style="color:{color}">{score}</span>'
        f"</div>"
    )


def _build_table_rows(results: list[FileMetrics]) -> str:
    rows: list[str] = []
    for m in results:
        sc = _status_class(m.status)
        health_icon = {"CRITICAL": "💀", "WARNING": "⚠️", "FAIR": "🌡", "HEALTHY": "✅"}.get(
            m.status, ""
        )
        score_html = _score_bar_html(m.composite_score)
        clone_note = (
            f'<br><small style="color:#ff8c00">clone of {m.clone_of[:30]}…</small>'
            if m.clone_similarity >= 0.4
            else ""
        )
        sec_note = (
            f'<br><small style="color:#ff453a">🔐 {", ".join(m.security_smells[:2])}</small>'
            if m.has_security_smell
            else ""
        )
        rows.append(
            f"<tr class=\"row-{sc}\">"
            f"<td class=\"center\">{health_icon} {m.composite_score}</td>"
            f'<td class="filepath">{m.path}{clone_note}{sec_note}</td>'
            f"<td class=\"right\">{m.lines:,}</td>"
            f"<td class=\"right\">{_human_days(m.days_since_commit)}</td>"
            f"<td class=\"right\">{m.commit_count}</td>"
            f"<td class=\"right\">{m.recent_churn}</td>"
            f"<td class=\"right\">{m.author_count}</td>"
            f"<td class=\"right\">"
            + (f"{m.avg_complexity:.1f}" if m.avg_complexity is not None else "N/A")
            + "</td>"
            f'<td class="diagnosis {sc}">{m.diagnosis}</td>'
            "</tr>"
        )
    return "\n".join(rows)


def _build_most_wanted_html(worst: FileMetrics) -> str:
    rows = [
        ("Size",        worst.size_score,           f"{worst.lines:,} lines"),
        ("Age",         worst.age_score,             _human_days(worst.days_since_commit)),
        ("Churn",       worst.churn_score,           f"{worst.commit_count} commits"),
        ("Recent",      worst.recent_churn_score,    f"{worst.recent_churn} in 90d"),
        ("Complexity",  worst.complexity_score,
         f"{worst.avg_complexity:.1f}" if worst.avg_complexity is not None else "N/A"),
        ("Authors",     worst.author_score,          str(worst.author_count)),
        ("Tests",       worst.test_score,
         "✅ found" if worst.has_test_file else "✗ none"),
    ]
    if worst.path.endswith(".py"):
        rows.append(("Dead Code", worst.dead_code_score,
                     f"{worst.dead_code_count} unused" if worst.dead_code_count else "none"))

    metric_rows = ""
    for label, score, detail in rows:
        color = _score_color_css(score)
        bar   = _score_bar_html(score)
        metric_rows += (
            f"<tr><td>{label}</td><td>{bar}</td>"
            f'<td style="color:{color}">{detail}</td></tr>'
        )

    return f"""
<div class="panel red-panel">
  <div class="panel-title">🪦 MOST WANTED</div>
  <div class="mw-path">{worst.path}</div>
  <div class="mw-diag">"{worst.diagnosis}" — {worst.composite_score}/100</div>
  <table class="metrics-table">{metric_rows}</table>
</div>"""


def _build_security_html(results: list[FileMetrics]) -> str:
    sec_files = [m for m in results if m.has_security_smell]
    if not sec_files:
        return ""
    rows = "".join(
        f"<tr><td>🔐</td><td class=\"filepath\">{m.path}</td>"
        f"<td>{', '.join(m.security_smells[:3])}</td></tr>"
        for m in sec_files[:20]
    )
    return f"""
<div class="panel red-panel">
  <div class="panel-title">🔐 SECURITY ALERTS — {len(sec_files)} file(s)</div>
  <table class="metrics-table">{rows}</table>
</div>"""


_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0a0a0a; color: #e6e6e6; font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 13px; padding: 24px; }
h1 { color: #dc143c; text-align: center; font-size: 2em; letter-spacing: 0.05em; margin-bottom: 4px; }
.tagline { color: #787878; text-align: center; font-style: italic; margin-bottom: 24px; }
.summary { display: flex; gap: 16px; flex-wrap: wrap; justify-content: center; margin-bottom: 24px; }
.stat-box { background: #161616; border: 1px solid #3a0000; border-radius: 6px; padding: 12px 20px; text-align: center; min-width: 90px; }
.stat-val { font-size: 1.6em; font-weight: bold; }
.stat-label { color: #787878; font-size: 0.85em; margin-top: 2px; }
.stat-critical { color: #ff453a; } .stat-warning { color: #ff8c00; }
.stat-fair { color: #ffbf00; } .stat-healthy { color: #00c850; }
.stat-dead { color: #ff8c00; } .stat-sec { color: #ff453a; }
.table-wrap { overflow-x: auto; margin-bottom: 24px; }
table.main { width: 100%; border-collapse: collapse; }
table.main th { background: #1a0000; color: #dc143c; padding: 8px 10px; text-align: left; border-bottom: 2px solid #8b0000; cursor: pointer; user-select: none; white-space: nowrap; }
table.main th:hover { background: #2a0000; }
table.main td { padding: 6px 10px; border-bottom: 1px solid #1a1a1a; vertical-align: middle; }
.row-critical td { color: #ff6464; } .row-warning td { color: #ffb432; }
.row-fair td { color: #e6d750; } .row-healthy td { color: #64d282; opacity: 0.75; }
td.center { text-align: center; } td.right { text-align: right; }
td.filepath { font-size: 0.9em; max-width: 320px; word-break: break-all; }
td.diagnosis { font-style: italic; }
td.diagnosis.critical { color: #ff453a; } td.diagnosis.warning { color: #ff8c00; }
td.diagnosis.fair { color: #ffbf00; } td.diagnosis.healthy { color: #00c850; }
.bar-wrap { display: flex; align-items: center; gap: 6px; min-width: 130px; }
.bar-fill { height: 8px; border-radius: 3px; flex-shrink: 0; }
.bar-label { font-size: 0.85em; white-space: nowrap; }
.panel { background: #0f0f0f; border: 2px solid #8b0000; border-radius: 6px; padding: 16px; margin-bottom: 20px; }
.red-panel { border-color: #8b0000; }
.amber-panel { border: 2px solid #b8860b; }
.panel-title { font-size: 1.1em; font-weight: bold; color: #dc143c; margin-bottom: 12px; }
.amber-panel .panel-title { color: #ffbf00; }
.mw-path { color: #e6e6e6; font-weight: bold; margin-bottom: 4px; }
.mw-diag { color: #787878; font-style: italic; margin-bottom: 12px; }
table.metrics-table { width: 100%; border-collapse: collapse; }
table.metrics-table td { padding: 4px 8px; border-bottom: 1px solid #1a1a1a; vertical-align: middle; }
.qw-item { padding: 4px 0; } .qw-bullet { color: #ffbf00; font-weight: bold; }
.qw-file { color: #e6e6e6; } .qw-suggestion { color: #ffbf00; font-style: italic; }
footer { text-align: center; color: #505050; margin-top: 24px; font-size: 0.85em; }
"""

_SORT_JS = """
function sortTable(n) {
  var tbl = document.getElementById('mainTable'), rows, switching = true, dir = 'asc', i, x, y, shouldSwitch, switchCount = 0;
  while (switching) {
    switching = false; rows = tbl.rows;
    for (i = 1; i < rows.length - 1; i++) {
      shouldSwitch = false;
      x = rows[i].getElementsByTagName('TD')[n];
      y = rows[i+1].getElementsByTagName('TD')[n];
      var xv = isNaN(x.innerText) ? x.innerText.toLowerCase() : Number(x.innerText);
      var yv = isNaN(y.innerText) ? y.innerText.toLowerCase() : Number(y.innerText);
      if ((dir === 'asc' && xv > yv) || (dir === 'desc' && xv < yv)) { shouldSwitch = true; break; }
    }
    if (shouldSwitch) { rows[i].parentNode.insertBefore(rows[i+1], rows[i]); switching = true; switchCount++; }
    else if (switchCount === 0 && dir === 'asc') { dir = 'desc'; switching = true; }
  }
}
"""


def generate_html_report(
    results: list[FileMetrics],
    repo_path: Path,
    elapsed: float,
    total_scanned: int,
) -> str:
    """Generate a complete self-contained HTML report string."""
    critical     = sum(1 for m in results if m.status == "CRITICAL")
    warning      = sum(1 for m in results if m.status == "WARNING")
    fair         = sum(1 for m in results if m.status == "FAIR")
    healthy      = sum(1 for m in results if m.status == "HEALTHY")
    dead_code_ct = sum(1 for m in results if m.dead_code_count > 0)
    sec_ct       = sum(1 for m in results if m.has_security_smell)

    table_rows = _build_table_rows(results)
    most_wanted = _build_most_wanted_html(results[0]) if results else ""
    security_section = _build_security_html(results)

    # Quick Wins
    wins = sorted(
        [m for m in results if m.status in ("WARNING", "FAIR") and m.composite_score >= 41],
        key=lambda m: m.composite_score, reverse=True,
    )[:5]
    quick_wins_rows = ""
    for m in wins:
        suggestion = (
            f"fix security smell ({', '.join(m.security_smells[:1])})"
            if m.has_security_smell
            else "review and improve"
        )
        quick_wins_rows += (
            f'<div class="qw-item">'
            f'<span class="qw-bullet">● </span>'
            f'<span class="qw-file">{m.path}</span> '
            f'<span style="color:#787878">score:{m.composite_score}</span> '
            f'<span class="qw-suggestion">→ {suggestion}</span>'
            f"</div>"
        )
    quick_wins_html = f"""
<div class="panel amber-panel">
  <div class="panel-title">⚡ QUICK WINS</div>
  {quick_wins_rows}
</div>""" if wins else ""

    repo_name = repo_path.name

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>deathbed — {repo_name} health report</title>
<style>{_CSS}</style>
</head>
<body>
<h1>DEATHBED</h1>
<p class="tagline">every codebase has files that are dying.  find them.</p>
<p class="tagline" style="font-size:0.85em">repo: {repo_path}  ·  {len(results)} files shown  ·  {elapsed:.2f}s</p>

<div class="summary">
  <div class="stat-box"><div class="stat-val">{total_scanned}</div><div class="stat-label">🔍 scanned</div></div>
  <div class="stat-box"><div class="stat-val stat-critical">{critical}</div><div class="stat-label">💀 critical</div></div>
  <div class="stat-box"><div class="stat-val stat-warning">{warning}</div><div class="stat-label">⚠️ warning</div></div>
  <div class="stat-box"><div class="stat-val stat-fair">{fair}</div><div class="stat-label">🌡 fair</div></div>
  <div class="stat-box"><div class="stat-val stat-healthy">{healthy}</div><div class="stat-label">✅ healthy</div></div>
  <div class="stat-box"><div class="stat-val stat-dead">{dead_code_ct}</div><div class="stat-label">🧟 dead code</div></div>
  <div class="stat-box"><div class="stat-val stat-sec">{sec_ct}</div><div class="stat-label">🔐 sec smells</div></div>
</div>

<div class="table-wrap">
<table class="main" id="mainTable">
<thead><tr>
  <th onclick="sortTable(0)">HLTH ↕</th>
  <th onclick="sortTable(1)">FILE ↕</th>
  <th onclick="sortTable(2)">LINES ↕</th>
  <th onclick="sortTable(3)">TOUCHED ↕</th>
  <th onclick="sortTable(4)">CHURN ↕</th>
  <th onclick="sortTable(5)">RECENT ↕</th>
  <th onclick="sortTable(6)">AUTH ↕</th>
  <th onclick="sortTable(7)">CPLX ↕</th>
  <th onclick="sortTable(8)">DIAGNOSIS ↕</th>
</tr></thead>
<tbody>
{table_rows}
</tbody>
</table>
</div>

{most_wanted}
{quick_wins_html}
{security_section}

<footer>
  Generated by <strong>deathbed v1.2.0</strong> ·
  MIT License · Nikolozi Khachiashvili
</footer>
<script>{_SORT_JS}</script>
</body>
</html>"""
