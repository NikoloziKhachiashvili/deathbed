"""GitPython helpers for extracting per-file history."""

from __future__ import annotations

import ast
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
    repo: git.Repo,
    rel_path: str,
    before_ts: Optional[int] = None,
) -> tuple[int, int, int, int, int]:
    """
    Return (days_since_last_commit, commit_count, author_count,
            recent_churn, prev_churn) for a file.

    If before_ts is given, only commits at or before that Unix timestamp
    are considered (for --diff historical analysis).

    recent_churn = commits in the last 90 days (relative to before_ts or now).
    prev_churn   = commits in the 90 days before that.
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

    # Cap at before_ts if provided
    if before_ts is not None:
        entries = [(ts, a) for ts, a in entries if ts <= before_ts]
        if not entries:
            return 0, 0, 0, 0, 0

    now = before_ts if before_ts is not None else int(time.time())
    ninety_days = 90 * 86400

    latest_ts = entries[0][0]
    days = max(0, (now - latest_ts) // 86400)
    commit_count = len(entries)
    author_count = len({a for _, a in entries})

    recent_cutoff = now - ninety_days
    prev_cutoff = now - 2 * ninety_days
    recent_churn = sum(1 for ts, _ in entries if ts >= recent_cutoff)
    prev_churn   = sum(1 for ts, _ in entries if prev_cutoff <= ts < recent_cutoff)

    return days, commit_count, author_count, recent_churn, prev_churn


def get_ref_timestamp(repo: git.Repo, ref: str) -> int:
    """Return the Unix commit timestamp of a git ref."""
    try:
        ts_str = repo.git.log(ref, "-1", "--format=%at")
        return int(ts_str.strip())
    except Exception:
        return int(time.time())


def _check_test_assertions(fpath: Path) -> bool:
    """
    Return True if the file contains at least one assert statement.
    Non-Python test files always return True (assume they have assertions).
    """
    if fpath.suffix.lower() != ".py":
        return True
    try:
        source = fpath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                return True
        return False
    except Exception:
        return True  # parse error → assume assertions exist


def find_test_file(repo_root: Path, rel_path: Path) -> tuple[bool, bool, bool]:
    """
    Look for a corresponding test file anywhere in the repo.
    Returns (has_test, is_recent, has_assertions) where:
      - has_test:        a matching test file was found
      - is_recent:       the test file was modified within 90 days
      - has_assertions:  the test file contains at least one assert statement
                         (always True when has_test is False)
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
                    return True, is_recent, _check_test_assertions(fpath)
            # check if file is in a test dir and has the stem in the name
            if dir_p.name in test_dirs and stem.lower() in lower:
                fpath = dir_p / fname
                try:
                    mtime = fpath.stat().st_mtime
                    is_recent = (now - mtime) < ninety_days
                except OSError:
                    is_recent = False
                return True, is_recent, _check_test_assertions(fpath)

    return False, False, True


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


# ── Dangerous pattern detection ───────────────────────────────────────────────

_DANGEROUS_MODULES = {"pickle", "cPickle", "marshal", "shelve"}
_DANGEROUS_BUILTINS = {"eval", "exec", "compile"}
_DANGEROUS_OS_ATTRS = {"system", "popen", "startfile"}
_SUBPROCESS_FUNCS   = {"call", "run", "Popen", "check_call", "check_output"}


def detect_security_smells(abs_path: Path) -> list[str]:
    """
    Detect dangerous security patterns in a Python file via AST analysis.
    Returns a deduplicated list of smell descriptions (empty for non-Python).
    """
    if abs_path.suffix.lower() != ".py":
        return []

    try:
        source = abs_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(abs_path))
    except Exception:
        return []

    smells: list[str] = []

    for node in ast.walk(tree):
        # ── Dangerous imports ─────────────────────────────────────────────────
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in _DANGEROUS_MODULES:
                    smells.append(f"imports {top}")

        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if module in _DANGEROUS_MODULES:
                smells.append(f"imports {module}")

        # ── Dangerous calls ───────────────────────────────────────────────────
        elif isinstance(node, ast.Call):
            func = node.func

            # eval() / exec() / compile() as bare names
            if isinstance(func, ast.Name) and func.id in _DANGEROUS_BUILTINS:
                smells.append(f"calls {func.id}()")

            elif isinstance(func, ast.Attribute):
                # os.system() / os.popen() etc.
                if (
                    isinstance(func.value, ast.Name)
                    and func.value.id == "os"
                    and func.attr in _DANGEROUS_OS_ATTRS
                ):
                    smells.append(f"calls os.{func.attr}()")

                # subprocess.*(shell=True)
                elif func.attr in _SUBPROCESS_FUNCS:
                    for kw in node.keywords:
                        if (
                            kw.arg == "shell"
                            and isinstance(kw.value, ast.Constant)
                            and kw.value.value is True
                        ):
                            smells.append(f"subprocess.{func.attr}(shell=True)")
                            break

    # Deduplicate while preserving order
    return list(dict.fromkeys(smells))


# ── Blame helpers ─────────────────────────────────────────────────────────────

def get_last_author(repo: git.Repo, rel_path: str) -> tuple[str, str]:
    """Return (author_name, commit_subject) of the most recent commit for a file."""
    try:
        raw = repo.git.log(
            "--follow", "-1",
            "--format=%an\x1f%s",
            "--",
            rel_path,
        )
        if "\x1f" in raw:
            name, subject = raw.strip().split("\x1f", 1)
            return name.strip(), subject.strip()
    except Exception:
        pass
    return "", ""


def get_changed_files_since(repo: git.Repo, since_ref: str) -> set[str]:
    """Return the set of file paths (POSIX) changed between since_ref and HEAD."""
    try:
        raw = repo.git.diff("--name-only", f"{since_ref}...HEAD")
        return {line.strip() for line in raw.splitlines() if line.strip()}
    except Exception:
        return set()


# ── Vulture dead-code detection ───────────────────────────────────────────────

def run_vulture(abs_path: Path) -> int:
    """
    Run vulture on a Python file and return the count of high-confidence
    unused functions, classes, and variables.
    Returns 0 for non-Python files or if vulture is unavailable / fails.
    """
    if abs_path.suffix.lower() != ".py":
        return 0
    try:
        import vulture as _vlt  # noqa: F401
        from vulture import Vulture

        source = abs_path.read_text(encoding="utf-8", errors="replace")
        v = Vulture(min_confidence=80)
        v.scan(source, filename=str(abs_path))
        unused = list(v.get_unused_code(min_confidence=80))
        return sum(
            1 for item in unused
            if getattr(item, "typ", "") in ("function", "class", "variable")
        )
    except ImportError:
        return 0
    except Exception:
        return 0
