"""FLEET tab — every coding agent herdr is currently watching.

Phase 0: live agents only, straight from herdr. Phase 4 merges in session
history from disk and promotes this to the landing view.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Static

from pipnav.core.herdr import HerdrAgent

# Presentation only — herdr's own status names live in core/herdr.py.
STATUS_BADGES: dict[str, str] = {
    "blocked": "[bold red]NEEDS YOU[/]",
    "working": "[bold green]WORKING[/]",
    "done": "[bold yellow]DONE[/]",
    "idle": "[dim]IDLE[/]",
    "unknown": "[dim]?[/]",
}


class FleetTable(DataTable):
    """DataTable with no background tint on focus."""

    DEFAULT_CSS = """
    FleetTable {
        background-tint: initial;
    }
    FleetTable:focus {
        background-tint: initial;
    }
    """


@dataclass(frozen=True)
class FleetRow:
    """A row in the fleet table, kept so keybindings can act on the selection."""

    pane_id: str
    harness: str
    status: str
    project: str
    doing: str


class FleetTab(VerticalScroll):
    """Live view of every agent in the herd."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._rows: tuple[FleetRow, ...] = ()

    def compose(self) -> ComposeResult:
        yield Static("", id="fleet-status")
        table = FleetTable(id="fleet-table")
        table.cursor_type = "row"
        table.zebra_stripes = False
        yield table

    def on_mount(self) -> None:
        table = self.query_one("#fleet-table", FleetTable)
        table.add_columns("AGENT", "STATUS", "PROJECT", "DOING", "PANE")
        self.query_one("#fleet-status", Static).update("[dim]connecting to herdr...[/]")

    @property
    def rows(self) -> tuple[FleetRow, ...]:
        return self._rows

    def selected_pane_id(self) -> str:
        """The pane id under the cursor, or "" when the table is empty."""
        table = self.query_one("#fleet-table", FleetTable)
        index = table.cursor_row
        if 0 <= index < len(self._rows):
            return self._rows[index].pane_id
        return ""

    def update_fleet(
        self,
        agents: tuple[HerdrAgent, ...],
        available: bool,
        version: str = "",
    ) -> None:
        """Rebuild the table from herdr's live agent list."""
        self._render_status(agents, available, version)

        rows = [
            FleetRow(
                pane_id=agent.pane_id,
                harness=agent.label or agent.harness or "—",
                status=agent.status,
                project=agent.cwd.name if agent.cwd else "—",
                doing=agent.title or "—",
            )
            for agent in agents
        ]
        self._rows = tuple(rows)

        table = self.query_one("#fleet-table", FleetTable)
        # DataTable highlights row 0 on rebuild; suppress it so the 3s refresh
        # doesn't sound like the user navigating.
        with table.prevent(DataTable.RowHighlighted):
            table.clear()
            for row in rows:
                table.add_row(
                    row.harness,
                    STATUS_BADGES.get(row.status, row.status),
                    row.project,
                    row.doing,
                    row.pane_id,
                )

    def _render_status(
        self,
        agents: tuple[HerdrAgent, ...],
        available: bool,
        version: str,
    ) -> None:
        status = self.query_one("#fleet-status", Static)

        if not available:
            status.update(
                "[bold red]herdr not running[/] — "
                "start it with [bold]herdr[/] in a terminal. "
                "PipNav still launches sessions the old way."
            )
            return

        if not agents:
            status.update(
                f"[green]herdr {version}[/] connected — no agents running yet"
            )
            return

        blocked = sum(1 for agent in agents if agent.needs_you)
        attention = (
            f"  ·  [bold red]{blocked} needs you[/]" if blocked else "  ·  all quiet"
        )
        status.update(
            f"[green]herdr {version}[/]  ·  {len(agents)} "
            f"agent{'s' if len(agents) != 1 else ''}{attention}"
        )
