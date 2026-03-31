"""INV tab — sortable DataTable of all projects, Fallout inventory style."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import DataTable

from pipnav.core.git import GitStatus
from pipnav.core.utils import time_ago


class InventoryTable(DataTable):
    """DataTable with no background tint on focus."""

    DEFAULT_CSS = """
    InventoryTable {
        background-tint: initial;
    }
    InventoryTable:focus {
        background-tint: initial;
    }
    """


@dataclass(frozen=True)
class InventoryRow:
    """A row in the inventory table."""

    name: str
    branch: str
    modified: int
    last_commit: str
    path: Path


class InventoryTab(VerticalScroll):
    """Fallout inventory-style sortable project table."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._rows: tuple[InventoryRow, ...] = ()

    def compose(self) -> ComposeResult:
        table = InventoryTable(id="inv-table")
        table.cursor_type = "row"
        table.zebra_stripes = False
        yield table

    def on_mount(self) -> None:
        """Set up table columns."""
        table = self.query_one("#inv-table", InventoryTable)
        table.add_columns("NAME", "BRANCH", "MOD", "LAST COMMIT", "PATH")

    def update_inventory(
        self,
        projects: tuple[tuple[str, Path], ...],
        git_statuses: dict[str, GitStatus | None],
    ) -> None:
        """Rebuild the table with current project data."""
        table = self.query_one("#inv-table", InventoryTable)
        table.clear()

        rows: list[InventoryRow] = []
        for name, path in projects:
            gs = git_statuses.get(str(path))
            branch = gs.branch if gs else "—"
            modified = gs.modified_count + gs.untracked_count if gs else 0
            last = time_ago(gs.last_commit_time) if gs else "—"
            rows.append(InventoryRow(name, branch, modified, last, path))

        self._rows = tuple(rows)

        for row in rows:
            mod_str = str(row.modified) if row.modified > 0 else "—"
            short_path = f"~/{row.path.relative_to(Path.home())}"
            table.add_row(row.name, row.branch, mod_str, row.last_commit, short_path)
