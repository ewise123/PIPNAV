"""PipNav application entry point — wires together all UI and core modules."""

from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.events import Key
from textual.widgets import ContentSwitcher, DirectoryTree, Footer, Input

from pipnav.core.config import PipNavConfig, load_config, update_config
from pipnav.core.git import GitStatus, compute_badge, get_git_status
from pipnav.core.launcher import launch_claude, launch_vscode
from pipnav.core.logging import setup_logging
from pipnav.core.notes import (
    ProjectNotes,
    cycle_tag,
    load_notes,
    set_note,
)
from pipnav.core.projects import ProjectInfo, discover_projects, is_stale
from pipnav.core.search import filter_projects
from pipnav.core.sessions import SessionInfo, load_sessions, record_session
from pipnav.core.utils import read_readme_preview
from pipnav.ui.boot_screen import BootScreen
from pipnav.ui.crt_overlay import CRTOverlay
from pipnav.ui.files_tab import FilesTab
from pipnav.ui.header import PipNavHeader
from pipnav.ui.help_overlay import HelpScreen
from pipnav.ui.log_tab import LogTab
from pipnav.ui.project_detail import ProjectDetail
from pipnav.ui.project_list import ProjectEntry, ProjectList
from pipnav.ui.search_bar import SearchBar
from pipnav.ui.sessions_tab import SessionsTab


