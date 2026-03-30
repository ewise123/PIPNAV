"""Utility functions — time formatting and text helpers."""

from datetime import datetime
from pathlib import Path


def time_ago(dt: datetime | None) -> str:
    """Return a human-readable relative time string."""
    if dt is None:
        return "unknown"

    delta = datetime.now() - dt
    seconds = int(delta.total_seconds())

    if seconds < 0:
        return "just now"
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} min ago" if minutes > 1 else "1 min ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hours ago" if hours > 1 else "1 hour ago"
    if seconds < 2592000:  # 30 days
        days = seconds // 86400
        return f"{days} days ago" if days > 1 else "1 day ago"
    if seconds < 31536000:  # 365 days
        months = seconds // 2592000
        return f"{months} months ago" if months > 1 else "1 month ago"

    years = seconds // 31536000
    return f"{years} years ago" if years > 1 else "1 year ago"


def read_readme_preview(path: Path, max_lines: int = 5) -> str:
    """Read first few lines of README.md, stripping markdown headers."""
    readme = path / "README.md"
    if not readme.exists():
        readme = path / "readme.md"
    if not readme.exists():
        return ""

    try:
        lines: list[str] = []
        for line in readme.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Strip markdown header markers
            if stripped.startswith("#"):
                stripped = stripped.lstrip("#").strip()
            # Skip horizontal rules
            if stripped in ("---", "***", "___"):
                continue
            lines.append(stripped)
            if len(lines) >= max_lines:
                break
        return "\n".join(lines)
    except OSError:
        return ""
