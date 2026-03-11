"""Tests for filters.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from deathbed.filters import (
    ANALYZABLE_EXTENSIONS,
    SKIP_DIRS,
    _is_binary,
    get_analyzable_files,
)


def test_is_binary_text_file(tmp_path):
    f = tmp_path / "code.py"
    f.write_text("hello world\n", encoding="utf-8")
    assert _is_binary(f) is False


def test_is_binary_null_bytes(tmp_path):
    f = tmp_path / "binary.bin"
    f.write_bytes(b"\x00\x01\x02hello")
    assert _is_binary(f) is True


def test_is_binary_missing():
    assert _is_binary(Path("/nonexistent/file")) is True


def test_analyzable_extensions_has_python():
    assert ".py" in ANALYZABLE_EXTENSIONS


def test_analyzable_extensions_has_js():
    assert ".js" in ANALYZABLE_EXTENSIONS


def test_skip_dirs_has_node_modules():
    assert "node_modules" in SKIP_DIRS


def test_get_analyzable_files_basic(tmp_path):
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "main.py").write_text("print('hi')\n", encoding="utf-8")

    files, ignored = get_analyzable_files(tmp_path)
    paths = [p.as_posix() for p in files]
    assert "src/main.py" in paths
    assert ignored == 0


def test_get_analyzable_files_skips_skip_dirs(tmp_path):
    node_mod = tmp_path / "node_modules"
    node_mod.mkdir()
    (node_mod / "dep.js").write_text("module.exports = {}\n", encoding="utf-8")

    files, _ = get_analyzable_files(tmp_path)
    paths = [p.as_posix() for p in files]
    assert not any("node_modules" in p for p in paths)


def test_get_analyzable_files_skips_binary(tmp_path):
    f = tmp_path / "binary.py"
    f.write_bytes(b"\x00\x01\x02")
    files, _ = get_analyzable_files(tmp_path)
    assert f.name not in [p.name for p in files]


def test_get_analyzable_files_skips_unknown_extension(tmp_path):
    (tmp_path / "notes.txt").write_text("hello\n", encoding="utf-8")
    files, _ = get_analyzable_files(tmp_path)
    assert not any(p.suffix == ".txt" for p in files)


def test_get_analyzable_files_respects_gitignore(tmp_path):
    (tmp_path / ".gitignore").write_text("secret.py\n", encoding="utf-8")
    (tmp_path / "secret.py").write_text("password = 'abc'\n", encoding="utf-8")
    (tmp_path / "public.py").write_text("x = 1\n", encoding="utf-8")

    files, _ = get_analyzable_files(tmp_path)
    names = [p.name for p in files]
    assert "secret.py" not in names
    assert "public.py" in names


def test_get_analyzable_files_sorted(tmp_path):
    (tmp_path / "z.py").write_text("z = 1\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("a = 1\n", encoding="utf-8")
    (tmp_path / "m.py").write_text("m = 1\n", encoding="utf-8")

    files, _ = get_analyzable_files(tmp_path)
    names = [p.name for p in files]
    assert names == sorted(names)


def test_get_analyzable_files_skips_hidden_dirs(tmp_path):
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "secret.py").write_text("x = 1\n", encoding="utf-8")
    files, _ = get_analyzable_files(tmp_path)
    assert not any(".hidden" in str(p) for p in files)


def test_get_analyzable_files_deathbedignore(tmp_path):
    (tmp_path / ".deathbedignore").write_text("legacy.py\n", encoding="utf-8")
    (tmp_path / "legacy.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "active.py").write_text("y = 2\n", encoding="utf-8")

    files, ignored = get_analyzable_files(tmp_path)
    names = [p.name for p in files]
    assert "legacy.py" not in names
    assert "active.py" in names
    assert ignored == 1


def test_get_analyzable_files_deathbedignore_glob(tmp_path):
    (tmp_path / ".deathbedignore").write_text("vendor/**\n", encoding="utf-8")
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "lib.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("y = 2\n", encoding="utf-8")

    files, ignored = get_analyzable_files(tmp_path)
    names = [p.name for p in files]
    assert "lib.py" not in names
    assert "app.py" in names
