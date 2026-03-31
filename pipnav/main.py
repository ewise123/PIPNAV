"""PipNav application entry point — wires together all UI and core modules."""

from __future__ import annotations

import random
import string
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.events import Key
from textual.theme import Theme
from textual.widgets import ContentSwitcher, DataTable, DirectoryTree, Input, OptionList, Static

from pipnav.core.audio import init_audio, play_sound
from pipnav.core.config import PipNavConfig, load_config, update_config
from pipnav.core.flavor import random_loading_message
from pipnav.core.git import GitStatus, compute_badge, get_git_status
from pipnav.core.launcher import launch_claude, launch_vscode
from pipnav.core.logging import setup_logging
from pipnav.core.notes import ProjectNotes, cycle_tag, load_notes, set_note
from pipnav.core.projects import ProjectInfo, discover_projects, is_stale
from pipnav.core.search import filter_projects
from pipnav.core.sessions import SessionInfo, load_sessions, record_session
from pipnav.core.stats import compute_aggregate_stats
from pipnav.core.utils import read_readme_preview
from pipnav.ui.boot_screen import BootScreen
from pipnav.ui.files_tab import FilesTab
from pipnav.ui.header import PipNavHeader
from pipnav.ui.help_overlay import HelpScreen
from pipnav.ui.idle_screen import IdleScreen
from pipnav.ui.inventory_tab import InventoryTab
from pipnav.ui.log_tab import LogTab
from pipnav.ui.project_detail import ProjectDetail
from pipnav.ui.project_list import ProjectEntry, ProjectList
from pipnav.ui.search_bar import SearchBar
from pipnav.ui.sessions_tab import SessionsTab
from pipnav.ui.status_bar import StatusBar

# --- Color scheme themes ---

_THEME_COLORS = {
    "green": {
        "primary": "#8EFE55", "secondary": "#1A8033", "bg": "#0D2B0D",
        "crt_bright": "#A4FE77", "crt_dim": "#5A9E33",
        "crt_bg_bright": "#103510", "crt_bg_dim": "#081A08",
    },
    "amber": {
        "primary": "#FFB000", "secondary": "#996600", "bg": "#2B1A00",
        "crt_bright": "#FFCC44", "crt_dim": "#CC8800",
        "crt_bg_bright": "#352200", "crt_bg_dim": "#1A1100",
    },
    "blue": {
        "primary": "#00BFFF", "secondary": "#006688", "bg": "#001A2B",
        "crt_bright": "#44DDFF", "crt_dim": "#0088AA",
        "crt_bg_bright": "#002235", "crt_bg_dim": "#001018",
    },
    "white": {
        "primary": "#E0E0E0", "secondary": "#666666", "bg": "#1A1A1A",
        "crt_bright": "#F0F0F0", "crt_dim": "#999999",
        "crt_bg_bright": "#222222", "crt_bg_dim": "#111111",
    },
}

SCHEME_NAMES = ("green", "amber", "blue", "white")


