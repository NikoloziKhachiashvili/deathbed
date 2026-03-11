"""Tests for git_utils.py — security detection, vulture, count_lines."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from deathbed.git_utils import (
    count_lines,
    detect_security_smells,
    run_vulture,
)


# ── count_lines ───────────────────────────────────────────────────────────────

def test_count_lines_basic(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("line1\nline2\nline3\n", encoding="utf-8")
    assert count_lines(f) == 3


def test_count_lines_no_trailing_newline(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("line1\nline2", encoding="utf-8")
    assert count_lines(f) == 2


def test_count_lines_empty(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("", encoding="utf-8")
    assert count_lines(f) == 0


def test_count_lines_missing():
    assert count_lines(Path("/nonexistent/file.py")) == 0


# ── detect_security_smells ────────────────────────────────────────────────────

def _py(tmp_path, content: str) -> Path:
    f = tmp_path / "test_file.py"
    f.write_text(textwrap.dedent(content), encoding="utf-8")
    return f


def test_no_smells_clean_code(tmp_path):
    f = _py(tmp_path, """
        def hello():
            print("hi")
    """)
    assert detect_security_smells(f) == []


def test_detects_pickle_import(tmp_path):
    f = _py(tmp_path, "import pickle\n")
    smells = detect_security_smells(f)
    assert any("pickle" in s for s in smells)


def test_detects_from_pickle_import(tmp_path):
    f = _py(tmp_path, "from pickle import loads\n")
    smells = detect_security_smells(f)
    assert any("pickle" in s for s in smells)


def test_detects_eval(tmp_path):
    f = _py(tmp_path, "x = eval(user_input)\n")
    smells = detect_security_smells(f)
    assert any("eval" in s for s in smells)


def test_detects_exec(tmp_path):
    f = _py(tmp_path, "exec(code)\n")
    smells = detect_security_smells(f)
    assert any("exec" in s for s in smells)


def test_detects_os_system(tmp_path):
    f = _py(tmp_path, "import os\nos.system('rm -rf /')\n")
    smells = detect_security_smells(f)
    assert any("os.system" in s for s in smells)


def test_detects_subprocess_shell_true(tmp_path):
    f = _py(tmp_path, "import subprocess\nsubprocess.run('ls', shell=True)\n")
    smells = detect_security_smells(f)
    assert any("shell=True" in s for s in smells)


def test_no_false_positive_subprocess_shell_false(tmp_path):
    f = _py(tmp_path, "import subprocess\nsubprocess.run(['ls'], shell=False)\n")
    smells = detect_security_smells(f)
    assert not any("shell=True" in s for s in smells)


def test_non_python_file_returns_empty(tmp_path):
    f = tmp_path / "index.js"
    f.write_text("eval('bad')\n", encoding="utf-8")
    assert detect_security_smells(f) == []


def test_syntax_error_file_returns_empty(tmp_path):
    f = _py(tmp_path, "def broken(\n")
    assert detect_security_smells(f) == []


def test_multiple_smells_deduplicated(tmp_path):
    f = _py(tmp_path, """
        import pickle
        import pickle
        x = eval('x')
    """)
    smells = detect_security_smells(f)
    pickle_mentions = [s for s in smells if "pickle" in s]
    assert len(pickle_mentions) == 1


def test_detects_marshal(tmp_path):
    f = _py(tmp_path, "import marshal\n")
    smells = detect_security_smells(f)
    assert any("marshal" in s for s in smells)


# ── run_vulture ───────────────────────────────────────────────────────────────

def test_run_vulture_non_python(tmp_path):
    f = tmp_path / "index.js"
    f.write_text("function dead() {}\n", encoding="utf-8")
    assert run_vulture(f) == 0


def test_run_vulture_clean_python(tmp_path):
    # A file with everything used shouldn't flag much
    f = tmp_path / "used.py"
    f.write_text("def hello():\n    return 42\nhello()\n", encoding="utf-8")
    result = run_vulture(f)
    assert isinstance(result, int)
    assert result >= 0


def test_run_vulture_returns_int_on_error(tmp_path):
    f = tmp_path / "broken.py"
    f.write_text("def broken(\n", encoding="utf-8")
    assert run_vulture(f) == 0


def test_run_vulture_missing_file():
    assert run_vulture(Path("/nonexistent/file.py")) == 0