class PipNavApp(App):
    """Fallout Pip-Boy themed TUI project launcher."""

    CSS_PATH = "ui/app.tcss"
    TITLE = "PipNav"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "quit_or_close", "Back/Quit"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("l", "focus_right", "Focus Right"),
        ("h", "focus_left", "Focus Left"),
        ("backspace", "go_back", "Back"),
        ("v", "open_vscode", "VS Code"),
        ("c", "open_claude", "Claude"),
        ("r", "resume_claude", "Resume"),
        ("slash", "start_search", "Search"),
        ("1", "show_tab('STAT')", "STAT"),
        ("2", "show_tab('FILES')", "FILES"),
        ("3", "show_tab('LOG')", "LOG"),
        ("4", "show_tab('SESSIONS')", "SESSIONS"),
        ("t", "cycle_tag", "Tag"),
        ("n", "edit_note", "Note"),
        ("f5", "refresh", "Refresh"),
        ("grave_accent", "toggle_crt", "CRT"),
        ("tilde", "toggle_crt", "CRT"),
        ("question_mark", "show_help", "Help"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._config: PipNavConfig = PipNavConfig()
        self._all_projects: tuple[ProjectInfo, ...] = ()
        self._git_statuses: dict[str, GitStatus | None] = {}
        self._sessions: dict[str, SessionInfo] = {}
        self._notes: dict[str, ProjectNotes] = {}
        self._current_tab: str = "STAT"
        self._editing_note: bool = False
        # Navigation stack for drilling into folders
        self._nav_stack: list[tuple[str, ...]] = []
        self._current_roots: tuple[str, ...] = ()

    def compose(self) -> ComposeResult:
        yield PipNavHeader(id="header")
        yield SearchBar(id="search-bar")
        with Horizontal(id="main-layout"):
            yield ProjectList(id="project-list")
            with ContentSwitcher(initial="STAT", id="tab-content"):
                yield ProjectDetail(id="STAT")
                yield FilesTab(id="FILES")
                yield LogTab(id="LOG")
                yield SessionsTab(id="SESSIONS")
        yield Input(placeholder="Enter note (max 200 chars)...", id="note-input")
        yield CRTOverlay(id="crt-overlay")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app — load config, discover projects."""
        setup_logging()
        self._config = load_config()
        self._sessions = load_sessions()
        self._notes = load_notes()
        self._current_roots = self._config.project_roots

        # Hide search bar and note input initially
        self.query_one("#search-bar", SearchBar).display = False
        self.query_one("#note-input", Input).display = False

        # CRT overlay
        crt = self.query_one("#crt-overlay", CRTOverlay)
        crt.display = self._config.crt_effects

        # Show boot screen if CRT effects are on (otherwise skip)
        if self._config.crt_effects:
            self.push_screen(BootScreen())

        # Focus the project list
        self.query_one("#project-list", ProjectList).focus_list()

        # Load projects in background
        self._load_projects()

    @work(exclusive=True, thread=True)
    def _load_projects(self) -> None:
        """Discover projects and fetch git status in background."""
        projects = discover_projects(self._current_roots)
        statuses: dict[str, GitStatus | None] = {}

        for project in projects:
            if project.is_git_repo:
                statuses[str(project.path)] = get_git_status(project.path)
            else:
                statuses[str(project.path)] = None

        self.app.call_from_thread(self._update_project_list, projects, statuses)

    def _update_project_list(
        self,
        projects: tuple[ProjectInfo, ...],
        statuses: dict[str, GitStatus | None],
    ) -> None:
        """Update the UI with discovered projects."""
        self._all_projects = projects
        self._git_statuses.update(statuses)
        self._rebuild_list(projects)

    def _rebuild_list(self, projects: tuple[ProjectInfo, ...]) -> None:
        """Rebuild the OptionList with the given projects."""
        entries: list[ProjectEntry] = []
        for project in projects:
            git_status = self._git_statuses.get(str(project.path))
            has_session = str(project.path) in self._sessions
            stale = is_stale(project, self._config.stale_threshold_days)
            badge = compute_badge(git_status, has_session, stale)
            entries.append(
                ProjectEntry(name=project.name, path=project.path, badge=badge)
            )

        self.query_one("#project-list", ProjectList).set_projects(tuple(entries))

    # --- Directory drill-down ---

    @on(ProjectList.Activated)
    def _on_project_activated(self, event: ProjectList.Activated) -> None:
        """Drill into folder when Enter is pressed."""
        path = event.path
        self._drill_into(path)

    def _drill_into(self, path: Path) -> None:
        """Drill into a folder's subdirectories."""
        if not path:
            return

        # Check if this folder has subdirectories worth drilling into
        try:
            subdirs = [
                d for d in sorted(path.iterdir(), key=lambda p: p.name.lower())
                if d.is_dir() and not d.name.startswith(".")
            ]
        except OSError:
            return

        if not subdirs:
            self.notify("No subdirectories to open", severity="warning")
            return

        # Push current roots onto the stack and drill into this folder
        self._nav_stack.append(self._current_roots)
        self._current_roots = (str(path),)
        self._load_projects()
        self._update_title()

    def action_go_back(self) -> None:
        """Go back up to the parent directory level."""
        if not self._nav_stack:
            self.notify("Already at top level")
            return

        self._current_roots = self._nav_stack.pop()
        self._load_projects()
        self._update_title()

    def _update_title(self) -> None:
        """Update the app subtitle to show current location."""
        if self._nav_stack:
            # Show the current folder name we're inside
            root = Path(self._current_roots[0])
            self.sub_title = f"/{root.name}"
        else:
            self.sub_title = ""

    # --- Project selection ---

    @on(ProjectList.Selected)
    def _on_project_selected(self, event: ProjectList.Selected) -> None:
        """Update detail panel and tabs when a project is selected."""
        path = event.path
        name = event.name

        git_status = self._git_statuses.get(str(path))
        session = self._sessions.get(str(path))
        notes = self._notes.get(str(path), ProjectNotes())
        readme = read_readme_preview(path)

        # Update STAT tab
        detail = self.query_one("#STAT", ProjectDetail)
        detail.update_detail(name, path, git_status, session, notes, readme)

        # Update FILES tab
        files_tab = self.query_one("#FILES", FilesTab)
        files_tab.project_path = path

        # Update LOG tab
        log_tab = self.query_one("#LOG", LogTab)
        log_tab.project_path = path

        # Update SESSIONS tab
        sessions_tab = self.query_one("#SESSIONS", SessionsTab)
        sessions_tab.project_path = path

    def _selected_project_path(self) -> Path | None:
        """Return the path of the currently selected project."""
        entry = self.query_one("#project-list", ProjectList).selected_entry
        return entry.path if entry else None

    # --- Tab switching ---

    def on_key(self, event: Key) -> None:
        """Intercept Tab before Textual's focus system consumes it."""
        if event.key == "tab":
            event.stop()
            event.prevent_default()
            self.action_next_tab()

    def action_next_tab(self) -> None:
        """Cycle through tabs."""
        tabs = ("STAT", "FILES", "LOG", "SESSIONS")
        try:
            idx = tabs.index(self._current_tab)
            self._current_tab = tabs[(idx + 1) % len(tabs)]
        except ValueError:
            self._current_tab = "STAT"
        self._apply_tab()

    def action_show_tab(self, tab: str) -> None:
        """Switch to a specific tab."""
        self._current_tab = tab
        self._apply_tab()

    def _apply_tab(self) -> None:
        """Apply the current tab selection to UI."""
        self.query_one("#tab-content", ContentSwitcher).current = self._current_tab
        self.query_one("#header", PipNavHeader).active_tab = self._current_tab

    # --- Launchers ---

    def action_open_vscode(self) -> None:
        """Open selected project in VS Code."""
        path = self._selected_project_path()
        if path:
            ok, err = launch_vscode(path, self._config.vscode_command)
            if not ok:
                self.notify(err, severity="error")
            else:
                self.notify(f"Opening {path.name} in VS Code...")

    def action_open_claude(self) -> None:
        """Launch Claude Code on selected project."""
        path = self._selected_project_path()
        if path:
            ok, err = launch_claude(path, self._config.claude_command)
            if ok:
                self._sessions = record_session(path, resumable=True)
                self.notify(f"Claude Code launched for {path.name}")
            else:
                self.notify(err, severity="error")

    def action_resume_claude(self) -> None:
        """Resume Claude Code session on selected project."""
        path = self._selected_project_path()
        if path:
            ok, err = launch_claude(
                path, self._config.claude_command, resume=True
            )
            if ok:
                self._sessions = record_session(path, resumable=True)
                self.notify(f"Resuming Claude session for {path.name}")
            else:
                self.notify(err, severity="error")

    # --- Search ---

    def action_start_search(self) -> None:
        """Open the search bar."""
        search_bar = self.query_one("#search-bar", SearchBar)
        search_bar.is_searching = True

    @on(SearchBar.QueryChanged)
    def _on_search_query(self, event: SearchBar.QueryChanged) -> None:
        """Filter projects by search query."""
        filtered = filter_projects(event.query, self._all_projects)
        self._rebuild_list(filtered)

    @on(SearchBar.SearchClosed)
    def _on_search_closed(self, event: SearchBar.SearchClosed) -> None:
        """Restore full project list when search is closed."""
        self._rebuild_list(self._all_projects)
        self.query_one("#project-list", ProjectList).focus_list()

    # --- Tags and Notes ---

    def action_cycle_tag(self) -> None:
        """Cycle tag on the selected project."""
        path = self._selected_project_path()
        if path:
            self._notes = cycle_tag(
                str(path), self._config.tags, self._notes
            )
            self._refresh_selected_detail()

    def action_edit_note(self) -> None:
        """Show inline note editor."""
        path = self._selected_project_path()
        if not path:
            return

        note_input = self.query_one("#note-input", Input)
        current_notes = self._notes.get(str(path), ProjectNotes())
        note_input.value = current_notes.note
        note_input.display = True
        note_input.focus()
        self._editing_note = True

    @on(Input.Submitted, "#note-input")
    def _on_note_submitted(self, event: Input.Submitted) -> None:
        """Save note and hide the input."""
        path = self._selected_project_path()
        if path:
            self._notes = set_note(str(path), event.value, self._notes)
            self._refresh_selected_detail()

        note_input = self.query_one("#note-input", Input)
        note_input.display = False
        self._editing_note = False
        self.query_one("#project-list", ProjectList).focus_list()

    # --- CRT effects ---

    def action_toggle_crt(self) -> None:
        """Toggle CRT scanline effects."""
        new_value = not self._config.crt_effects
        self._config = update_config(self._config, crt_effects=new_value)
        self.query_one("#crt-overlay", CRTOverlay).display = new_value

    # --- Help ---

    def action_show_help(self) -> None:
        """Show keybinding help overlay."""
        self.push_screen(HelpScreen())

    # --- Refresh ---

    def action_refresh(self) -> None:
        """Refresh all project metadata."""
        self._sessions = load_sessions()
        self._notes = load_notes()
        self._load_projects()
        self.notify("Refreshing projects...")

    # --- Focus and cursor ---

    def action_focus_right(self) -> None:
        """Move focus to the active tab's content panel."""
        tab = self._current_tab
        try:
            if tab == "FILES":
                self.query_one("#file-tree").focus()
            elif tab == "LOG":
                self.query_one("#LOG").focus()
            elif tab == "SESSIONS":
                self.query_one("#session-options").focus()
            else:
                # STAT has no focusable content, stay on list
                pass
        except Exception:
            pass

    def action_focus_left(self) -> None:
        """Move focus back to the project list."""
        self.query_one("#project-list", ProjectList).focus_list()

    def action_cursor_down(self) -> None:
        """Move cursor down in project list."""
        try:
            ol = self.query_one("#project-list #project-options")
            ol.action_cursor_down()  # type: ignore[attr-defined]
        except Exception:
            pass

    def action_cursor_up(self) -> None:
        """Move cursor up in project list."""
        try:
            ol = self.query_one("#project-list #project-options")
            ol.action_cursor_up()  # type: ignore[attr-defined]
        except Exception:
            pass

    # --- Quit handling ---

    def action_quit_or_close(self) -> None:
        """Close search/note if open, go back if drilled in, otherwise quit."""
        search_bar = self.query_one("#search-bar", SearchBar)
        if search_bar.is_searching:
            search_bar.is_searching = False
            self.post_message(SearchBar.SearchClosed())
            return

        if self._editing_note:
            note_input = self.query_one("#note-input", Input)
            note_input.display = False
            self._editing_note = False
            self.query_one("#project-list", ProjectList).focus_list()
            return

        # If drilled into a subfolder, go back instead of quitting
        if self._nav_stack:
            self.action_go_back()
            return

        self.exit()

    # --- Session resume ---

    @on(SessionsTab.SessionActivated)
    def _on_session_activated(self, event: SessionsTab.SessionActivated) -> None:
        """Resume a specific Claude Code session in a new terminal tab."""
        ok, err = launch_claude(
            event.project_path,
            self._config.claude_command,
            session_id=event.session_id,
        )
        if ok:
            self.notify(f"Resuming Claude session...")
        else:
            self.notify(err, severity="error")

    # --- File tree integration ---

    @on(DirectoryTree.FileSelected)
    def _on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Open selected file in VS Code."""
        launch_vscode(
            event.path.parent,
            self._config.vscode_command,
            file_path=event.path,
        )

    # --- Helpers ---

    def _refresh_selected_detail(self) -> None:
        """Re-render the detail panel for the current selection."""
        entry = self.query_one("#project-list", ProjectList).selected_entry
        if entry:
            path = entry.path
            git_status = self._git_statuses.get(str(path))
            session = self._sessions.get(str(path))
            notes = self._notes.get(str(path), ProjectNotes())
            readme = read_readme_preview(path)
            detail = self.query_one("#STAT", ProjectDetail)
            detail.update_detail(entry.name, path, git_status, session, notes, readme)


def main() -> None:
    """Entry point for the pipnav command."""
    app = PipNavApp()
    app.run()


if __name__ == "__main__":
    main()
