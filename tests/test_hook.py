"""Tests for hook.py — git regression guard install/uninstall."""
from __future__ import annotations

from pathlib import Path

import pytest

from deathbed.hook import _HOOK_MARKER, install_hook, uninstall_hook


def _make_fake_repo(tmp_path: Path) -> Path:
    """Create a minimal fake git repo structure with a hooks dir."""
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    return tmp_path


class TestInstallHook:
    def test_installs_hook_file(self, tmp_path):
        repo = _make_fake_repo(tmp_path)
        install_hook(repo)
        hook_file = repo / ".git" / "hooks" / "post-commit"
        assert hook_file.exists()

    def test_hook_contains_marker(self, tmp_path):
        repo = _make_fake_repo(tmp_path)
        install_hook(repo)
        hook_file = repo / ".git" / "hooks" / "post-commit"
        content = hook_file.read_text(encoding="utf-8")
        assert _HOOK_MARKER in content

    def test_hook_contains_warn_drop_value(self, tmp_path):
        repo = _make_fake_repo(tmp_path)
        install_hook(repo, warn_drop=15, block_drop=25)
        hook_file = repo / ".git" / "hooks" / "post-commit"
        content = hook_file.read_text(encoding="utf-8")
        assert "15" in content
        assert "25" in content

    def test_idempotent_reinstall(self, tmp_path):
        repo = _make_fake_repo(tmp_path)
        install_hook(repo)
        # Second call with marker present should overwrite silently
        install_hook(repo, warn_drop=5)
        hook_file = repo / ".git" / "hooks" / "post-commit"
        assert hook_file.exists()

    def test_raises_file_not_found_when_no_hooks_dir(self, tmp_path):
        # No .git/hooks directory
        with pytest.raises(FileNotFoundError):
            install_hook(tmp_path)

    def test_raises_file_exists_when_foreign_hook_present(self, tmp_path):
        repo = _make_fake_repo(tmp_path)
        hook_file = repo / ".git" / "hooks" / "post-commit"
        hook_file.write_text("#!/bin/bash\necho 'foreign hook'\n", encoding="utf-8")
        with pytest.raises(FileExistsError):
            install_hook(repo)

    def test_hook_is_python_script(self, tmp_path):
        repo = _make_fake_repo(tmp_path)
        install_hook(repo)
        hook_file = repo / ".git" / "hooks" / "post-commit"
        content = hook_file.read_text(encoding="utf-8")
        assert "#!/usr/bin/env python3" in content

    def test_hook_contains_import_json(self, tmp_path):
        repo = _make_fake_repo(tmp_path)
        install_hook(repo)
        hook_file = repo / ".git" / "hooks" / "post-commit"
        content = hook_file.read_text(encoding="utf-8")
        assert "import json" in content


class TestUninstallHook:
    def test_removes_deathbed_hook(self, tmp_path):
        repo = _make_fake_repo(tmp_path)
        install_hook(repo)
        result = uninstall_hook(repo)
        assert result is True
        hook_file = repo / ".git" / "hooks" / "post-commit"
        assert not hook_file.exists()

    def test_returns_false_when_no_hook(self, tmp_path):
        repo = _make_fake_repo(tmp_path)
        result = uninstall_hook(repo)
        assert result is False

    def test_returns_false_when_foreign_hook(self, tmp_path):
        repo = _make_fake_repo(tmp_path)
        hook_file = repo / ".git" / "hooks" / "post-commit"
        hook_file.write_text("#!/bin/bash\necho 'not deathbed'\n", encoding="utf-8")
        result = uninstall_hook(repo)
        assert result is False
        # Foreign hook should still exist
        assert hook_file.exists()

    def test_idempotent_double_uninstall(self, tmp_path):
        repo = _make_fake_repo(tmp_path)
        install_hook(repo)
        assert uninstall_hook(repo) is True
        assert uninstall_hook(repo) is False  # already removed
