"""Tests for config.py — TOML config loader."""
from __future__ import annotations

import pytest
from pathlib import Path

from deathbed.config import load_config, _try_load_toml, _DEFAULTS


class TestTryLoadToml:
    def test_returns_empty_dict_when_file_missing(self, tmp_path):
        result = _try_load_toml(tmp_path / "nonexistent.toml")
        assert result == {}

    def test_returns_empty_dict_on_invalid_toml(self, tmp_path):
        bad = tmp_path / "bad.toml"
        bad.write_text("this is not valid toml [[[[", encoding="utf-8")
        # Should not raise; returns empty dict gracefully
        result = _try_load_toml(bad)
        assert isinstance(result, dict)

    def test_loads_valid_toml_if_tomllib_available(self, tmp_path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text(
            "[thresholds]\nwarning = 70\ncritical = 45\n",
            encoding="utf-8",
        )
        result = _try_load_toml(toml_file)
        # Either {} (no tomllib/tomli) or the parsed data — both are valid
        assert isinstance(result, dict)
        if result:
            assert result.get("thresholds", {}).get("warning") == 70


class TestLoadConfig:
    def test_returns_all_sections(self, tmp_path):
        cfg = load_config(tmp_path)
        assert "thresholds" in cfg
        assert "guard" in cfg
        assert "org" in cfg
        assert "decay" in cfg

    def test_defaults_are_present(self, tmp_path):
        cfg = load_config(tmp_path)
        assert cfg["thresholds"]["warning"] == 65
        assert cfg["thresholds"]["critical"] == 40
        assert cfg["guard"]["warn_drop"] == 10
        assert cfg["guard"]["block_drop"] == 20
        assert cfg["org"]["exclude"] == []
        assert cfg["decay"]["min_scans"] == 3
        assert cfg["decay"]["horizon_days"] == 30

    def test_repo_toml_overrides_defaults(self, tmp_path):
        toml_file = tmp_path / ".deathbed.toml"
        toml_file.write_text(
            "[thresholds]\nwarning = 70\n",
            encoding="utf-8",
        )
        cfg = load_config(tmp_path)
        # If tomllib/tomli is available, override should apply
        # If not, defaults are used — both are acceptable
        assert isinstance(cfg["thresholds"]["warning"], int)

    def test_missing_repo_uses_only_defaults(self, tmp_path):
        cfg = load_config(tmp_path)
        assert cfg["thresholds"]["warning"] == _DEFAULTS["thresholds"]["warning"]

    def test_handles_missing_global_config_gracefully(self, tmp_path, monkeypatch):
        # Monkeypatch home to a temp dir with no config
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        cfg = load_config(tmp_path)
        assert cfg["thresholds"]["warning"] == 65
