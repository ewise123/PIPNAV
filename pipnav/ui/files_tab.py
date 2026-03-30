"""FILES tab — directory tree for the selected project."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DirectoryTree, Static

HIDDEN_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".egg-info",
}


class FilteredProjectTree(DirectoryTree):
    """DirectoryTree that hides common noise directories."""

    DEFAULT_CSS = """
    FilteredProjectTree {
        background-tint: initial;
    }
    FilteredProjectTree:focus {
        background-tint: initial;
    }
    FilteredProjectTree > .tree--guides {
        color: #1A8033;
    }
    FilteredProjectTree > .tree--guides-hover {
        color: #1A8033;
    }
    FilteredProjectTree > .tree--guides-selected {
        color: #1A8033;
    }
    FilteredProjectTree:focus > .tree--guides {
        color: #1A8033;
    }
    FilteredProjectTree:focus > .tree--guides-hover {
        color: #1A8033;
    }
    FilteredProjectTree:focus > .tree--guides-selected {
        color: #1A8033;
    }
    """

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Filter out hidden and noise directories."""
        return [
            p
            for p in paths
            if p.name not in HIDDEN_DIRS and not p.name.startswith(".")
        ]


class FilesTab(Widget):
    """File browser tab for the selected project."""

    project_path: reactive[Path | None] = reactive(None)

    def compose(self) -> ComposeResult:
        yield Static("Select a project to browse files", id="files-placeholder")
        yield FilteredProjectTree(".", id="file-tree")

    def on_mount(self) -> None:
        """Hide the tree initially until a project is selected."""
        self.query_one("#file-tree", FilteredProjectTree).display = False

    def watch_project_path(self, path: Path | None) -> None:
        """Update the tree when the project changes."""
        if path is None:
            return

        self.query_one("#files-placeholder", Static).display = False
        tree = self.query_one("#file-tree", FilteredProjectTree)
        tree.path = path
        tree.display = True
        tree.reload()
