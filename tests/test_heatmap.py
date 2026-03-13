"""Tests for heatmap.py — terminal treemap renderer."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from deathbed.heatmap import (
    _heatmap_char,
    _heatmap_color,
    render_heatmap,
)
from deathbed.scoring import FileMetrics, compute_scores


def _make_metric(path: str = "foo.py", score: int = 80, lines: int = 100) -> FileMetrics:
    m = FileMetrics(path=path, lines=lines, days_since_commit=10,
                    commit_count=5, author_count=1, avg_complexity=2.0)
    compute_scores(m)
    m.composite_score = score
    return m


# ── Color and char helpers ────────────────────────────────────────────────────

class TestHeatmapColor:
    def test_healthy_is_green(self):
        c = _heatmap_color(90)
        assert "0,200,80" in c or "200,80" in c

    def test_fair_is_yellow(self):
        c = _heatmap_color(70)
        assert "200,200,0" in c

    def test_warning_is_orange(self):
        c = _heatmap_color(50)
        assert "255,140,0" in c

    def test_critical_is_red(self):
        c = _heatmap_color(30)
        assert "255,69,58" in c

    @pytest.mark.parametrize("score,expected_prefix", [
        (100, "rgb(0"),
        (86,  "rgb(0"),
        (85,  "rgb(200"),
        (66,  "rgb(200"),
        (65,  "rgb(255,140"),
        (41,  "rgb(255,140"),
        (40,  "rgb(255,69"),
        (0,   "rgb(255,69"),
    ])
    def test_boundary_scores(self, score, expected_prefix):
        c = _heatmap_color(score)
        assert c.startswith(expected_prefix)


class TestHeatmapChar:
    def test_healthy_is_full_block(self):
        assert _heatmap_char(90) == "\u2588"

    def test_fair_is_dark_shade(self):
        assert _heatmap_char(70) == "\u2593"

    def test_warning_is_medium_shade(self):
        assert _heatmap_char(50) == "\u2592"

    def test_critical_is_light_shade(self):
        assert _heatmap_char(30) == "\u2591"


# ── render_heatmap ────────────────────────────────────────────────────────────

class TestRenderHeatmap:
    def test_no_output_for_empty_results(self, capsys):
        # Should not crash or print anything meaningful
        with patch("deathbed.heatmap._get_palette") as mock_palette:
            mock_console = MagicMock()
            mock_console.width = 120
            mock_palette.return_value = (
                "rgb(0,200,80)", "rgb(255,191,0)", "rgb(255,140,0)",
                "rgb(255,69,58)", "rgb(178,0,0)", "rgb(220,20,60)",
                "rgb(80,80,80)", "rgb(230,230,230)", "rgb(120,120,120)",
                mock_console,
            )
            render_heatmap([])
        mock_console.print.assert_not_called()

    def test_renders_with_single_file(self):
        m = _make_metric("main.py", score=75, lines=200)
        with patch("deathbed.heatmap._get_palette") as mock_palette:
            mock_console = MagicMock()
            mock_console.width = 120
            mock_palette.return_value = (
                "rgb(0,200,80)", "rgb(255,191,0)", "rgb(255,140,0)",
                "rgb(255,69,58)", "rgb(178,0,0)", "rgb(220,20,60)",
                "rgb(80,80,80)", "rgb(230,230,230)", "rgb(120,120,120)",
                mock_console,
            )
            render_heatmap([m])
        mock_console.print.assert_called()

    def test_too_narrow_shows_error_panel(self):
        m = _make_metric("main.py", score=75, lines=200)
        with patch("deathbed.heatmap._get_palette") as mock_palette:
            mock_console = MagicMock()
            mock_console.width = 40  # too narrow
            mock_palette.return_value = (
                "rgb(0,200,80)", "rgb(255,191,0)", "rgb(255,140,0)",
                "rgb(255,69,58)", "rgb(178,0,0)", "rgb(220,20,60)",
                "rgb(80,80,80)", "rgb(230,230,230)", "rgb(120,120,120)",
                mock_console,
            )
            render_heatmap([m])
        # Should print a panel about being too narrow
        mock_console.print.assert_called_once()

    def test_renders_multiple_files(self):
        files = [
            _make_metric(f"file{i}.py", score=max(10, 90 - i * 10), lines=100 + i * 50)
            for i in range(5)
        ]
        with patch("deathbed.heatmap._get_palette") as mock_palette:
            mock_console = MagicMock()
            mock_console.width = 120
            mock_palette.return_value = (
                "rgb(0,200,80)", "rgb(255,191,0)", "rgb(255,140,0)",
                "rgb(255,69,58)", "rgb(178,0,0)", "rgb(220,20,60)",
                "rgb(80,80,80)", "rgb(230,230,230)", "rgb(120,120,120)",
                mock_console,
            )
            render_heatmap(files)
        mock_console.print.assert_called()

    def test_handles_zero_line_files(self):
        m = _make_metric("empty.py", score=50, lines=0)
        with patch("deathbed.heatmap._get_palette") as mock_palette:
            mock_console = MagicMock()
            mock_console.width = 120
            mock_palette.return_value = (
                "rgb(0,200,80)", "rgb(255,191,0)", "rgb(255,140,0)",
                "rgb(255,69,58)", "rgb(178,0,0)", "rgb(220,20,60)",
                "rgb(80,80,80)", "rgb(230,230,230)", "rgb(120,120,120)",
                mock_console,
            )
            # Should not crash
            render_heatmap([m])
