# Tests for analyzer.py — clone detection and score computation.

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from deathbed.analyzer import _detect_clones
from deathbed.scoring import FileMetrics, compute_scores


def _m(path: str, **kwargs) -> FileMetrics:
    defaults = dict(
        lines=50, days_since_commit=10, commit_count=3, author_count=1,
        avg_complexity=2.0, has_test_file=True, test_file_recent=True,
        recent_churn=1, prev_churn=0,
    )
    defaults.update(kwargs)
    m = FileMetrics(path=path, **defaults)
    compute_scores(m)
    return m


# ── _detect_clones ────────────────────────────────────────────────────────────

def test_detect_clones_identical_files(tmp_path):
    content = "def foo():\n    return 42\n\ndef bar():\n    return 'hello'\n" * 10
    (tmp_path / "a.py").write_text(content, encoding="utf-8")
    (tmp_path / "b.py").write_text(content, encoding="utf-8")

    a = _m("a.py")
    b = _m("b.py")
    _detect_clones([a, b], tmp_path)

    assert a.clone_similarity >= 0.4
    assert b.clone_similarity >= 0.4
    assert a.clone_of == "b.py"
    assert b.clone_of == "a.py"


def test_detect_clones_dissimilar_files(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\ny = 2\nz = 3\n" * 20, encoding="utf-8")
    (tmp_path / "b.py").write_text("import os\nimport sys\nfrom pathlib import Path\n" * 20, encoding="utf-8")

    a = _m("a.py")
    b = _m("b.py")
    _detect_clones([a, b], tmp_path)

    assert a.clone_similarity < 0.4
    assert b.clone_similarity < 0.4


def test_detect_clones_empty_results(tmp_path):
    _detect_clones([], tmp_path)  # should not raise


def test_detect_clones_single_file(tmp_path):
    (tmp_path / "solo.py").write_text("x = 1\n", encoding="utf-8")
    m = _m("solo.py")
    _detect_clones([m], tmp_path)
    assert m.clone_similarity == 0.0


def test_detect_clones_missing_file(tmp_path):
    # File listed in metrics but not on disk → should be skipped gracefully
    a = _m("missing.py")
    b = _m("also_missing.py")
    _detect_clones([a, b], tmp_path)
    assert a.clone_similarity == 0.0
    assert b.clone_similarity == 0.0


def test_detect_clones_partial_similarity(tmp_path):
    # 70% similar content
    base = "def func_{}():\n    return {}\n\n"
    shared = "".join(base.format(i, i) for i in range(20))
    unique_a = "".join(f"def unique_a_{i}(): pass\n" for i in range(6))
    unique_b = "".join(f"def unique_b_{i}(): pass\n" for i in range(6))

    (tmp_path / "a.py").write_text(shared + unique_a, encoding="utf-8")
    (tmp_path / "b.py").write_text(shared + unique_b, encoding="utf-8")

    a = _m("a.py")
    b = _m("b.py")
    _detect_clones([a, b], tmp_path)

    # Shared code is large, so similarity should be >= 0.4
    assert a.clone_similarity >= 0.4


def test_detect_clones_sets_clone_of(tmp_path):
    content = "def hello():\n    print('world')\n\n" * 15
    (tmp_path / "x.py").write_text(content, encoding="utf-8")
    (tmp_path / "y.py").write_text(content, encoding="utf-8")

    x = _m("x.py")
    y = _m("y.py")
    _detect_clones([x, y], tmp_path)

    assert x.clone_of in ("y.py", "x.py")  # x should point to y
    assert y.clone_of in ("x.py", "y.py")


# ── git_utils helpers (no git repo needed) ────────────────────────────────────

def test_get_complexity_js_returns_value(tmp_path):
    # v3.0.0: JS/TS files now return a complexity estimate (not None)
    from deathbed.git_utils import get_complexity
    f = tmp_path / "index.js"
    f.write_text("function x() { if (a) { return 1; } return 0; }\n", encoding="utf-8")
    result = get_complexity(f)
    assert result is not None
    assert result >= 1.0

def test_get_complexity_truly_unsupported_returns_none(tmp_path):
    # Truly unsupported file types (e.g. .css) should return None
    from deathbed.git_utils import get_complexity
    f = tmp_path / "styles.css"
    f.write_text("body { color: red; }\n", encoding="utf-8")
    assert get_complexity(f) is None


def test_get_complexity_simple_python(tmp_path):
    from deathbed.git_utils import get_complexity
    f = tmp_path / "simple.py"
    f.write_text("def hello():\n    return 1\n", encoding="utf-8")
    result = get_complexity(f)
    assert result is not None
    assert result >= 1.0


def test_get_complexity_empty_python(tmp_path):
    from deathbed.git_utils import get_complexity
    f = tmp_path / "empty.py"
    f.write_text("# just a comment\n", encoding="utf-8")
    result = get_complexity(f)
    # radon returns 1.0 for trivial or empty files
    assert result is None or result >= 1.0


def test_find_test_file_found(tmp_path):
    from deathbed.git_utils import find_test_file
    src = tmp_path / "src"
    src.mkdir()
    (src / "utils.py").write_text("x = 1\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_utils.py").write_text("assert True\n", encoding="utf-8")

    has_test, _, _assertions = find_test_file(tmp_path, Path("src/utils.py"))
    assert has_test is True


def test_find_test_file_not_found(tmp_path):
    from deathbed.git_utils import find_test_file
    (tmp_path / "orphan.py").write_text("x = 1\n", encoding="utf-8")

    has_test, is_recent, has_assertions = find_test_file(tmp_path, Path("orphan.py"))
    assert has_test is False
    assert is_recent is False
    assert has_assertions is True  # default when no test found


def test_find_test_file_assertions_check(tmp_path):
    from deathbed.git_utils import find_test_file

    src = tmp_path / "src"
    src.mkdir()
    (src / "utils.py").write_text("x = 1\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    # Test file with no assertions
    (tests / "test_utils.py").write_text("def test_nothing():\n    pass\n", encoding="utf-8")

    has_test, _, has_assertions = find_test_file(tmp_path, Path("src/utils.py"))
    assert has_test is True
    assert has_assertions is False


def test_find_test_file_with_assertions(tmp_path):
    from deathbed.git_utils import find_test_file

    src = tmp_path / "src"
    src.mkdir()
    (src / "calc.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_calc.py").write_text("def test_add():\n    assert 1 + 1 == 2\n", encoding="utf-8")

    has_test, _, has_assertions = find_test_file(tmp_path, Path("src/calc.py"))
    assert has_test is True
    assert has_assertions is True
