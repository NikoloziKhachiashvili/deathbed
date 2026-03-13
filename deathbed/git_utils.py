"""GitPython helpers for extracting per-file history."""

from __future__ import annotations

import ast
import contextlib
import logging
import os
import re
import subprocess
import time
from pathlib import Path

import git

log = logging.getLogger(__name__)

__all__ = [
    "open_repo",
    "get_repo_root",
    "count_lines",
    "get_file_history",
    "get_ref_timestamp",
    "find_test_file",
    "build_test_index",
    "get_complexity",
    "detect_security_smells",
    "get_last_author",
    "get_changed_files_since",
    "run_vulture",
]


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
    except OSError as exc:
        log.debug("Could not read %s: %s", abs_path, exc)
        return 0


def get_file_history(
    repo: git.Repo,
    rel_path: str,
    before_ts: int | None = None,
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
    except git.GitCommandError as exc:
        log.debug("git log failed for %s: %s", rel_path, exc)
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
    except (git.GitCommandError, ValueError) as exc:
        log.debug("get_ref_timestamp failed for %s: %s", ref, exc)
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
        return any(isinstance(node, ast.Assert) for node in ast.walk(tree))
    except (SyntaxError, OSError):
        return True  # parse error → assume assertions exist


def build_test_index(repo_root: Path) -> dict[str, Path]:
    """
    Walk the repo once and build a mapping of lowercased filename → absolute path
    for files that look like test files.

    A file is a test file if:
    - Its name starts with "test_" or contains "_test.", ".test.", or ".spec."
    - Or it lives inside a directory named tests/test/spec/__tests__/test_suite
    """
    test_dirs = {"tests", "test", "spec", "__tests__", "test_suite"}
    index: dict[str, Path] = {}

    for dirpath, _dirnames, filenames in os.walk(repo_root):
        dir_p = Path(dirpath)
        in_test_dir = dir_p.name in test_dirs

        for fname in filenames:
            lower = fname.lower()
            is_test_file = (
                lower.startswith("test_")
                or "_test." in lower
                or ".test." in lower
                or ".spec." in lower
                or in_test_dir
            )
            if is_test_file:
                index[lower] = dir_p / fname

    return index


def find_test_file(index: dict[str, Path], rel_path: Path) -> tuple[bool, bool, bool]:
    """
    Look for a corresponding test file using a pre-built index.
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

    now = time.time()
    ninety_days = 90 * 86400

    # Check exact candidates first
    for candidate in candidates:
        lower_candidate = candidate.lower()
        if lower_candidate in index:
            fpath = index[lower_candidate]
            try:
                mtime = fpath.stat().st_mtime
                is_recent = (now - mtime) < ninety_days
            except OSError:
                is_recent = False
            return True, is_recent, _check_test_assertions(fpath)

    # Also check any test file that starts with test_{stem}
    prefix = f"test_{stem}".lower()
    for lower_fname, fpath in index.items():
        if lower_fname.startswith(prefix):
            try:
                mtime = fpath.stat().st_mtime
                is_recent = (now - mtime) < ninety_days
            except OSError:
                is_recent = False
            return True, is_recent, _check_test_assertions(fpath)

    # Check any test file in a test dir that contains the stem
    stem_lower = stem.lower()
    for lower_fname, fpath in index.items():
        if stem_lower in lower_fname:
            test_dirs = {"tests", "test", "spec", "__tests__", "test_suite"}
            if fpath.parent.name in test_dirs:
                try:
                    mtime = fpath.stat().st_mtime
                    is_recent = (now - mtime) < ninety_days
                except OSError:
                    is_recent = False
                return True, is_recent, _check_test_assertions(fpath)

    return False, False, True


def _get_complexity_python(abs_path: Path) -> float | None:
    """
    Run radon cyclomatic complexity on a Python file.
    Returns average complexity or None if not applicable / radon fails.
    """
    try:
        from radon.complexity import cc_visit

        source = abs_path.read_text(encoding="utf-8", errors="replace")
        results = cc_visit(source)
        if not results:
            return 1.0  # trivially simple
        return sum(r.complexity for r in results) / len(results)
    except ImportError as exc:
        log.debug("radon not available: %s", exc)
        return None
    except Exception as exc:
        log.debug("Python complexity failed for %s: %s", abs_path, exc)
        return None


def _get_complexity_js(abs_path: Path) -> float | None:
    """Estimate JS/TS complexity via control flow keyword counting."""
    try:
        source = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        log.debug("Could not read %s: %s", abs_path, exc)
        return None
    func_count = max(1, len(re.findall(
        r'(?:function\s+\w+\s*\(|(?:^|\s)(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\([^)]*\)\s*=>|\b(?:async\s+)?function\s*\()',
        source, re.MULTILINE,
    )))
    cc_points = len(re.findall(
        r'\b(?:if|else\s+if|while|for|switch|case(?=\s)|catch)\b|\?\s*[^:?\n]+:|(?<!\|)\|\|(?!\|)|(?<!&)&&(?!&)',
        source,
    ))
    return max(1.0, (cc_points / func_count) + 1.0)


def _get_complexity_go(abs_path: Path) -> float | None:
    """Run gocyclo on a Go file. Returns average complexity or None if unavailable."""
    try:
        result = subprocess.run(
            ["gocyclo", str(abs_path)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None
        complexities = []
        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if parts:
                with contextlib.suppress(ValueError):
                    complexities.append(int(parts[0]))
        if not complexities:
            return None
        return sum(complexities) / len(complexities)
    except FileNotFoundError:
        log.debug("gocyclo not found; skipping Go complexity for %s", abs_path)
        return None
    except subprocess.TimeoutExpired:
        log.debug("gocyclo timed out for %s", abs_path)
        return None
    except Exception as exc:
        log.debug("Go complexity failed for %s: %s", abs_path, exc)
        return None


def _get_complexity_rust(abs_path: Path) -> float | None:
    """Count match arms and control flow as a Rust complexity proxy."""
    try:
        source = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        log.debug("Could not read %s: %s", abs_path, exc)
        return None
    func_count = max(1, len(re.findall(r'\bfn\s+\w+', source)))
    cc_points = len(re.findall(
        r'\b(?:if|else\s+if|while|for\s+\w|loop|match)\b|=>', source
    ))
    return max(1.0, cc_points / func_count)


def detect_dead_code_rust(abs_path: Path) -> int:
    """Count #[allow(dead_code)] annotations as a dead code signal."""
    try:
        source = abs_path.read_text(encoding="utf-8", errors="replace")
        return len(re.findall(r'#\[allow\(dead_code\)\]', source))
    except OSError as exc:
        log.debug("Could not read %s: %s", abs_path, exc)
        return 0


def get_complexity(abs_path: Path) -> float | None:
    """
    Return cyclomatic complexity for the given source file.
    Dispatches to language-specific implementations.
    Returns None if language not supported or analysis fails.
    """
    suffix = abs_path.suffix.lower()
    if suffix == ".py":
        return _get_complexity_python(abs_path)
    if suffix in (".js", ".ts", ".jsx", ".tsx"):
        return _get_complexity_js(abs_path)
    if suffix == ".go":
        return _get_complexity_go(abs_path)
    if suffix == ".rs":
        return _get_complexity_rust(abs_path)
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
    except (SyntaxError, OSError) as exc:
        log.debug("Security smell detection failed for %s: %s", abs_path, exc)
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
    except (git.GitCommandError, ValueError) as exc:
        log.debug("get_last_author failed for %s: %s", rel_path, exc)
    return "", ""


def get_changed_files_since(repo: git.Repo, since_ref: str) -> set[str]:
    """Return the set of file paths (POSIX) changed between since_ref and HEAD."""
    try:
        raw = repo.git.diff("--name-only", f"{since_ref}...HEAD")
        return {line.strip() for line in raw.splitlines() if line.strip()}
    except git.GitCommandError as exc:
        log.debug("get_changed_files_since failed for %s: %s", since_ref, exc)
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
    except Exception as exc:
        log.debug("vulture failed for %s: %s", abs_path, exc)
        return 0
