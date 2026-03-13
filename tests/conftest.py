# Shared pytest fixtures.
#
# We suppress all writes to ~/.deathbed/history.json during tests.

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_history_writes(monkeypatch):
    """Prevent test runs from writing to ~/.deathbed/history.json."""
    import deathbed.history as hist_mod
    monkeypatch.setattr(hist_mod, "save_scan", lambda *a, **kw: None)
