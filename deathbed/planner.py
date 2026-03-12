"""Refactoring roadmap generator — Sprint-based action plan from local metrics."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Optional

from .scoring import FileMetrics


# ── Effort estimation ─────────────────────────────────────────────────────────

def _estimate_effort(m: FileMetrics) -> str:
    """Return Small / Medium / Large based on lines and complexity."""
    is_large = m.lines > 500 or (m.avg_complexity is not None and m.avg_complexity > 10)
    is_medium = m.lines > 200 or (m.avg_complexity is not None and m.avg_complexity > 5)
    if is_large:
        return "Large"
    if is_medium:
        return "Medium"
    return "Small"


# ── AST helpers for richer actions ────────────────────────────────────────────

def _count_functions(root: Path, m: FileMetrics) -> int:
    """Count all functions/methods in a Python file."""
    try:
        source = (root / m.path).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
        return sum(
            1 for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
    except Exception:
        return 0


def _get_top_level_names(root: Path, m: FileMetrics) -> list[str]:
    """Return top-level class/function names from a Python file."""
    try:
        source = (root / m.path).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
        return [
            node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
    except Exception:
        return []


def _count_public_functions(root: Path, m: FileMetrics) -> int:
    """Count public (non-underscore-prefixed) functions in a Python file."""
    try:
        source = (root / m.path).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
        return sum(
            1 for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        )
    except Exception:
        return 0


# ── Action generation ─────────────────────────────────────────────────────────

def _safe_alternative(smell: str) -> str:
    """Map a security smell description to a safe replacement suggestion."""
    mappings = {
        "eval()":        "ast.literal_eval() for literals, or a safe expression parser",
        "exec()":        "importlib for dynamic imports, or refactor to avoid dynamic code",
        "compile()":     "a safe template engine or static code generation",
        "pickle":        "json, msgpack, or protobuf for serialisation",
        "marshal":       "json or pickle with strict sandboxing",
        "shelve":        "sqlite3 or a proper key-value store",
        "os.system()":   "subprocess.run() with shell=False and a list of args",
        "os.popen()":    "subprocess.run() with shell=False and capture_output=True",
        "os.startfile()": "subprocess.run() with explicit args",
        "shell=True":    "shell=False with a list of arguments",
    }
    for key, val in mappings.items():
        if key in smell:
            return val
    return "a safer, validated alternative"


def _get_action(m: FileMetrics, root: Path) -> str:
    """Generate a specific, actionable recommendation for this file."""
    base_diag = m.diagnosis.replace(" 🔥 heating up", "")

    if "security smell" in base_diag:
        if m.security_smells:
            smell = m.security_smells[0]
            safe = _safe_alternative(smell)
            return f"Replace {smell} with {safe}."
        return "Audit and remove all dangerous patterns (eval, exec, pickle, shell=True)."

    if "god file" in base_diag:
        return (
            f"Break apart this central file — {m.coupling_count} other file(s) depend on it. "
            "Extract cohesive groups of functions into focused, single-responsibility modules."
        )

    if "test theatre" in base_diag:
        return (
            "Add meaningful assert statements to the test file — "
            "it currently contains no assertions and provides zero safety net."
        )

    if "clone risk" in base_diag and m.clone_of:
        return (
            f"Merge with '{m.clone_of}' or extract a shared base class / utility module "
            "to eliminate duplication."
        )

    if "dead code cemetery" in base_diag:
        return (
            f"Remove dead code — vulture detected {m.dead_code_count} unused symbol(s) "
            "at ≥80% confidence. Run `vulture <file>` for the full list."
        )

    if "haunted" in base_diag:
        return (
            "Freeze new features. Schedule an architecture review session. "
            "Document the module intent and assign a single named owner via CODEOWNERS."
        )

    if "clone risk" in base_diag:
        return "Extract shared logic into a utility module to eliminate duplication."

    if "complexity graveyard" in base_diag or (
        m.complexity_score < 30 and m.path.endswith(".py")
    ):
        fn_count = _count_functions(root, m) if m.path.endswith(".py") else "?"
        return (
            f"Extract functions into separate modules — file has ~{fn_count} callable(s) "
            "with critically high average complexity. Aim for complexity ≤ 5 per function."
        )

    if "growing out of control" in base_diag:
        if m.path.endswith(".py"):
            names = _get_top_level_names(root, m)
            if names:
                boundary_str = ", ".join(names[:5])
                suffix = " …" if len(names) > 5 else ""
                return (
                    f"Split into smaller files. Natural boundaries: {boundary_str}{suffix}. "
                    f"File has {m.lines} lines — target < 300 per module."
                )
        return f"Split into smaller files — {m.lines} lines exceeds the 300-line guideline."

    if "nobody's watching" in base_diag:
        fn_count = _count_public_functions(root, m) if m.path.endswith(".py") else "?"
        return (
            f"Add tests for the ~{fn_count} public function(s). "
            "Start with the highest-churn paths — they change most and need tests most."
        )

    if "ownership void" in base_diag:
        return (
            "Schedule a knowledge transfer session, assign a named owner, "
            "and add the file to CODEOWNERS."
        )

    if "too many cooks" in base_diag or "haunted" in base_diag:
        return (
            "Assign a primary owner via CODEOWNERS. "
            "Require explicit reviewer approval for all future changes."
        )

    if "churn monster" in base_diag:
        return (
            "Stabilise the interface — high churn signals an unstable abstraction. "
            "Consider a design review before it entangles more calling code."
        )

    if "legacy ghost" in base_diag or "abandoned" in base_diag:
        return (
            "Schedule a codebase archaeology session — "
            "update, document, or delete this file."
        )

    return (
        "Review and refactor to address the dominant metric issue "
        "(see MOST WANTED panel for a detailed breakdown)."
    )


# ── Plan generation ───────────────────────────────────────────────────────────

def generate_plan(results: list[FileMetrics], root: Path) -> dict:
    """
    Generate a prioritised refactoring roadmap from file metrics.

    Returns a dict with keys 'sprint1', 'sprint2', 'sprint3', each containing
    a list of dicts: {file, action, effort, score, diagnosis}.

    Sprint 1 = CRITICAL  (do this week)
    Sprint 2 = WARNING   (do this month)
    Sprint 3 = FAIR      (do this quarter)
    """
    sprint1: list[dict] = []
    sprint2: list[dict] = []
    sprint3: list[dict] = []

    for m in results:
        if m.status == "HEALTHY":
            continue
        item = {
            "file":      m.path,
            "action":    _get_action(m, root),
            "effort":    _estimate_effort(m),
            "score":     m.composite_score,
            "diagnosis": m.diagnosis,
        }
        if m.status == "CRITICAL":
            sprint1.append(item)
        elif m.status == "WARNING":
            sprint2.append(item)
        else:
            sprint3.append(item)

    return {"sprint1": sprint1, "sprint2": sprint2, "sprint3": sprint3}


# ── Markdown export ───────────────────────────────────────────────────────────

def format_plan_markdown(plan: dict, repo_path: Path) -> str:
    """Format the refactoring plan as a Markdown document."""
    lines = [
        f"# Refactoring Roadmap — {repo_path.name}",
        "",
        "> Generated by **deathbed v3.0.0**.  "
        "All recommendations are derived from local git metrics — no API required.",
        "",
    ]

    sprint_configs = [
        ("sprint1", "Sprint 1 — Do This Week",    "🔴 CRITICAL files"),
        ("sprint2", "Sprint 2 — Do This Month",   "🟡 WARNING files"),
        ("sprint3", "Sprint 3 — Do This Quarter", "🟢 FAIR files"),
    ]

    for key, title, subtitle in sprint_configs:
        items = plan.get(key, [])
        if not items:
            continue
        lines.append(f"## {title}")
        lines.append(f"*{subtitle} · {len(items)} file(s)*")
        lines.append("")
        for item in items:
            lines.append(f"### `{item['file']}` &nbsp; score: {item['score']}/100")
            lines.append(f"- **Diagnosis:** {item['diagnosis']}")
            lines.append(f"- **Action:** {item['action']}")
            lines.append(f"- **Effort:** {item['effort']}")
            lines.append("")

    if not any(plan.get(k) for k, _, _ in sprint_configs):
        lines.append("*All files are healthy — no refactoring needed!* ✅")
        lines.append("")

    return "\n".join(lines)
