"""Orchestrates per-file metric collection and scoring."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import git

from .filters import get_analyzable_files
from .git_utils import (
    count_lines,
    find_test_file,
    get_complexity,
    get_file_history,
    get_repo_root,
    open_repo,
)
from .scoring import FileMetrics, compute_scores


def analyze_repo(
    repo_path: Path,
    top: int = 50,
    min_score: Optional[int] = None,
    quiet: bool = False,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> list[FileMetrics]:
    """
    Analyze a git repository and return scored FileMetrics, worst-first.

    Args:
        repo_path:    Path to the repo (or any subdir).
        top:          Return at most N results (0 = unlimited).
        min_score:    Only return files with composite_score < min_score.
        quiet:        Suppress internal prints.
        on_progress:  Callback(rel_path, current_index, total) called per file.

    Raises:
        git.InvalidGitRepositoryError: if path is not inside a git repo.
        git.NoSuchPathError:           if path does not exist.
    """
    repo = open_repo(repo_path)
    root = get_repo_root(repo)

    files = get_analyzable_files(root)
    total = len(files)
    results: list[FileMetrics] = []

    for idx, rel_path in enumerate(files):
        if on_progress:
            on_progress(str(rel_path), idx, total)

        abs_path = root / rel_path
        rel_str = rel_path.as_posix()

        try:
            lines = count_lines(abs_path)
            days, commits, authors, recent_churn, prev_churn = get_file_history(repo, rel_str)
            avg_cx = get_complexity(abs_path)
            has_test, test_recent = find_test_file(root, rel_path)

            m = FileMetrics(
                path=rel_str,
                lines=lines,
                days_since_commit=days,
                commit_count=commits,
                author_count=authors,
                avg_complexity=avg_cx,
                has_test_file=has_test,
                test_file_recent=test_recent,
                recent_churn=recent_churn,
                prev_churn=prev_churn,
            )
            compute_scores(m)
            results.append(m)
        except Exception:
            # Never crash on a single file; silently skip it
            continue

    # Signal completion
    if on_progress:
        on_progress("", total, total)

    # Sort worst-first
    results.sort(key=lambda m: m.composite_score)

    # Apply min_score filter
    if min_score is not None:
        results = [m for m in results if m.composite_score < min_score]

    # Apply top limit
    if top > 0:
        results = results[:top]

    return results
