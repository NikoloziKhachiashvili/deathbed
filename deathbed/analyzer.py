"""Orchestrates per-file metric collection and scoring."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, Optional

import git

from .filters import get_analyzable_files
from .git_utils import (
    count_lines,
    detect_security_smells,
    find_test_file,
    get_changed_files_since,
    get_complexity,
    get_file_history,
    get_last_author,
    get_ref_timestamp,
    get_repo_root,
    open_repo,
    run_vulture,
)
from .scoring import FileMetrics, compute_scores


@dataclass
class AuthorStats:
    author: str
    files_owned: int
    avg_score: float
    critical_count: int
    warning_count: int
    grade: str


def analyze_repo(
    repo_path: Path,
    top: int = 50,
    min_score: Optional[int] = None,
    quiet: bool = False,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
    since_ref: Optional[str] = None,
    include_blame: bool = False,
    _meta: Optional[dict] = None,
) -> list[FileMetrics]:
    """
    Analyze a git repository and return scored FileMetrics, worst-first.

    Args:
        repo_path:     Path to the repo (or any subdir).
        top:           Return at most N results (0 = unlimited).
        min_score:     Only return files with composite_score < min_score.
        quiet:         Suppress internal prints.
        on_progress:   Callback(rel_path, current_index, total) called per file.
        since_ref:     If given, restrict analysis to files changed since this ref
                       (PR mode).
        include_blame: If True, populate last_author / last_commit_msg per file.
        _meta:         Optional dict that gets populated with repo_root,
                       ignored_count, and since_count for the caller.

    Raises:
        git.InvalidGitRepositoryError: if path is not inside a git repo.
        git.NoSuchPathError:           if path does not exist.
    """
    repo = open_repo(repo_path)
    root = get_repo_root(repo)

    files, ignored_count = get_analyzable_files(root)

    # PR mode: restrict to files changed since the given ref
    if since_ref is not None:
        changed = get_changed_files_since(repo, since_ref)
        files = [f for f in files if f.as_posix() in changed]

    if _meta is not None:
        _meta["repo_root"]     = root
        _meta["ignored_count"] = ignored_count
        _meta["since_count"]   = len(files)

    total = len(files)
    results: list[FileMetrics] = []

    for idx, rel_path in enumerate(files):
        if on_progress:
            on_progress(str(rel_path), idx, total)

        abs_path = root / rel_path
        rel_str  = rel_path.as_posix()

        try:
            lines                        = count_lines(abs_path)
            days, commits, authors, recent_churn, prev_churn = get_file_history(repo, rel_str)
            avg_cx                       = get_complexity(abs_path)
            has_test, test_recent        = find_test_file(root, rel_path)
            dead_count                   = run_vulture(abs_path)
            sec_smells                   = detect_security_smells(abs_path)

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
                dead_code_count=dead_count,
                has_security_smell=bool(sec_smells),
                security_smells=sec_smells,
            )
            compute_scores(m)

            if include_blame:
                m.last_author, m.last_commit_msg = get_last_author(repo, rel_str)

            results.append(m)
        except Exception:
            # Never crash on a single file; silently skip it
            continue

    # Signal completion
    if on_progress:
        on_progress("", total, total)

    # Clone detection (after all files are scored)
    _detect_clones(results, root)

    # Re-diagnose after clone data is set (clone_similarity may change diagnosis)
    from .scoring import _diagnose  # noqa: PLC0415
    for m in results:
        m.diagnosis = _diagnose(m)

    # Sort worst-first
    results.sort(key=lambda m: m.composite_score)

    # Apply min_score filter
    if min_score is not None:
        results = [m for m in results if m.composite_score < min_score]

    # Apply top limit
    if top > 0:
        results = results[:top]

    return results


def _detect_clones(results: list[FileMetrics], root: Path) -> None:
    """
    Compute pairwise similarity between files and populate clone_similarity /
    clone_of on each FileMetrics in-place.

    Uses difflib line-level comparison, capped at 200 files to stay O(n²) fast.
    Only sets clone_similarity when the ratio exceeds 0.40 (40%).
    """
    # Read and normalise file contents (strip blank lines + comments)
    contents: dict[str, list[str]] = {}
    for m in results:
        abs_path = root / m.path
        try:
            raw = abs_path.read_text(encoding="utf-8", errors="replace")
            lines = [
                ln.strip() for ln in raw.splitlines()
                if ln.strip() and not ln.strip().startswith(("#", "//", "/*", "*"))
            ]
            if lines:
                contents[m.path] = lines
        except Exception:
            pass

    paths = list(contents.keys())
    n = min(len(paths), 200)   # cap to keep it fast
    paths = paths[:n]

    best: dict[str, tuple[float, str]] = {}  # path -> (max_sim, other_path)

    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            a, b = paths[i], paths[j]
            la, lb = contents[a], contents[b]

            # Quick ratio is an upper bound; skip if clearly below threshold
            matcher = SequenceMatcher(None, la, lb, autojunk=False)
            if matcher.quick_ratio() < 0.35:
                continue

            ratio = matcher.ratio()
            if ratio < 0.40:
                continue

            if ratio > best.get(a, (0.0, ""))[0]:
                best[a] = (ratio, b)
            if ratio > best.get(b, (0.0, ""))[0]:
                best[b] = (ratio, a)

    for m in results:
        if m.path in best:
            m.clone_similarity, m.clone_of = best[m.path]


def analyze_diff(
    repo_path: Path,
    ref: str,
    top: int = 50,
    min_score: Optional[int] = None,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> tuple[list[FileMetrics], list[FileMetrics]]:
    """
    Analyze the repo at HEAD (current) and at a historical ref.

    Returns (current_results, historical_results), both sorted worst-first.
    Historical results use the same file list but cap git history at the ref's
    commit timestamp.
    """
    repo     = open_repo(repo_path)
    root     = get_repo_root(repo)
    before_ts = get_ref_timestamp(repo, ref)

    files, _ = get_analyzable_files(root)
    total = len(files)

    current_results:    list[FileMetrics] = []
    historical_results: list[FileMetrics] = []

    for idx, rel_path in enumerate(files):
        if on_progress:
            on_progress(str(rel_path), idx, total)

        abs_path = root / rel_path
        rel_str  = rel_path.as_posix()

        try:
            lines                        = count_lines(abs_path)
            avg_cx                       = get_complexity(abs_path)
            has_test, test_recent        = find_test_file(root, rel_path)
            dead_count                   = run_vulture(abs_path)
            sec_smells                   = detect_security_smells(abs_path)

            # Current (HEAD) history
            days, commits, authors, recent, prev = get_file_history(repo, rel_str)
            m_cur = FileMetrics(
                path=rel_str, lines=lines,
                days_since_commit=days, commit_count=commits, author_count=authors,
                avg_complexity=avg_cx, has_test_file=has_test,
                test_file_recent=test_recent, recent_churn=recent, prev_churn=prev,
                dead_code_count=dead_count,
                has_security_smell=bool(sec_smells), security_smells=sec_smells,
            )
            compute_scores(m_cur)
            current_results.append(m_cur)

            # Historical (at ref) history — same file, capped at before_ts
            h_days, h_commits, h_authors, h_recent, h_prev = get_file_history(
                repo, rel_str, before_ts=before_ts
            )
            m_hist = FileMetrics(
                path=rel_str, lines=lines,
                days_since_commit=h_days, commit_count=h_commits, author_count=h_authors,
                avg_complexity=avg_cx, has_test_file=has_test,
                test_file_recent=test_recent, recent_churn=h_recent, prev_churn=h_prev,
                dead_code_count=dead_count,
                has_security_smell=bool(sec_smells), security_smells=sec_smells,
            )
            compute_scores(m_hist)
            historical_results.append(m_hist)

        except Exception:
            continue

    if on_progress:
        on_progress("", total, total)

    # Clone detection on current state
    _detect_clones(current_results, root)
    from .scoring import _diagnose  # noqa: PLC0415
    for m in current_results:
        m.diagnosis = _diagnose(m)

    # Sort & filter current results
    current_results.sort(key=lambda m: m.composite_score)
    if min_score is not None:
        current_results = [m for m in current_results if m.composite_score < min_score]
    if top > 0:
        current_results = current_results[:top]

    historical_results.sort(key=lambda m: m.composite_score)

    return current_results, historical_results


def analyze_leaderboard(
    repo_path: Path,
    top: Optional[int] = None,
) -> list[AuthorStats]:
    """
    Compute per-author stats based on last-author ownership.

    Calls analyze_repo internally with include_blame=True and aggregates
    the results by author.  Returns a list sorted by critical_count descending,
    then avg_score ascending (most-at-risk authors first).
    """
    from .scoring import letter_grade

    results = analyze_repo(repo_path, top=0, include_blame=True)

    author_data: dict[str, list[FileMetrics]] = {}
    for m in results:
        if m.last_author:
            author_data.setdefault(m.last_author, []).append(m)

    stats_list: list[AuthorStats] = []
    for author, metrics in author_data.items():
        avg_score = sum(m.composite_score for m in metrics) / len(metrics)
        stats_list.append(AuthorStats(
            author=author,
            files_owned=len(metrics),
            avg_score=avg_score,
            critical_count=sum(1 for m in metrics if m.status == "CRITICAL"),
            warning_count=sum(1 for m in metrics if m.status == "WARNING"),
            grade=letter_grade(int(avg_score)),
        ))

    stats_list.sort(key=lambda s: (-s.critical_count, s.avg_score))
    if top and top > 0:
        stats_list = stats_list[:top]
    return stats_list
