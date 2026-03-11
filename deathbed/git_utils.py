"""GitPython helpers for extracting per-file history."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import git


def open_repo(path: Path) -> git.Repo:
    """Open a git repo, raising git.InvalidGitRepositoryError if not one."""
    return git.Repo(str(path), search_parent_directories=True)


def get_repo_root(repo: git.Repo) -> Path:
    return Path(repo.working_tree_dir)  # type: ignore[arg-type]


def count_lines(abs_path: Path) -> int:
    """Count lines in a file, returning 0 on read error."""
    try:
        text = abs_path.read_text(encoding="utf-8", errors="replace")
        return text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    except OSError:
        return 0


def get_file_history(
    repo: git.Repo, rel_path: str
) -> tuple[int, int, int, int, int]:
    """
    Return (days_since_last_commit, commit_count, author_count,
            recent_churn, prev_churn) for a file.
    recent_churn = commits in the last 90 days.
    prev_churn   = commits in the 90 days before that (days 91-180 ago).
    Uses `git log --follow` for rename tracking.
    Returns (0, 0, 0, 0, 0) if the file has no history.
    """
    try:
        raw = repo.git.log(
            "--follow",
            "--format=%at\x1f%ae",
            "--",
            rel_path,
        )
    except git.GitCommandError:
        return 0, 0, 0, 0, 0

    if not raw.strip():
        return 0, 0, 0, 0, 0

    entries: list[tuple[int, str]] = []
    for line in raw.strip().splitlines():
        if "\x1f" not in line:
            continue
        ts_str, author = line.split("\x1f", 1)
        try:
            entries.append((int(ts_str.strip()), author.strip().lower()))
        except ValueError:
            continue

    if not entries:
        return 0, 0, 0, 0, 0

    now = int(time.time())
    ninety_days = 90 * 86400

    latest_ts = entries[0][0]
    days = max(0, (now - latest_ts) // 86400)
    commit_count = len(entries)
    author_count = len({a for _, a in entries})

    recent_cutoff = now - ninety_days
    prev_cutoff = now - 2 * ninety_days
    recent_churn = sum(1 for ts, _ in entries if ts >= recent_cutoff)
    prev_churn = sum(1 for ts, _ in entries if prev_cutoff <= ts < recent_cutoff)

    return days, commit_count, author_count, recent_churn, prev_churn


def find_test_file(repo_root: Path, rel_path: Path) -> tuple[bool, bool]:
    """
    Look for a corresponding test file anywhere in the repo.
    Returns (has_test, is_recent) where is_recent means modified within 90 days.
    """
    stem = rel_path.stem
    candidates = [
        f"test_{stem}",
        f"{stem}_test",
        f"test_{stem}.py",
        f"{stem}_test.py",
        f"spec_{stem}.js",
        f"{stem}.spec.js",
        f"{stem}.test.js",
        f"{stem}.spec.ts",
        f"{stem}.test.ts",
    ]
    # Also look in common test directories
    test_dirs = {"tests", "test", "spec", "__tests__", "test_suite"}

    now = time.time()
    ninety_days = 90 * 86400

    for dirpath, dirnames, filenames in __import__("os").walk(repo_root):
        dir_p = Path(dirpath)
        for fname in filenames:
            lower = fname.lower()
            for candidate in candidates:
                if lower == candidate.lower() or lower.startswith(f"test_{stem}".lower()):
                    fpath = dir_p / fname
                    try:
                        mtime = fpath.stat().st_mtime
                        is_recent = (now - mtime) < ninety_days
                    except OSError:
                        is_recent = False
                    return True, is_recent
            # check if file is in a test dir and has the stem in the name
            if dir_p.name in test_dirs and stem.lower() in lower:
                fpath = dir_p / fname
                try:
                    mtime = fpath.stat().st_mtime
                    is_recent = (now - mtime) < ninety_days
                except OSError:
                    is_recent = False
                return True, is_recent

    return False, False


def get_complexity(abs_path: Path) -> Optional[float]:
    """
    Run radon cyclomatic complexity on a Python file.
    Returns average complexity or None if not applicable / radon fails.
    """
    if abs_path.suffix.lower() != ".py":
        return None
    try:
        from radon.complexity import cc_visit

        source = abs_path.read_text(encoding="utf-8", errors="replace")
        results = cc_visit(source)
        if not results:
            return 1.0  # trivially simple
        return sum(r.complexity for r in results) / len(results)
    except Exception:
        return None
