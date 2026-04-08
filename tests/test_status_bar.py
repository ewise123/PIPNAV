"""Tests for adaptive status bar behavior."""

from types import SimpleNamespace

from pipnav.ui.status_bar import StatusBar


def test_status_bar_refreshes_on_resize(monkeypatch) -> None:
    bar = StatusBar()
    calls: list[str] = []

    monkeypatch.setattr(bar, "_refresh_display", lambda: calls.append("refresh"))

    bar.on_resize(SimpleNamespace())

    assert calls == ["refresh"]
