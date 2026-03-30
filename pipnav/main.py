"""PipNav application entry point — wires together all UI and core modules."""

from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.events import Key
from textual.theme import Theme
from textual.widgets import ContentSwitcher, DirectoryTree, Footer, Input

from pipnav.core.config import PipNavConfig, load_config, update_config
from pipnav.core.git import GitStatus, compute_badge, get_git_status
from pipnav.core.launcher import launch_claude, launch_vscode
from pipnav.core.logging import setup_logging
from pipnav.core.notes import ProjectNotes, cycle_tag, load_notes, set_note
from pipnav.core.projects import ProjectInfo, discover_projects, is_stale
from pipnav.core.search import filter_projects
from pipnav.core.sessions import SessionInfo, load_sessions, record_session
from pipnav.core.utils import read_readme_preview
from pipnav.ui.boot_screen import BootScreen
from pipnav.ui.files_tab import FilesTab
from pipnav.ui.header import PipNavHeader
from pipnav.ui.help_overlay import HelpScreen
from pipnav.ui.log_tab import LogTab
from pipnav.ui.project_detail import ProjectDetail
from pipnav.ui.project_list import ProjectEntry, ProjectList
from pipnav.ui.search_bar import SearchBar
from pipnav.ui.sessions_tab import SessionsTab

PIPBOY_THEME = Theme(
    name="pipboy",
    primary="#8EFE55",
    secondary="#1A8033",
    accent="#8EFE55",
    foreground="#8EFE55",
    background="#0D2B0D",
    surface="#0D2B0D",
    panel="#0D2B0D",
    warning="#8EFE55",
    error="#FF4444",
    success="#8EFE55",
    dark=True,
    variables={
        "block-cursor-background": "#8EFE55",
        "block-cursor-foreground": "#0D2B0D",
        "block-cursor-blurred-background": "#0D2B0D",
        "block-cursor-blurred-foreground": "#8EFE55",
        "block-hover-background": "transparent",
        "surface-active": "#0D2B0D",
        "input-cursor-background": "#8EFE55",
        "input-cursor-foreground": "#0D2B0D",
    },
)


class PipBoyInput(Input):
    """Input with no background tint on focus."""

    DEFAULT_CSS = """
    PipBoyInput {
        background-tint: initial;
    }
    PipBoyInput:focus {
        background-tint: initial;
    }
    """


