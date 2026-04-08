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

from pipnav.core.audio import init_audio, play_sound, shutdown_audio
from pipnav.core.config import PipNavConfig, load_config, update_config
from pipnav.core.flavor import random_loading_message
from pipnav.core.git import GitStatus, compute_badge, get_git_status
from pipnav.core.indexer import ProjectIndexer
from pipnav.core.launcher import launch_claude, launch_remote_control, launch_vscode
from pipnav.core.logging import setup_logging
from pipnav.core.profiles import (
    DEFAULT_PROFILE,
    WorkspaceProfile,
    filter_projects_by_profile,
    get_available_recipes,
    get_effective_roots,
    get_profile_by_name,
    load_profiles,
)
from pipnav.core.memory import (
    ProjectMemory,
    cycle_tag,
    load_memory,
    memory_to_notes,
    save_memory,
    set_note,
)
from pipnav.core.notes import ProjectNotes
from pipnav.core.projects import ProjectInfo, discover_projects, is_stale
from pipnav.core.search import filter_projects
from pipnav.core.sessions import SessionInfo, load_sessions, record_session
from pipnav.core.stats import compute_aggregate_stats
from pipnav.core.utils import read_readme_preview
from pipnav.core.watcher import FileWatcher
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
from pipnav.ui.launch_builder import LaunchBuilder
from pipnav.ui.memory_editor import MemoryEditor
from pipnav.ui.profile_switcher import ProfileSwitcher
from pipnav.ui.recipe_editor import RecipeEditor, launch_options_to_recipe
from pipnav.ui.recipe_picker import RecipePicker
from pipnav.ui.session_center_tab import SessionCenterTab
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
        ("5", "show_tab('CONSOLE')", "CONSOLE"),
        ("6", "show_tab('INV')", "INV"),
        ("t", "cycle_tag", "Tag"),
        ("n", "edit_memory", "Memory"),
        ("N", "edit_note", "Note"),
        ("p", "cycle_color_scheme", "Color"),
        ("full_stop", "refresh", "Refresh"),
        ("grave_accent", "toggle_sound", "Sound"),
        ("tilde", "toggle_sound", "Sound"),
        ("question_mark", "show_help", "Help"),
        ("f", "session_filter", "Filter"),
        ("o", "session_sort", "Sort"),
        ("w", "switch_profile", "Profile"),
        ("a", "pick_recipe", "Action"),
    ]

    _CHAR_ACTIONS = frozenset({
        "quit", "cursor_down", "cursor_up", "focus_right", "focus_left",
        "open_vscode", "open_claude", "resume_claude", "start_search",
        "cycle_tag", "edit_memory", "edit_note", "toggle_sound", "show_help",
        "cycle_color_scheme", "session_filter", "session_sort",
        "switch_profile", "pick_recipe",
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
        self._memory: dict[str, ProjectMemory] = {}
        self._current_tab: str = "STAT"
        self._editing_note: bool = False
        self._nav_stack: list[tuple[str, ...]] = []
        self._current_roots: tuple[str, ...] = ()
        self._idle_timer: object | None = None
        self._indexer: ProjectIndexer | None = None
        self._watcher: FileWatcher | None = None
        self._watcher_triggered: bool = False
        self._profiles: tuple[WorkspaceProfile, ...] = ()
        self._active_profile: WorkspaceProfile = DEFAULT_PROFILE
        self._background_session_center_refresh: bool = False

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
                yield SessionCenterTab(id="CONSOLE")
                yield InventoryTab(id="INV")
        yield PipBoyInput(placeholder="Enter note (max 200 chars)...", id="note-input")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        """Initialize the app — load config, discover projects."""
        setup_logging()
        init_audio()
        self._config = load_config()

        self._sessions = load_sessions()
        self._memory = load_memory()

        # Load workspace profiles and apply active profile
        self._profiles = load_profiles()
        available_profiles = self._available_profiles()
        if self._config.active_profile:
            found = get_profile_by_name(
                available_profiles, self._config.active_profile
            )
            if found is not None:
                self._active_profile = found

        self._current_roots = get_effective_roots(
            self._active_profile, self._config.project_roots
        )

        # Apply color scheme — profile overrides config
        scheme = self._active_profile.color_scheme or self._config.color_scheme
        if scheme not in SCHEME_NAMES:
            scheme = "green"
        self.theme = f"pipboy-{scheme}"

        self.query_one("#search-bar", SearchBar).display = False
        self.query_one("#note-input", PipBoyInput).display = False

        # Always show boot screen
        self.push_screen(BootScreen())

        # Initialize indexer with warm-start from cache
        self._indexer = ProjectIndexer(
            roots=self._current_roots,
            ttl_seconds=self._config.cache_ttl_seconds,
        )
        cached = self._indexer.warm_start()
        if cached is not None:
            # Use cached data for instant startup
            projects = self._indexer.get_projects()
            statuses = self._indexer.get_git_statuses()
            self._update_project_list(projects, statuses)

        # Start file watcher for live updates
        self._watcher = FileWatcher(
            roots=self._current_roots,
            interval_seconds=self._config.poll_interval_seconds,
            on_change=self._on_watcher_change,
        )
        self._watcher.start()

        # Show active profile in status bar
        if self._active_profile.name != "default":
            try:
                self.query_one("#status-bar", StatusBar).update_profile(
                    self._active_profile.name
                )
            except Exception:
                pass

        self.query_one("#project-list", ProjectList).focus_list()
        self._load_projects()
        self._reset_idle_timer()

    def on_unmount(self) -> None:
        """Clean up the persistent audio helper and watcher on app shutdown."""
        if self._watcher is not None:
            self._watcher.stop()
        shutdown_audio()

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
    def _load_projects(self, force_full: bool = False) -> None:
        """Discover projects and fetch git status in background via indexer."""
        if self._indexer is not None:
            # Update indexer roots in case they changed (drill-down)
            self._indexer.roots = self._current_roots
            self._indexer.refresh(force_full=force_full)
            projects = self._indexer.get_projects()
            statuses = self._indexer.get_git_statuses()
        else:
            # Fallback if indexer not initialized
            projects = discover_projects(self._current_roots)
            statuses = {}
            for project in projects:
                if project.is_git_repo:
                    statuses[str(project.path)] = get_git_status(project.path)
                else:
                    statuses[str(project.path)] = None

        self.call_from_thread(self._update_project_list, projects, statuses)

    def _on_watcher_change(self) -> None:
        """Called from watcher thread when filesystem changes are detected."""
        self.call_from_thread(self._trigger_background_refresh)

    def _trigger_background_refresh(self) -> None:
        """Trigger a background refresh from the main thread.

        Force a full re-index so git/session changes detected by the watcher
        are reflected immediately, then refresh the session center quietly.
        """
        self._background_session_center_refresh = True
        self._load_projects(force_full=True)
        # Update freshness display
        try:
            self.query_one("#status-bar", StatusBar).update_freshness(
                self._indexer.last_scan_time() if self._indexer else None
            )
        except Exception:
            pass

    def _update_project_list(
        self,
        projects: tuple[ProjectInfo, ...],
        statuses: dict[str, GitStatus | None],
    ) -> None:
        """Update the UI with discovered projects."""
        visible_paths = frozenset(
            filter_projects_by_profile(
                tuple(str(project.path) for project in projects),
                self._active_profile,
            )
        )
        visible_projects = tuple(
            project for project in projects if str(project.path) in visible_paths
        )
        self._all_projects = visible_projects
        self._git_statuses = {
            path: status
            for path, status in statuses.items()
            if path in visible_paths
        }
        self._rebuild_list(visible_projects)
        self._update_status_bar()
        self._update_inventory()
        self._update_session_center(
            background=self._background_session_center_refresh
        )
        self._background_session_center_refresh = False
        # Update freshness indicator
        try:
            self.query_one("#status-bar", StatusBar).update_freshness(
                self._indexer.last_scan_time() if self._indexer else None
            )
        except Exception:
            pass

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

    def _update_session_center(self, background: bool = False) -> None:
        """Update the CONSOLE tab with all sessions."""
        try:
            self.query_one("#CONSOLE", SessionCenterTab).load_sessions(
                self._all_projects,
                background=background,
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
        if self._watcher is not None:
            self._watcher.roots = self._current_roots
        if self._indexer is not None:
            self._indexer.invalidate()
        self._load_projects()
        self._update_title()

    def action_go_back(self) -> None:
        """Go back up to the parent directory level."""
        if not self._nav_stack:
            self.notify("Already at top level")
            return

        self._current_roots = self._nav_stack.pop()
        if self._watcher is not None:
            self._watcher.roots = self._current_roots
        if self._indexer is not None:
            self._indexer.invalidate()
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
        if getattr(event, "user_initiated", True):
            play_sound("navigate")
        path = event.path
        name = event.name

        git_status = self._git_statuses.get(str(path))
        session = self._sessions.get(str(path))
        notes = memory_to_notes(self._memory.get(str(path), ProjectMemory()))
        readme = read_readme_preview(path)

        mem = self._memory.get(str(path))
        self.query_one("#STAT", ProjectDetail).update_detail(
            name, path, git_status, session, notes, readme, memory=mem
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
        tabs = ("STAT", "FILES", "LOG", "SESSIONS", "CONSOLE", "INV")
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
            self._memory = cycle_tag(str(path), self._config.tags, self._memory)
            self._refresh_selected_detail()

    def action_edit_memory(self) -> None:
        """Open the memory editor modal for the selected project."""
        path = self._selected_project_path()
        if not path:
            return
        mem = self._memory.get(str(path), ProjectMemory())
        self.push_screen(MemoryEditor(mem, project_name=path.name))

    @on(MemoryEditor.Saved)
    def _on_memory_saved(self, event: MemoryEditor.Saved) -> None:
        """Save updated memory for the selected project."""
        path = self._selected_project_path()
        if path:
            self._memory = {**self._memory, str(path): event.memory}
            save_memory(self._memory)
            self._refresh_selected_detail()
            self.notify("Memory saved")

    def action_edit_note(self) -> None:
        """Show inline note editor (quick note)."""
        path = self._selected_project_path()
        if not path:
            return

        note_input = self.query_one("#note-input", PipBoyInput)
        current_notes = memory_to_notes(self._memory.get(str(path), ProjectMemory()))
        note_input.value = current_notes.note
        note_input.display = True
        note_input.focus()
        self._editing_note = True

    @on(PipBoyInput.Submitted, "#note-input")
    def _on_note_submitted(self, event: PipBoyInput.Submitted) -> None:
        """Save note and hide the input."""
        path = self._selected_project_path()
        if path:
            self._memory = set_note(str(path), event.value, self._memory)
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

    # --- Workspace profiles ---

    def action_switch_profile(self) -> None:
        """Open the profile switcher modal."""
        self.push_screen(
            ProfileSwitcher(self._available_profiles(), self._active_profile.name)
        )

    @on(ProfileSwitcher.Selected)
    def _on_profile_selected(self, event: ProfileSwitcher.Selected) -> None:
        """Apply the selected workspace profile."""
        profile = event.profile
        self._active_profile = profile
        self._config = update_config(self._config, active_profile=profile.name)

        # Update roots
        self._nav_stack.clear()
        self._current_roots = get_effective_roots(
            profile, self._config.project_roots
        )
        if self._watcher is not None:
            self._watcher.roots = self._current_roots
        if self._indexer is not None:
            self._indexer.invalidate()

        # Apply profile color scheme, or fall back to the global config scheme.
        scheme = profile.color_scheme or self._config.color_scheme
        if scheme not in SCHEME_NAMES:
            scheme = "green"
        self.theme = f"pipboy-{scheme}"

        # Update status bar profile indicator
        try:
            bar_name = profile.name if profile.name != "default" else ""
            self.query_one("#status-bar", StatusBar).update_profile(bar_name)
        except Exception:
            pass

        self.notify(f"Profile: {profile.name}")
        self._load_projects()
        self._update_title()

    def action_pick_recipe(self) -> None:
        """Open the recipe picker modal for the selected project."""
        path = self._selected_project_path()
        if not path:
            self.notify("Select a project first", severity="warning")
            return
        recipes = get_available_recipes(self._active_profile)
        self.push_screen(RecipePicker(recipes))

    @on(RecipePicker.Selected)
    def _on_recipe_selected(self, event: RecipePicker.Selected) -> None:
        """Execute the selected launch recipe."""
        path = self._selected_project_path()
        if not path:
            return

        recipe = event.recipe
        play_sound("launch")
        extra_flags = list(recipe.claude_flags)
        if recipe.permission_mode:
            extra_flags.extend(["--permission-mode", recipe.permission_mode])

        if recipe.action == "resume_latest":
            ok, err = launch_claude(
                path,
                self._config.claude_command,
                resume=True,
                extra_flags=tuple(extra_flags),
            )
        elif recipe.action == "resume_pick":
            # Switch to SESSIONS tab so user can pick
            self.action_show_tab("SESSIONS")
            return
        elif recipe.action == "remote_control":
            ok, err = launch_remote_control(
                path,
                self._config.claude_command,
                session_name=path.name,
            )
        else:
            ok, err = launch_claude(
                path,
                self._config.claude_command,
                extra_flags=tuple(extra_flags),
            )

        if ok:
            self._sessions = record_session(path, resumable=True)
            self.notify(f"{recipe.name}: {path.name}")
        else:
            self.notify(err, severity="error")

    @on(RecipePicker.CustomRequested)
    def _on_custom_requested(self, event: RecipePicker.CustomRequested) -> None:
        """Open the custom launch builder."""
        path = self._selected_project_path()
        name = path.name if path else ""
        self.push_screen(LaunchBuilder(project_name=name))

    @on(RecipePicker.NewRecipeRequested)
    def _on_new_recipe_requested(
        self, event: RecipePicker.NewRecipeRequested
    ) -> None:
        """Open the recipe editor for a new recipe."""
        self.push_screen(RecipeEditor())

    @on(LaunchBuilder.Launched)
    def _on_custom_launch(self, event: LaunchBuilder.Launched) -> None:
        """Handle a custom launch."""
        path = self._selected_project_path()
        if not path:
            return

        play_sound("launch")
        flags = list(event.options.to_flags())
        ok, err = launch_claude(
            path, self._config.claude_command, extra_flags=tuple(flags)
        )

        if ok:
            self._sessions = record_session(path, resumable=True)
            self.notify(f"Custom launch: {path.name}")

            # Save as recipe if requested
            if event.save_as_recipe:
                recipe = launch_options_to_recipe(event.options)
                self.push_screen(RecipeEditor(recipe))
        else:
            self.notify(err, severity="error")

    @on(RecipeEditor.Saved)
    def _on_recipe_saved(self, event: RecipeEditor.Saved) -> None:
        """Save a new recipe to the active profile."""
        from pipnav.core.profiles import save_profiles

        recipe = event.recipe
        profile = self._active_profile

        # Add recipe to profile (replace if same name exists)
        existing = tuple(r for r in profile.recipes if r.name != recipe.name)
        updated_profile = WorkspaceProfile(
            name=profile.name,
            roots=profile.roots,
            tags_filter=profile.tags_filter,
            hidden_projects=profile.hidden_projects,
            color_scheme=profile.color_scheme,
            default_recipe=profile.default_recipe,
            recipes=(*existing, recipe),
        )
        self._active_profile = updated_profile

        # Update in profiles list
        updated_profiles = tuple(
            updated_profile if p.name == profile.name else p
            for p in self._profiles
        )
        # If profile wasn't in the list (e.g. default), add it
        if not any(p.name == profile.name for p in self._profiles):
            updated_profiles = (*self._profiles, updated_profile)

        self._profiles = updated_profiles
        save_profiles(self._profiles)
        self.notify(f"Recipe saved: {recipe.name}")

    # --- Sound toggle ---

    def action_toggle_sound(self) -> None:
        """Toggle sound effects on/off."""
        from pipnav.core import audio
        if audio._muted:
            audio._muted = False
            play_sound("crt_on")
            self.notify("Sound ON")
        else:
            audio._muted = True
            shutdown_audio()
            self.notify("Sound OFF")

    # --- Help ---

    def action_show_help(self) -> None:
        """Show keybinding help overlay."""
        self.push_screen(HelpScreen())

    # --- Refresh ---

    def action_refresh(self) -> None:
        """Refresh all project metadata (forces full re-scan)."""
        self._sessions = load_sessions()
        self._memory = load_memory()
        if self._indexer is not None:
            self._indexer.invalidate()
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
            elif tab == "CONSOLE":
                self.query_one("#session-center-table").focus()
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
        """Resume a specific Claude Code session from per-project SESSIONS tab."""
        ok, err = launch_claude(
            event.project_path,
            self._config.claude_command,
            session_id=event.session_id,
        )
        if ok:
            self.notify("Resuming Claude session...")
        else:
            self.notify(err, severity="error")

    @on(SessionCenterTab.SessionActivated)
    def _on_center_session_activated(
        self, event: SessionCenterTab.SessionActivated
    ) -> None:
        """Resume a session from the Session Control Center."""
        play_sound("launch")
        ok, err = launch_claude(
            event.project_path,
            self._config.claude_command,
            session_id=event.session_id,
        )
        if ok:
            self._sessions = record_session(event.project_path, resumable=True)
            self.notify(f"Resuming session in {event.project_path.name}...")
        else:
            self.notify(err, severity="error")

    def action_session_filter(self) -> None:
        """Cycle session center filter (only when CONSOLE tab is active)."""
        if self._current_tab == "CONSOLE":
            self.query_one("#CONSOLE", SessionCenterTab).cycle_filter()

    def action_session_sort(self) -> None:
        """Cycle session center sort (only when CONSOLE tab is active)."""
        if self._current_tab == "CONSOLE":
            self.query_one("#CONSOLE", SessionCenterTab).cycle_sort()

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
            notes = memory_to_notes(self._memory.get(str(path), ProjectMemory()))
            mem = self._memory.get(str(path))
            readme = read_readme_preview(path)
            self.query_one("#STAT", ProjectDetail).update_detail(
                entry.name, path, git_status, session, notes, readme, memory=mem
            )

    def _available_profiles(self) -> tuple[WorkspaceProfile, ...]:
        """Return configured profiles plus the built-in default profile."""
        default_profile = next(
            (
                profile
                for profile in self._profiles
                if profile.name.lower() == DEFAULT_PROFILE.name.lower()
            ),
            DEFAULT_PROFILE,
        )
        profiles: list[WorkspaceProfile] = [default_profile]
        seen = {default_profile.name.lower()}

        for profile in self._profiles:
            if profile.name.lower() in seen:
                continue
            profiles.append(profile)
            seen.add(profile.name.lower())

        return tuple(profiles)


def main() -> None:
    """Entry point for the pipnav command."""
    app = PipNavApp()
    app.run()


if __name__ == "__main__":
    main()
