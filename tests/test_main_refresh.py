"""Targeted tests for watcher, profile, and recipe behavior in the app."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from pipnav.core.config import PipNavConfig
from pipnav.core.profiles import DEFAULT_PROFILE, LaunchRecipe, WorkspaceProfile
from pipnav.core.projects import ProjectInfo
from pipnav.core.memory import ProjectMemory
from pipnav.core.notes import ProjectNotes
from pipnav.main import PipNavApp


class _FakeStatusBar:
    def update_freshness(self, _value) -> None:
        pass

    def update_profile(self, _value) -> None:
        pass


def test_background_refresh_flag_initialized() -> None:
    app = PipNavApp()

    assert app._background_session_center_refresh is False


def test_trigger_background_refresh_forces_full_reload(
    monkeypatch,
) -> None:
    app = PipNavApp()
    loads: list[bool] = []

    monkeypatch.setattr(
        app,
        "_load_projects",
        lambda force_full=False: loads.append(force_full),
    )
    monkeypatch.setattr(
        app,
        "query_one",
        lambda *args, **kwargs: _FakeStatusBar(),
    )
    app._indexer = SimpleNamespace(last_scan_time=lambda: None)

    app._trigger_background_refresh()

    assert app._background_session_center_refresh is True
    assert loads == [True]


def test_update_project_list_refreshes_session_center_in_background(
    monkeypatch,
) -> None:
    app = PipNavApp()
    refresh_modes: list[bool] = []

    monkeypatch.setattr(app, "_rebuild_list", lambda _projects: None)
    monkeypatch.setattr(app, "_update_status_bar", lambda: None)
    monkeypatch.setattr(app, "_update_inventory", lambda: None)
    monkeypatch.setattr(
        app,
        "_update_session_center",
        lambda background=False: refresh_modes.append(background),
    )
    monkeypatch.setattr(
        app,
        "query_one",
        lambda *args, **kwargs: _FakeStatusBar(),
    )

    app._background_session_center_refresh = True
    app._update_project_list((), {})

    assert refresh_modes == [True]
    assert app._background_session_center_refresh is False


def test_update_project_list_applies_hidden_project_filter(
    monkeypatch,
) -> None:
    app = PipNavApp()
    rebuilt: list[str] = []

    monkeypatch.setattr(app, "_rebuild_list", lambda projects: rebuilt.extend(
        project.name for project in projects
    ))
    monkeypatch.setattr(app, "_update_status_bar", lambda: None)
    monkeypatch.setattr(app, "_update_inventory", lambda: None)
    monkeypatch.setattr(app, "_update_session_center", lambda background=False: None)
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: _FakeStatusBar())

    app._active_profile = WorkspaceProfile(
        name="focused",
        hidden_projects=("hide-me",),
    )
    projects = (
        ProjectInfo("hide-me", Path("/tmp/hide-me"), False, None),
        ProjectInfo("keep-me", Path("/tmp/keep-me"), False, None),
    )
    statuses = {
        "/tmp/hide-me": None,
        "/tmp/keep-me": None,
    }

    app._update_project_list(projects, statuses)

    assert rebuilt == ["keep-me"]
    assert [project.name for project in app._all_projects] == ["keep-me"]
    assert set(app._git_statuses) == {"/tmp/keep-me"}


def test_action_switch_profile_includes_default_profile(
    monkeypatch,
) -> None:
    app = PipNavApp()
    shown = []

    monkeypatch.setattr(app, "push_screen", lambda screen: shown.append(screen))

    app._profiles = (WorkspaceProfile(name="work"),)
    app.action_switch_profile()

    assert len(shown) == 1
    assert [profile.name for profile in shown[0]._profiles] == ["default", "work"]


def test_action_switch_profile_prefers_persisted_default(
    monkeypatch,
) -> None:
    app = PipNavApp()
    shown = []
    saved_default = WorkspaceProfile(
        name="default",
        roots=("~/workspace",),
        color_scheme="amber",
    )

    monkeypatch.setattr(app, "push_screen", lambda screen: shown.append(screen))

    app._profiles = (saved_default, WorkspaceProfile(name="work"),)
    app.action_switch_profile()

    assert len(shown) == 1
    assert shown[0]._profiles[0] == saved_default


def test_profile_selection_uses_config_scheme_for_default_profile(
    monkeypatch,
) -> None:
    app = PipNavApp()
    loads: list[bool] = []

    monkeypatch.setattr(
        "pipnav.main.update_config",
        lambda config, **changes: replace(config, **changes),
    )
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: _FakeStatusBar())
    monkeypatch.setattr(app, "_load_projects", lambda *args, **kwargs: loads.append(True))
    monkeypatch.setattr(app, "notify", lambda *args, **kwargs: None)

    app._config = PipNavConfig(
        project_roots=("~/projects",),
        color_scheme="amber",
    )
    app._current_roots = ("/tmp/current",)
    app._nav_stack = [("/tmp/old",)]
    app._watcher = SimpleNamespace(roots=())
    app._indexer = SimpleNamespace(invalidate=lambda: None)
    app.theme = "pipboy-blue"

    app._on_profile_selected(SimpleNamespace(profile=DEFAULT_PROFILE))

    assert app.theme == "pipboy-amber"
    assert app._config.active_profile == "default"
    assert app._current_roots == ("~/projects",)
    assert app._nav_stack == []
    assert loads == [True]


def test_profile_saved_rename_replaces_original_active_profile(
    monkeypatch,
) -> None:
    app = PipNavApp()
    loads: list[bool] = []
    saved_profiles: list[tuple[WorkspaceProfile, ...]] = []

    monkeypatch.setattr(
        "pipnav.main.update_config",
        lambda config, **changes: replace(config, **changes),
    )
    monkeypatch.setattr(
        "pipnav.core.profiles.save_profiles",
        lambda profiles: saved_profiles.append(profiles),
    )
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: _FakeStatusBar())
    monkeypatch.setattr(app, "_load_projects", lambda *args, **kwargs: loads.append(True))
    monkeypatch.setattr(app, "notify", lambda *args, **kwargs: None)

    old_profile = WorkspaceProfile(
        name="work",
        roots=("~/work",),
        color_scheme="blue",
    )
    renamed_profile = WorkspaceProfile(
        name="deep-work",
        roots=("~/deep-work",),
        color_scheme="amber",
    )

    app._profiles = (old_profile, WorkspaceProfile(name="personal"))
    app._active_profile = old_profile
    app._config = PipNavConfig(
        active_profile="work",
        project_roots=("~/projects",),
        color_scheme="green",
    )
    app._current_roots = ("~/work",)
    app._watcher = SimpleNamespace(roots=())
    app._indexer = SimpleNamespace(invalidate=lambda: None)

    app._on_profile_saved(
        SimpleNamespace(profile=renamed_profile, original_name="work")
    )

    assert [profile.name for profile in app._profiles] == ["personal", "deep-work"]
    assert saved_profiles == [app._profiles]
    assert app._active_profile == renamed_profile
    assert app._config.active_profile == "deep-work"
    assert app._current_roots == ("~/deep-work",)
    assert app.theme == "pipboy-amber"
    assert loads == [True]


def test_recipe_selected_passes_recipe_flags_to_launcher(
    monkeypatch,
) -> None:
    app = PipNavApp()
    calls = []

    monkeypatch.setattr(app, "_selected_project_path", lambda: Path("/tmp/demo"))
    monkeypatch.setattr(app, "notify", lambda *args, **kwargs: None)
    monkeypatch.setattr("pipnav.main.play_sound", lambda *args, **kwargs: None)
    monkeypatch.setattr("pipnav.main.record_session", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        "pipnav.main.launch_claude",
        lambda path, command, **kwargs: (calls.append((path, command, kwargs)) or (True, "")),
    )

    app._config = PipNavConfig(claude_command="claude")
    recipe = LaunchRecipe(
        name="Review",
        action="launch",
        claude_flags=("--model", "opus"),
        permission_mode="plan",
    )

    app._on_recipe_selected(SimpleNamespace(recipe=recipe))

    assert calls == [
        (
            Path("/tmp/demo"),
            "claude",
            {"extra_flags": ("--model", "opus", "--permission-mode", "plan")},
        )
    ]


def test_remote_control_recipe_selected_passes_recipe_settings(
    monkeypatch,
) -> None:
    app = PipNavApp()
    calls = []

    monkeypatch.setattr(app, "_selected_project_path", lambda: Path("/tmp/demo"))
    monkeypatch.setattr(app, "notify", lambda *args, **kwargs: None)
    monkeypatch.setattr("pipnav.main.play_sound", lambda *args, **kwargs: None)
    monkeypatch.setattr("pipnav.main.record_session", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        "pipnav.main.launch_remote_control",
        lambda path, command, **kwargs: (calls.append((path, command, kwargs)) or (True, "")),
    )

    app._config = PipNavConfig(claude_command="claude")
    recipe = LaunchRecipe(
        name="Remote Review",
        action="remote_control",
        claude_flags=("--spawn", "worktree", "--capacity", "8", "--name", "custom-name"),
        permission_mode="plan",
    )

    app._on_recipe_selected(SimpleNamespace(recipe=recipe))

    assert calls == [
        (
            Path("/tmp/demo"),
            "claude",
            {
                "permission_mode": "plan",
                "session_name": "demo",
                "extra_flags": (
                    "--spawn",
                    "worktree",
                    "--capacity",
                    "8",
                    "--name",
                    "custom-name",
                ),
            },
        )
    ]


def test_project_selected_skips_sound_for_programmatic_updates(monkeypatch) -> None:
    app = PipNavApp()
    detail_calls = []
    files_tab = SimpleNamespace(project_path=None)
    log_tab = SimpleNamespace(project_path=None)

    monkeypatch.setattr(
        "pipnav.main.play_sound",
        lambda *_args, **_kwargs: detail_calls.append("sound"),
    )
    monkeypatch.setattr("pipnav.main.read_readme_preview", lambda _path: "README")

    app._git_statuses = {}
    app._sessions = {}
    app._memory = {"/tmp/demo": ProjectMemory(note="note")}

    def query_one(selector, *_args, **_kwargs):
        if selector == "#STAT":
            return SimpleNamespace(update_detail=lambda *args, **kwargs: detail_calls.append(args))
        if selector == "#FILES":
            return files_tab
        if selector == "#LOG":
            return log_tab
        raise AssertionError(selector)

    monkeypatch.setattr(app, "query_one", query_one)

    app._on_project_selected(
        SimpleNamespace(
            path=Path("/tmp/demo"),
            name="demo",
            user_initiated=False,
        )
    )

    assert "sound" not in detail_calls
    assert files_tab.project_path == Path("/tmp/demo")
    assert log_tab.project_path == Path("/tmp/demo")
    assert any(
        call[0] == "demo" and call[1] == Path("/tmp/demo")
        for call in detail_calls
        if isinstance(call, tuple)
    )


def test_action_show_tab_console_filters_to_selected_project(monkeypatch) -> None:
    app = PipNavApp()
    console_calls: list[Path | None] = []
    header = SimpleNamespace(active_tab=None)
    content = SimpleNamespace(current=None)
    console_tab = SimpleNamespace(
        clear_project_filter=lambda: console_calls.append(None),
        set_project_filter=lambda path: console_calls.append(path),
    )

    monkeypatch.setattr("pipnav.main.play_sound", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_selected_project_path", lambda: Path("/tmp/demo"))

    def query_one(selector, *_args, **_kwargs):
        if selector == "#CONSOLE":
            return console_tab
        if selector == "#tab-content":
            return content
        if selector == "#header":
            return header
        raise AssertionError(selector)

    monkeypatch.setattr(app, "query_one", query_one)

    app.action_show_tab("CONSOLE")

    assert console_calls == [Path("/tmp/demo")]
    assert content.current == "CONSOLE"
    assert header.active_tab == "CONSOLE"


def test_resume_pick_recipe_scopes_console_to_selected_project(
    monkeypatch,
) -> None:
    app = PipNavApp()
    console_calls: list[Path | None] = []
    header = SimpleNamespace(active_tab=None)
    content = SimpleNamespace(current=None)
    console_tab = SimpleNamespace(
        clear_project_filter=lambda: console_calls.append(None),
        set_project_filter=lambda path: console_calls.append(path),
    )

    monkeypatch.setattr(app, "_selected_project_path", lambda: Path("/tmp/demo"))
    monkeypatch.setattr("pipnav.main.play_sound", lambda *_args, **_kwargs: None)

    def query_one(selector, *_args, **_kwargs):
        if selector == "#CONSOLE":
            return console_tab
        if selector == "#tab-content":
            return content
        if selector == "#header":
            return header
        raise AssertionError(selector)

    monkeypatch.setattr(app, "query_one", query_one)

    app._on_recipe_selected(
        SimpleNamespace(recipe=LaunchRecipe(name="Resume Pick", action="resume_pick"))
    )

    assert console_calls == [Path("/tmp/demo")]
    assert content.current == "CONSOLE"
    assert header.active_tab == "CONSOLE"
