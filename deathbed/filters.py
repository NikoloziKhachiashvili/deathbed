"""File discovery, gitignore filtering, and binary detection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pathspec

# Extensions we want to analyze
ANALYZABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".go", ".rs", ".rb", ".java",
    ".cpp", ".c", ".cs", ".php",
    ".swift", ".kt",
}

# Directories to always skip
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "venv", ".venv",
    "env", ".env", "dist", "build", "target", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "vendor", "third_party",
    ".idea", ".vscode", "coverage", "htmlcov", ".tox",
}

# File name patterns to always skip
SKIP_PATTERNS = {
    "*.min.js", "*.min.css", "*.lock", "package-lock.json",
    "yarn.lock", "Pipfile.lock", "poetry.lock", "Cargo.lock",
}


def _load_gitignore(repo_path: Path) -> pathspec.PathSpec:
    """Load .gitignore from repo root into a PathSpec."""
    patterns: list[str] = []
    gitignore = repo_path / ".gitignore"
    if gitignore.is_file():
        try:
            patterns = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            pass
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def _is_binary(path: Path) -> bool:
    """Heuristic binary check: look for null bytes in first 8 KB."""
    try:
        chunk = path.read_bytes()[:8192]
        return b"\x00" in chunk
    except OSError:
        return True


def get_analyzable_files(repo_path: Path) -> list[Path]:
    """
    Return a sorted list of relative Paths (relative to repo_path) that
    should be analyzed. Respects .gitignore, skips binaries, locked dirs,
    and unsupported extensions.
    """
    spec = _load_gitignore(repo_path)
    results: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(repo_path):
        dir_abs = Path(dirpath)
        rel_dir = dir_abs.relative_to(repo_path)

        # Prune directories in-place
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS
            and not d.startswith(".")
            and not spec.match_file(str(rel_dir / d) + "/")
        ]

        for fname in filenames:
            file_abs = dir_abs / fname
            rel_path = file_abs.relative_to(repo_path)
            rel_str = rel_path.as_posix()

            # Extension check
            if file_abs.suffix.lower() not in ANALYZABLE_EXTENSIONS:
                continue

            # Gitignore check
            if spec.match_file(rel_str):
                continue

            # Binary check (cheap: only reads 8 KB)
            if _is_binary(file_abs):
                continue

            results.append(rel_path)

    return sorted(results, key=lambda p: p.as_posix())
