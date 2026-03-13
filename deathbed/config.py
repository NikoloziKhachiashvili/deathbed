"""Configuration loader for .deathbed.toml — optional TOML config file."""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

__all__ = ["load_config"]

_DEFAULTS: dict = {
    "thresholds": {"warning": 65, "critical": 40},
    "guard": {"warn_drop": 10, "block_drop": 20},
    "org": {"exclude": []},
    "decay": {"min_scans": 3, "horizon_days": 30},
}


def _try_load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            return {}
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except Exception as exc:
        log.debug("Failed to load TOML config %s: %s", path, exc)
        return {}


def load_config(repo_root: Path) -> dict:
    """Load and merge config from ~/.deathbed/config.toml and <repo>/.deathbed.toml."""
    global_cfg = _try_load_toml(Path.home() / ".deathbed" / "config.toml")
    repo_cfg   = _try_load_toml(repo_root / ".deathbed.toml")
    result: dict = {}
    for section, defaults in _DEFAULTS.items():
        merged = {**defaults}
        if section in global_cfg and isinstance(global_cfg[section], dict):
            merged.update(global_cfg[section])
        if section in repo_cfg and isinstance(repo_cfg[section], dict):
            merged.update(repo_cfg[section])
        result[section] = merged
    return result