def _make_theme(name: str, colors: dict[str, str]) -> Theme:
    """Create a Textual Theme from a color dict."""
    return Theme(
        name=f"pipboy-{name}",
        primary=colors["primary"],
        secondary=colors["secondary"],
        accent=colors["primary"],
        foreground=colors["primary"],
        background=colors["bg"],
        surface=colors["bg"],
        panel=colors["bg"],
        warning=colors["primary"],
        error="#FF4444",
        success=colors["primary"],
        dark=True,
        variables={
            "block-cursor-background": colors["primary"],
            "block-cursor-foreground": "#000000",
            "block-cursor-blurred-background": colors["bg"],
            "block-cursor-blurred-foreground": colors["primary"],
            "block-hover-background": "transparent",
            "surface-active": colors["bg"],
            "input-cursor-background": colors["primary"],
            "input-cursor-foreground": colors["bg"],
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


# Idle timeout in seconds
IDLE_TIMEOUT = 300


class PipNavApp(App):
    """Fallout Pip-Boy themed TUI project launcher."""

    CSS_PATH = "ui/app.tcss"
    TITLE = "PipNav"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "quit_or_close", "Back/Quit"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("l", "focus_right", "Right"),
        ("h", "focus_left", "Left"),
        ("backspace", "go_back", "Back"),
        ("v", "open_vscode", "VS Code"),
        ("c", "open_claude", "Claude"),
        ("r", "resume_claude", "Resume"),
        ("slash", "start_search", "Search"),
        ("1", "show_tab('STAT')", "STAT"),
        ("2", "show_tab('FILES')", "FILES"),
        ("3", "show_tab('LOG')", "LOG"),
        ("4", "show_tab('SESSIONS')", "SESSIONS"),
        ("5", "show_tab('INV')", "INV"),
        ("t", "cycle_tag", "Tag"),
        ("n", "edit_note", "Note"),
        ("p", "cycle_color_scheme", "Color"),
        ("full_stop", "refresh", "Refresh"),
        ("grave_accent", "toggle_sound", "Sound"),
        ("tilde", "toggle_sound", "Sound"),
        ("question_mark", "show_help", "Help"),
    ]

    _CHAR_ACTIONS = frozenset({
        "quit", "cursor_down", "cursor_up", "focus_right", "focus_left",
        "open_vscode", "open_claude", "resume_claude", "start_search",
        "cycle_tag", "edit_note", "toggle_sound", "show_help",
        "cycle_color_scheme",
    })

    def __init__(self) -> None:
        super().__init__()
        # Register all color scheme themes
        for name, colors in _THEME_COLORS.items():
            self.register_theme(_make_theme(name, colors))

        self._config: PipNavConfig = PipNavConfig()
        self._all_projects: tuple[ProjectInfo, ...] = ()
        self._git_statuses: dict[str, GitStatus | None] = {}
        self._sessions: dict[str, SessionInfo] = {}
        self._notes: dict[str, ProjectNotes] = {}
        self._current_tab: str = "STAT"
        self._editing_note: bool = False
        self._nav_stack: list[tuple[str, ...]] = []
        self._current_roots: tuple[str, ...] = ()
        self._idle_timer: object | None = None

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
                yield InventoryTab(id="INV")
        yield PipBoyInput(placeholder="Enter note (max 200 chars)...", id="note-input")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        """Initialize the app — load config, discover projects."""
        setup_logging()
        init_audio()
        self._config = load_config()

        self._sessions = load_sessions()
        self._notes = load_notes()
        self._current_roots = self._config.project_roots

        # Apply color scheme from config
        scheme = getattr(self._config, "color_scheme", "green")
        if scheme not in SCHEME_NAMES:
            scheme = "green"
        self.theme = f"pipboy-{scheme}"

        self.query_one("#search-bar", SearchBar).display = False
        self.query_one("#note-input", PipBoyInput).display = False

        # Always show boot screen
        self.push_screen(BootScreen())

        self.query_one("#project-list", ProjectList).focus_list()
        self._load_projects()
        self._reset_idle_timer()

    # --- Key handling ---

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Block single-char bindings when an Input has focus."""
        if isinstance(self.focused, Input) and action in self._CHAR_ACTIONS:
            return False
        return True

    def on_key(self, event: Key) -> None:
        """Intercept Tab and reset idle timer on any key."""
        self._reset_idle_timer()
        if event.key == "tab":
            event.stop()
            event.prevent_default()
            self.action_next_tab()

    # --- Idle screen ---

    def _reset_idle_timer(self) -> None:
        """Reset the idle timeout. Shows PLEASE STAND BY after inactivity."""
        if self._idle_timer is not None:
            self._idle_timer.stop()  # type: ignore[union-attr]
        self._idle_timer = self.set_timer(IDLE_TIMEOUT, self._show_idle)

    def _show_idle(self) -> None:
        """Show the PLEASE STAND BY screen."""
        self.push_screen(IdleScreen())

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
        self._update_status_bar()
        self._update_inventory()

    def _rebuild_list(self, projects: tuple[ProjectInfo, ...]) -> None:
        """Rebuild the OptionList with the given projects."""
        entries: list[ProjectEntry] = []
        for project in projects:
            git_status = self._git_statuses.get(str(project.path))
            has_session = str(project.path) in self._sessions
            stale = is_stale(project, self._config.stale_threshold_days)
            badge = compute_badge(git_status, has_session, stale)
            has_warning = git_status is not None and git_status.is_dirty
            entries.append(
                ProjectEntry(
                    name=project.name,
                    path=project.path,
                    badge=badge,
                    is_stale=stale,
                    has_warning=has_warning,
                )
            )

        self.query_one("#project-list", ProjectList).set_projects(tuple(entries))

    def _update_status_bar(self) -> None:
        """Update the Pip-Boy status bar with aggregate stats."""
        stats = compute_aggregate_stats(self._git_statuses)
        try:
            self.query_one("#status-bar", StatusBar).update_stats(
                total=stats["total"],
                clean=stats["clean"],
                with_sessions=stats["projects_with_sessions"],
            )
        except Exception:
            pass

    def _update_inventory(self) -> None:
        """Update the INV tab DataTable."""
        try:
            projects = tuple(
                (p.name, p.path) for p in self._all_projects
            )
            self.query_one("#INV", InventoryTab).update_inventory(
                projects, self._git_statuses
            )
        except Exception:
            pass

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
        play_sound("navigate")
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
        tabs = ("STAT", "FILES", "LOG", "SESSIONS", "INV")
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
        play_sound("tab")
        self.query_one("#tab-content", ContentSwitcher).current = self._current_tab
        self.query_one("#header", PipNavHeader).active_tab = self._current_tab

    def _flash_static(self) -> None:
        """Brief static flash when switching tabs (CRT effect)."""
        self.screen.add_class("crt-static")
        self.set_timer(0.08, lambda: self.screen.remove_class("crt-static"))

    # --- Launchers ---

    def action_open_vscode(self) -> None:
        """Open selected project in VS Code."""
        path = self._selected_project_path()
        if path:
            play_sound("launch")
            ok, err = launch_vscode(path, self._config.vscode_command)
            if not ok:
                self.notify(err, severity="error")
            else:
                self.notify(f"Opening {path.name} in VS Code...")

    def action_open_claude(self) -> None:
        """Launch Claude Code on selected project."""
        path = self._selected_project_path()
        if path:
            play_sound("launch")
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
            play_sound("launch")
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

    # --- Color scheme ---

    def action_cycle_color_scheme(self) -> None:
        """Cycle through Pip-Boy color schemes."""
        current = getattr(self._config, "color_scheme", "green")
        try:
            idx = SCHEME_NAMES.index(current)
            next_scheme = SCHEME_NAMES[(idx + 1) % len(SCHEME_NAMES)]
        except ValueError:
            next_scheme = "green"

        self._config = update_config(self._config, color_scheme=next_scheme)
        self.theme = f"pipboy-{next_scheme}"
        self.notify(f"Color scheme: {next_scheme.upper()}")

    # --- Sound toggle ---

    def action_toggle_sound(self) -> None:
        """Toggle sound effects on/off."""
        from pipnav.core import audio
        audio_enabled = not getattr(audio, "_muted", False)
        audio._muted = audio_enabled
        if audio_enabled:
            self.notify("Sound OFF")
        else:
            play_sound("crt_on")
            self.notify("Sound ON")

    # --- Help ---

    def action_show_help(self) -> None:
        """Show keybinding help overlay."""
        self.push_screen(HelpScreen())

    # --- Refresh ---

    def action_refresh(self) -> None:
        """Refresh all project metadata."""
        self._sessions = load_sessions()
        self._notes = load_notes()
        self.notify(random_loading_message())
        self._load_projects()

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
            elif tab == "INV":
                self.query_one("#inv-table").focus()
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

    @on(DirectoryTree.NodeHighlighted)
    def _on_tree_navigate(self, event: DirectoryTree.NodeHighlighted) -> None:
        """Play navigate sound when moving in file tree."""
        play_sound("navigate")

    @on(OptionList.OptionHighlighted, "#session-options")
    def _on_session_navigate(self, event: OptionList.OptionHighlighted) -> None:
        """Play navigate sound when moving in session list."""
        play_sound("navigate")

    @on(DataTable.RowHighlighted)
    def _on_inv_navigate(self, event: DataTable.RowHighlighted) -> None:
        """Play navigate sound when moving in inventory table."""
        play_sound("navigate")

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