class PipNavApp(App):
    """Fallout Pip-Boy themed TUI project launcher."""

    CSS_PATH = "ui/app.tcss"
    TITLE = "PipNav"

    # Only non-character keys in BINDINGS — single-char keys handled in on_key
    BINDINGS = [
        ("escape", "quit_or_close", "Back/Quit"),
        ("backspace", "go_back", "Back"),
        ("f5", "refresh", "Refresh"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.register_theme(PIPBOY_THEME)
        self.theme = "pipboy"
        self._config: PipNavConfig = PipNavConfig()
        self._all_projects: tuple[ProjectInfo, ...] = ()
        self._git_statuses: dict[str, GitStatus | None] = {}
        self._sessions: dict[str, SessionInfo] = {}
        self._notes: dict[str, ProjectNotes] = {}
        self._current_tab: str = "STAT"
        self._editing_note: bool = False
        self._crt_timer: object | None = None
        self._crt_bright: bool = True
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
        yield PipBoyInput(placeholder="Enter note (max 200 chars)...", id="note-input")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app — load config, discover projects."""
        setup_logging()
        self._config = load_config()
        self._sessions = load_sessions()
        self._notes = load_notes()
        self._current_roots = self._config.project_roots

        self.query_one("#search-bar", SearchBar).display = False
        self.query_one("#note-input", PipBoyInput).display = False

        if self._config.crt_effects:
            self._enable_crt()
            self.push_screen(BootScreen())

        self.query_one("#project-list", ProjectList).focus_list()
        self._load_projects()

    # --- Key handling ---
    # Single-char bindings go here so they're suppressed when an Input has focus.

    def _input_has_focus(self) -> bool:
        """Return True if any Input widget currently has focus."""
        focused = self.focused
        return isinstance(focused, Input)

    def on_key(self, event: Key) -> None:
        """Handle all single-character keybindings, suppressing them during text input."""
        if event.key == "tab":
            event.stop()
            event.prevent_default()
            self.action_next_tab()
            return

        # Let Input widgets handle their own keys
        if self._input_has_focus():
            return

        key_actions: dict[str, str] = {
            "q": "quit",
            "j": "cursor_down",
            "k": "cursor_up",
            "l": "focus_right",
            "h": "focus_left",
            "v": "open_vscode",
            "c": "open_claude",
            "r": "resume_claude",
            "slash": "start_search",
            "1": "show_tab('STAT')",
            "2": "show_tab('FILES')",
            "3": "show_tab('LOG')",
            "4": "show_tab('SESSIONS')",
            "t": "cycle_tag",
            "n": "edit_note",
            "grave_accent": "toggle_crt",
            "tilde": "toggle_crt",
            "question_mark": "show_help",
        }

        action = key_actions.get(event.key)
        if action:
            event.stop()
            event.prevent_default()
            self.run_action(action)

    # --- Project loading ---

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

        self.call_from_thread(self._update_project_list, projects, statuses)

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
        self._drill_into(event.path)

    def _drill_into(self, path: Path) -> None:
        """Drill into a folder's subdirectories."""
        if not path:
            return

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

        self.query_one("#STAT", ProjectDetail).update_detail(
            name, path, git_status, session, notes, readme
        )
        self.query_one("#FILES", FilesTab).project_path = path
        self.query_one("#LOG", LogTab).project_path = path
        self.query_one("#SESSIONS", SessionsTab).project_path = path

    def _selected_project_path(self) -> Path | None:
        """Return the path of the currently selected project."""
        entry = self.query_one("#project-list", ProjectList).selected_entry
        return entry.path if entry else None

    # --- Tab switching ---

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
        self.query_one("#search-bar", SearchBar).is_searching = True

    @on(SearchBar.QueryChanged)
    def _on_search_query(self, event: SearchBar.QueryChanged) -> None:
        """Filter projects by search query."""
        self._rebuild_list(filter_projects(event.query, self._all_projects))

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
            self._notes = cycle_tag(str(path), self._config.tags, self._notes)
            self._refresh_selected_detail()

    def action_edit_note(self) -> None:
        """Show inline note editor."""
        path = self._selected_project_path()
        if not path:
            return

        note_input = self.query_one("#note-input", PipBoyInput)
        current_notes = self._notes.get(str(path), ProjectNotes())
        note_input.value = current_notes.note
        note_input.display = True
        note_input.focus()
        self._editing_note = True

    @on(PipBoyInput.Submitted, "#note-input")
    def _on_note_submitted(self, event: PipBoyInput.Submitted) -> None:
        """Save note and hide the input."""
        path = self._selected_project_path()
        if path:
            self._notes = set_note(str(path), event.value, self._notes)
            self._refresh_selected_detail()

        note_input = self.query_one("#note-input", PipBoyInput)
        note_input.display = False
        self._editing_note = False
        self.query_one("#project-list", ProjectList).focus_list()

    # --- CRT effects ---

    def action_toggle_crt(self) -> None:
        """Toggle CRT flicker effect."""
        new_value = not self._config.crt_effects
        self._config = update_config(self._config, crt_effects=new_value)
        if new_value:
            self._enable_crt()
            self.notify("CRT effects ON")
        else:
            self._disable_crt()
            self.notify("CRT effects OFF")

    def _enable_crt(self) -> None:
        """Start CRT flicker — alternate between bright and dim green."""
        self.add_class("crt-on")
        self._crt_timer = self.set_interval(0.15, self._crt_flicker)
        self._crt_bright = True

    def _disable_crt(self) -> None:
        """Stop CRT flicker and restore normal colors."""
        self.remove_class("crt-on")
        self.remove_class("crt-dim")
        if self._crt_timer is not None:
            self._crt_timer.stop()  # type: ignore[union-attr]
            self._crt_timer = None

    def _crt_flicker(self) -> None:
        """Toggle between bright and dim states for CRT flicker."""
        self._crt_bright = not self._crt_bright
        if self._crt_bright:
            self.remove_class("crt-dim")
        else:
            self.add_class("crt-dim")

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
        except Exception:
            pass

    def action_focus_left(self) -> None:
        """Move focus back to the project list."""
        self.query_one("#project-list", ProjectList).focus_list()

    def action_cursor_down(self) -> None:
        """Move cursor down in project list."""
        try:
            self.query_one("#project-list #project-options").action_cursor_down()  # type: ignore[attr-defined]
        except Exception:
            pass

    def action_cursor_up(self) -> None:
        """Move cursor up in project list."""
        try:
            self.query_one("#project-list #project-options").action_cursor_up()  # type: ignore[attr-defined]
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
            note_input = self.query_one("#note-input", PipBoyInput)
            note_input.display = False
            self._editing_note = False
            self.query_one("#project-list", ProjectList).focus_list()
            return

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
            self.notify("Resuming Claude session...")
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
            self.query_one("#STAT", ProjectDetail).update_detail(
                entry.name, path, git_status, session, notes, readme
            )


def main() -> None:
    """Entry point for the pipnav command."""
    app = PipNavApp()
    app.run()


if __name__ == "__main__":
    main()
