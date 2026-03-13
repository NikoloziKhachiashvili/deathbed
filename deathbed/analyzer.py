"""Orchestrates per-file metric collection and scoring."""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

from .filters import get_analyzable_files
from .git_utils import (
    build_test_index,
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

log = logging.getLogger(__name__)

__all__ = ["analyze_repo", "analyze_diff", "analyze_leaderboard", "AuthorStats"]

# ── Regex patterns for cross-language import extraction ───────────────────────

_JS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*?\s+from\s+|require\s*\(\s*)['"]([^'"]+)['"]""",
    re.MULTILINE,
)
_GENERIC_IMPORT_RE = re.compile(
    r"""import\s+["']?([^\s"';(]+)["']?""",
    re.MULTILINE,
)


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
    min_score: int | None = None,
    quiet: bool = False,
    on_progress: Callable[[str, int, int], None] | None = None,
    since_ref: str | None = None,
    include_blame: bool = False,
    _meta: dict | None = None,
) -> list[FileMetrics]:
    """
    Analyze a git repository and return scored FileMetrics, worst-first.

    Args:
        repo_path:     Path to the repo (or any subdir).
        top:           Return at most N results (0 = unlimited).
        min_score:     Only return files with composite_score < min_score.
        quiet:         Suppress internal prints.
        on_progress:   Callback(rel_path, current_index, total) called per file.
        since_ref:     If given, restrict analysis to files changed since this ref.
        include_blame: If True, populate last_author / last_commit_msg per file.
        _meta:         Optional dict populated with repo_root, ignored_count,
                       and since_count for the caller.

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

    # Build test index once for O(1) per-file lookup
    test_index = build_test_index(root)

    for idx, rel_path in enumerate(files):
        if on_progress:
            on_progress(str(rel_path), idx, total)

        abs_path = root / rel_path
        rel_str  = rel_path.as_posix()

        try:
            lines                                  = count_lines(abs_path)
            days, commits, authors, recent, prev   = get_file_history(repo, rel_str)
            avg_cx                                 = get_complexity(abs_path)
            has_test, test_recent, test_has_assert = find_test_file(test_index, rel_path)
            dead_count                             = run_vulture(abs_path)
            sec_smells                             = detect_security_smells(abs_path)

            m = FileMetrics(
                path=rel_str,
                lines=lines,
                days_since_commit=days,
                commit_count=commits,
                author_count=authors,
                avg_complexity=avg_cx,
                has_test_file=has_test,
                test_file_recent=test_recent,
                test_has_assertions=test_has_assert,
                recent_churn=recent,
                prev_churn=prev,
                dead_code_count=dead_count,
                has_security_smell=bool(sec_smells),
                security_smells=sec_smells,
            )
            compute_scores(m)

            if include_blame:
                m.last_author, m.last_commit_msg = get_last_author(repo, rel_str)

            results.append(m)
        except Exception as exc:
            # Never crash on a single file; log and skip
            log.debug("Skipping %s: %s", rel_str, exc)
            continue

    # Signal completion
    if on_progress:
        on_progress("", total, total)

    # Clone detection (cross-file, O(n²) capped at 200 files)
    _detect_clones(results, root)

    # Coupling detection (cross-file: who imports whom)
    _detect_coupling(results, root)

    # Multi-language dead code detection (JS/TS/Go/Rust)
    _detect_dead_code_multilang(results, root)

    # Final re-score pass: coupling and dead-code data is now set, recompute everything
    for m in results:
        compute_scores(m)

    # Populate lang_counts in meta if requested
    if _meta is not None:
        lang_counts: dict = {}
        for m in results:
            ext = Path(m.path).suffix.lower().lstrip(".")
            lang_counts[ext] = lang_counts.get(ext, 0) + 1
        _meta["lang_counts"] = lang_counts

    # Sort worst-first
    results.sort(key=lambda m: m.composite_score)

    # Apply min_score filter
    if min_score is not None:
        results = [m for m in results if m.composite_score < min_score]

    # Apply top limit
    if top > 0:
        results = results[:top]

    return results


def _extract_imports(abs_path: Path) -> set[str]:
    """
    Extract the set of imported module/file stems from a source file.
    Returns stems (no extension) that could match local file paths.
    """
    try:
        source = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()

    stems: set[str] = set()
    suffix = abs_path.suffix.lower()

    if suffix == ".py":
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        parts = alias.name.split(".")
                        stems.add(parts[-1])
                        if len(parts) > 1:
                            stems.add(parts[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    stems.add(parts[-1])
                    if len(parts) > 1:
                        stems.add(parts[0])
        except SyntaxError:
            pass

    elif suffix in (".js", ".ts", ".jsx", ".tsx"):
        for match in _JS_IMPORT_RE.finditer(source):
            path_str = match.group(1)
            stem = Path(path_str).stem
            if stem and not stem.startswith("@"):
                stems.add(stem)

    else:
        for match in _GENERIC_IMPORT_RE.finditer(source):
            token = match.group(1)
            stem = Path(token).stem
            if stem:
                stems.add(stem)

    return stems


def _detect_coupling(results: list[FileMetrics], root: Path) -> None:
    """
    For each file, count how many other analyzed files import it.
    Populates coupling_count and importers on each FileMetrics in-place.
    """
    # Build map from stem → [rel_paths] (handles name collisions)
    stem_to_paths: dict[str, list[str]] = {}
    for m in results:
        stem = Path(m.path).stem
        stem_to_paths.setdefault(stem, []).append(m.path)

    # For each file, extract what it imports
    file_imports: dict[str, set[str]] = {}
    for m in results:
        file_imports[m.path] = _extract_imports(root / m.path)

    # Reverse: for each file, which other files import it?
    importers_map: dict[str, set[str]] = {m.path: set() for m in results}
    for importer_path, imported_stems in file_imports.items():
        for stem in imported_stems:
            for target_path in stem_to_paths.get(stem, []):
                if target_path != importer_path:
                    importers_map[target_path].add(importer_path)

    # Update FileMetrics
    for m in results:
        importer_set = importers_map.get(m.path, set())
        m.coupling_count = len(importer_set)
        m.importers = sorted(importer_set)[:5]


def _detect_clones(results: list[FileMetrics], root: Path) -> None:
    """
    Compute pairwise similarity between files and populate clone_similarity /
    clone_of on each FileMetrics in-place.

    Uses difflib line-level comparison, capped at 200 files to stay O(n²) fast.
    Only sets clone_similarity when the ratio exceeds 0.40 (40%).
    """
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
        except OSError:
            pass

    paths = list(contents.keys())
    total_files = len(paths)
    n = min(total_files, 200)
    if total_files > 200:
        log.info(
            "Clone detection capped at 200 files (%d total); some files excluded.",
            total_files,
        )
    paths = paths[:n]

    best: dict[str, tuple[float, str]] = {}

    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            a, b = paths[i], paths[j]
            la, lb = contents[a], contents[b]

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


def _detect_dead_code_multilang(results: list[FileMetrics], root: Path) -> None:
    """
    Supplement vulture dead-code counts with language-specific detection for
    JS/TS (TODO/FIXME comments as a proxy) and Rust (#[allow(dead_code)]).
    Only updates files where dead_code_count is currently 0 to avoid overwriting
    Python/vulture results.
    """
    from .git_utils import detect_dead_code_rust

    for m in results:
        suffix = Path(m.path).suffix.lower()
        if m.dead_code_count > 0:
            # Already has a count (e.g. from vulture) — leave it
            continue

        abs_path = root / m.path
        if suffix == ".rs":
            count = detect_dead_code_rust(abs_path)
            if count > 0:
                m.dead_code_count = count
        elif suffix in (".js", ".ts", ".jsx", ".tsx"):
            # Use TODO/FIXME/HACK/DEAD comment density as a dead-code proxy
            try:
                source = abs_path.read_text(encoding="utf-8", errors="replace")
                dead_markers = len(re.findall(
                    r'//\s*(?:TODO|FIXME|HACK|DEAD|UNUSED|REMOVE|DEPRECATED)',
                    source, re.IGNORECASE,
                ))
                if dead_markers > 0:
                    m.dead_code_count = dead_markers
            except OSError as exc:
                log.debug("Dead code detection failed for %s: %s", m.path, exc)


def analyze_diff(
    repo_path: Path,
    ref: str,
    top: int = 50,
    min_score: int | None = None,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> tuple[list[FileMetrics], list[FileMetrics]]:
    """
    Analyze the repo at HEAD (current) and at a historical ref.

    Returns (current_results, historical_results), both sorted worst-first.
    Historical results use the same file list but cap git history at the ref's
    commit timestamp.
    """
    repo      = open_repo(repo_path)
    root      = get_repo_root(repo)
    before_ts = get_ref_timestamp(repo, ref)

    files, _ = get_analyzable_files(root)
    total = len(files)

    current_results:    list[FileMetrics] = []
    historical_results: list[FileMetrics] = []

    # Build test index once
    test_index = build_test_index(root)

    for idx, rel_path in enumerate(files):
        if on_progress:
            on_progress(str(rel_path), idx, total)

        abs_path = root / rel_path
        rel_str  = rel_path.as_posix()

        try:
            lines                                  = count_lines(abs_path)
            avg_cx                                 = get_complexity(abs_path)
            has_test, test_recent, test_has_assert = find_test_file(test_index, rel_path)
            dead_count                             = run_vulture(abs_path)
            sec_smells                             = detect_security_smells(abs_path)

            # Current (HEAD) history
            days, commits, authors, recent, prev = get_file_history(repo, rel_str)
            m_cur = FileMetrics(
                path=rel_str, lines=lines,
                days_since_commit=days, commit_count=commits, author_count=authors,
                avg_complexity=avg_cx, has_test_file=has_test,
                test_file_recent=test_recent, test_has_assertions=test_has_assert,
                recent_churn=recent, prev_churn=prev,
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
                days_since_commit=h_days, commit_count=h_commits,
                author_count=h_authors, avg_complexity=avg_cx,
                has_test_file=has_test, test_file_recent=test_recent,
                test_has_assertions=test_has_assert,
                recent_churn=h_recent, prev_churn=h_prev,
                dead_code_count=dead_count,
                has_security_smell=bool(sec_smells), security_smells=sec_smells,
            )
            compute_scores(m_hist)
            historical_results.append(m_hist)

        except Exception as exc:
            log.debug("Skipping %s in diff: %s", rel_str, exc)
            continue

    if on_progress:
        on_progress("", total, total)

    # Clone + coupling detection on current state
    _detect_clones(current_results, root)
    _detect_coupling(current_results, root)
    for m in current_results:
        compute_scores(m)

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
    top: int | None = None,
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
