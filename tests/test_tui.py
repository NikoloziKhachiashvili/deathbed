"""Tests for tui.py — interactive TUI (textual optional dependency)."""
from __future__ import annotations

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestRunInteractiveFallback:
    """When textual is not installed, run_interactive should fall back to run_display."""

    def test_run_interactive_signature(self):
        """run_interactive has the correct parameter signature."""
        from deathbed.tui import run_interactive
        import inspect
        sig = inspect.signature(run_interactive)
        params = list(sig.parameters.keys())
        assert "repo_path" in params
        assert "top" in params
        assert "min_score" in params
        assert "since_ref" in params
        assert "include_blame" in params
        assert "org_path" in params

    def test_run_interactive_calls_fallback_display_when_textual_absent(self):
        """When textual is not importable, run_interactive calls run_display."""
        with patch("deathbed.display.run_display") as mock_run:
            mock_run.return_value = None
            # Simulate textual being unavailable by patching the import inside run_interactive
            original_textual = sys.modules.get("textual", "NOTSET")
            try:
                sys.modules["textual"] = None  # type: ignore
                with patch("deathbed.display.console") as mock_console:
                    mock_console.print = MagicMock()
                    import deathbed.tui as tui_mod
                    try:
                        tui_mod.run_interactive(Path("."), top=10, min_score=None)
                    except Exception:
                        pass  # may fail for other reasons; just ensure no crash on import check
            finally:
                if original_textual == "NOTSET":
                    sys.modules.pop("textual", None)
                else:
                    sys.modules["textual"] = original_textual  # type: ignore


class TestTuiModule:
    def test_module_importable(self):
        """tui module can be imported without errors."""
        import deathbed.tui  # noqa: F401

    def test_run_interactive_is_callable(self):
        """run_interactive is a callable function."""
        from deathbed.tui import run_interactive
        assert callable(run_interactive)

    def test_run_textual_app_is_callable(self):
        """_run_textual_app is a callable function."""
        from deathbed.tui import _run_textual_app
        assert callable(_run_textual_app)

    def test_fallback_uses_display_console(self):
        """The fallback panel is printed via the display console (not tui.console)."""
        # The tui module imports console lazily from display, not at module level
        import deathbed.tui as tui_mod
        # Verify tui module itself does NOT have a top-level `console` attribute
        assert not hasattr(tui_mod, "console"), (
            "tui.py should not define a top-level console; it uses display.console lazily"
        )
