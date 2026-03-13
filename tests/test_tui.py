"""Tests for tui.py — interactive TUI (textual optional dependency)."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch


class TestRunInteractiveFallback:
    """When textual is not installed, run_interactive should fall back to run_display."""

    def test_run_interactive_signature(self):
        """run_interactive has the correct parameter signature."""
        import inspect

        from deathbed.tui import run_interactive
        sig = inspect.signature(run_interactive)
        params = list(sig.parameters.keys())
        assert "repo_path" in params
        assert "top" in params
        assert "min_score" in params
        assert "since_ref" in params
        assert "include_blame" in params
        assert "org_path" in params

    def test_run_interactive_calls_fallback_display_when_textual_absent(self, tmp_path):
        """When textual is not importable, run_interactive calls run_display."""
        saved = sys.modules.pop("textual", "NOTSET")
        try:
            sys.modules["textual"] = None  # type: ignore[assignment]
            with (
                patch("deathbed.display.run_display") as mock_run_display,
                patch("deathbed.display.console") as mock_console,
            ):
                mock_console.print = MagicMock()
                from deathbed.tui import run_interactive
                run_interactive(tmp_path, top=5, min_score=None)
            mock_run_display.assert_called_once()
        finally:
            if saved == "NOTSET":
                sys.modules.pop("textual", None)
            else:
                sys.modules["textual"] = saved  # type: ignore[assignment]


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
