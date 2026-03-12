"""Multi-repo org-wide health analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .analyzer import analyze_repo
from .git_utils import open_repo
from .scoring import compute_repo_score, letter_grade


@dataclass
class OrgRepoStats:
    name: str          # directory name
    path: Path         # absolute path
    repo_score: int    # 0-100
    grade: str         # A-F
    critical_count: int
    warning_count: int
    file_count: int
    worst_file: str    # rel-path of worst-scoring file
    worst_score: int   # score of worst file
    error: str = ""    # non-empty if analysis failed


def analyze_org(
    org_path: Path,
    top_per_repo: int = 50,
) -> list[OrgRepoStats]:
    """
    Scan every immediate subdirectory of org_path that is a git repo.

    Returns a list of OrgRepoStats sorted worst-first (lowest repo_score first).
    Non-git subdirectories are silently skipped.
    """
    stats_list: list[OrgRepoStats] = []

    try:
        subdirs = sorted(org_path.iterdir())
    except OSError:
        return stats_list

    for subdir in subdirs:
        if not subdir.is_dir():
            continue

        # Is it a git repo?
        try:
            open_repo(subdir)
        except Exception:
            continue

        try:
            results = analyze_repo(subdir, top=0, quiet=True)
            repo_score = compute_repo_score(results)
            grade = letter_grade(repo_score)
            critical = sum(1 for m in results if m.status == "CRITICAL")
            warning  = sum(1 for m in results if m.status == "WARNING")
            worst    = results[0] if results else None

            stats_list.append(OrgRepoStats(
                name=subdir.name,
                path=subdir,
                repo_score=repo_score,
                grade=grade,
                critical_count=critical,
                warning_count=warning,
                file_count=len(results),
                worst_file=worst.path if worst else "",
                worst_score=worst.composite_score if worst else 100,
            ))
        except Exception as exc:
            stats_list.append(OrgRepoStats(
                name=subdir.name,
                path=subdir,
                repo_score=0,
                grade="F",
                critical_count=0,
                warning_count=0,
                file_count=0,
                worst_file="",
                worst_score=0,
                error=str(exc),
            ))

    # Sort worst-first
    stats_list.sort(key=lambda s: s.repo_score)
    return stats_list


def org_combined_score(repos: list[OrgRepoStats]) -> int:
    """Compute an org-wide combined score (simple average of repo scores)."""
    valid = [r for r in repos if not r.error]
    if not valid:
        return 0
    return int(sum(r.repo_score for r in valid) / len(valid))
