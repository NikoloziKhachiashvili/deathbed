"""Shared utility functions used across multiple deathbed modules."""

from __future__ import annotations

from deathbed import __version__

__all__ = ["human_days", "score_severity", "__version__"]


def human_days(days: int) -> str:
    """Convert a day count to a human-readable relative time string."""
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days}d ago"
    if days < 30:
        weeks = days // 7
        return f"{weeks}w ago"
    if days < 365:
        months = days // 30
        return f"{months}mo ago"
    years = days // 365
    leftover = (days % 365) // 30
    return f"{years}y {leftover}mo ago" if leftover else f"{years}y ago"


def score_severity(score: int) -> str:
    """Map a 0-100 health score to a severity string."""
    if score <= 40:
        return "critical"
    if score <= 65:
        return "warning"
    if score <= 85:
        return "fair"
    return "healthy"
