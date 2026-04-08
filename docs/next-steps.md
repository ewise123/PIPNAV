# PipNav Next Steps

Date: 2026-04-08

## Current State

PipNav has a working core loop and five completed features from the original roadmap:

1. **Background Indexer + Live Watchers** — cached project state, incremental updates, polling watcher
2. **Session Control Center** — cross-project Claude session dashboard (CONSOLE tab) with status classification, filter/sort
3. **Workspace Profiles + Launch Recipes** — named workspace modes, custom launch builder, recipe editor, 5 built-in recipes
4. **Remote Control** — implemented as built-in launch recipes (server + interactive modes)
5. **Project Memory Layer** — structured per-project memory (handoff, next action, gotchas, prompts) with editor modal

Additionally, Feature 6 (Workflow Recipes / Quick Actions) is effectively complete — the recipe picker, custom launch builder, and recipe editor already cover what was spec'd.

**185 tests passing. 6 tabs. 30 keybindings. 7 modal screens.**

## Problems to Fix Before Adding More Features

These are bugs, gaps, and UX debt that should be addressed first.

### 1. Help overlay is stale

`pipnav/ui/help_overlay.py` documents the original keybindings but is missing:
- `n` — edit memory (was note, now memory editor)
- `N` — quick inline note
- `a` — recipe picker / quick actions
- `w` — switch workspace profile
- `f` — filter sessions (CONSOLE tab)
- `o` — sort sessions (CONSOLE tab)
- `R` keybinding is planned but not yet wired
- Tab 5 is CONSOLE, Tab 6 is INV (help still says 1-5)

Fix: rewrite the help text to match current bindings. Keep it accurate going forward by updating it in every feature PR.

### 2. SESSIONS tab and CONSOLE tab overlap

Two tabs show Claude sessions:
- **SESSIONS** (tab 4) — sessions for the currently selected project only
- **CONSOLE** (tab 5) — all sessions across all projects with filter/sort

This is confusing. The CONSOLE tab can already show per-project sessions if filtered.

Fix: Remove the SESSIONS tab entirely. When a project is selected in the left panel and the user switches to CONSOLE, auto-filter to that project's sessions. Add an "ALL" option to clear the project filter. This reduces tabs from 6 to 5: STAT | FILES | LOG | CONSOLE | INV.

Files affected:
- `pipnav/main.py` — remove SessionsTab from compose, update tab cycle, update focus_right, remove tab 4 binding, shift CONSOLE to 4 and INV to 5
- `pipnav/ui/header.py` — update TAB_NAMES
- `pipnav/ui/session_center_tab.py` — add project-scoped filtering (accept a project path, filter visible sessions to that project, show "viewing: ProjectName" indicator with a way to clear)
- `pipnav/ui/sessions_tab.py` — can be deleted or kept as dead code initially
- `pipnav/main.py` `_on_project_selected` — when CONSOLE tab is active, update its project filter

### 3. No profile editor in the UI

Users can create/edit recipes from within PipNav, but creating/editing profiles requires hand-editing `~/.pipnav/profiles.json`. The profile switcher modal is read-only.

Fix: Add a profile editor modal (similar to recipe_editor.py) accessible from the profile switcher. Fields: name, roots (comma-separated), hidden projects, color scheme, default recipe. Wire a "New Profile" and "Edit" option into the profile switcher modal.

Files affected:
- New file: `pipnav/ui/profile_editor.py`
- `pipnav/ui/profile_switcher.py` — add Edit/New options (like recipe_picker has Custom/New)
- `pipnav/main.py` — handle ProfileEditor.Saved event, save to profiles.json

### 4. Memory fields are buried in STAT

The STAT tab shows memory fields (handoff, next action, gotchas, prompts) at the bottom, after the README preview. For the memory to be useful, it needs to be prominent — especially handoff and next action, which are the first things you want to see when returning to a project.

Fix: Move memory fields above the README in the STAT tab render order. Show them right after CLAUDE and TAGS, before README. If handoff or next_action are populated, render them with emphasis (bold, or a visual separator).

Files affected:
- `pipnav/ui/project_detail.py` — reorder the `_render_detail` method to put memory fields before README

### 5. Status bar is getting crowded

The status bar currently shows: HP gauge, AP gauge, profile name, freshness indicator, and clock. On narrow terminals this will truncate.

Fix: Make the status bar adaptive. If terminal width < 100, hide the freshness indicator. If < 80, hide the profile name. The HP/AP gauges and clock should always show.

Files affected:
- `pipnav/ui/status_bar.py` — check `self.size.width` in `_refresh_display` and conditionally include segments

## Features to Build Next

After fixing the above, these are the two highest-value features remaining.

### 6. Inventory Portfolio Board (original roadmap #8)

The existing INV tab is a static DataTable dump. Upgrade it into a triage dashboard.

**What to build:**
- Filter bar at the top (like CONSOLE tab has) cycling through: ALL, DIRTY, STALE, ACTIVE (has Claude session), CLEAN
- Sort modes: name, last commit, modified count, attention score
- Attention score per project: weighted combination of is_dirty, is_stale, has_unpushed, has_session, days_since_commit
- Attention reason column showing why a project needs attention ("3 unpushed commits", "stale 45 days", "dirty + active session")
- `f` key cycles filter (context-sensitive: works in INV tab too, not just CONSOLE)
- `o` key cycles sort (same context sensitivity)

**New files:**
- `pipnav/core/portfolio.py` — attention scoring, filter definitions, sort functions

**Modified files:**
- `pipnav/ui/inventory_tab.py` — major upgrade: filter bar, attention column, sort modes
- `pipnav/main.py` — make `f`/`o` work in INV tab too (check `self._current_tab`)

**Data model:**
```python
@dataclass(frozen=True)
class PortfolioEntry:
    name: str
    path: Path
    branch: str
    modified_count: int
    last_commit: str
    attention_score: float
    attention_reason: str
    tags: tuple[str, ...]
```

### 7. Hook Profiles / Guardrails (original roadmap #9)

Let users manage Claude hook policies from PipNav.

**What to build:**
- Read Claude's hook configuration from `~/.claude/settings.json` and project-level `.claude/settings.json`
- Define built-in hook profile templates:
  - "Safe" — run tests before stop, log all Bash commands
  - "Strict" — require plan approval, no force push, no file deletion without confirmation
  - "Permissive" — minimal hooks
  - "Custom" — user-defined
- Modal to view current hooks, switch profiles, and see what each profile does
- Show active hook profile in STAT tab per project
- `g` keybinding opens guardrails/hook manager

**New files:**
- `pipnav/core/hooks.py` — read/write Claude settings hook config, built-in templates, HookProfile and HookDefinition dataclasses
- `pipnav/ui/hook_manager.py` — modal for viewing/switching hook profiles

**Modified files:**
- `pipnav/main.py` — add `g` keybinding, wire modal
- `pipnav/ui/project_detail.py` — show hook profile name in STAT
- `pipnav/core/config.py` — add `default_hook_profile: str = ""`

**Important:** Research Claude's hook configuration format first. Read `~/.claude/settings.json` to understand the actual schema for hooks (event types, command format, scope). The hook profiles should generate valid Claude settings, not a PipNav-specific format.

## Features to Skip or Defer Indefinitely

These features from the original roadmap should not be built now:

- **Agent Team Board (#7)** — Claude teams are experimental. Filesystem format undocumented and unstable. Wait for a stable API.
- **Loop + Automation Panel (#10)** — `/loop` tasks are session-scoped and invisible to PipNav. Nothing to display.
- **Headless Console (#11)** — Buildable as recipe extensions (run `claude -p` and save output to memory), not a standalone panel.
- **Subagent Pack Launcher (#12)** — Already possible via recipes with `--agent` flags. Not a separate feature.
- **Features 13-20** (Channels, GitHub Actions, Threat Meter, Patrols, Radio, Map, Replay, Worktree Bunker) — Parking lot. Revisit after the core is polished and the tool has real daily users.

## Sequencing

1. Fix help overlay (30 min)
2. Merge SESSIONS into CONSOLE (2-3 hours)
3. Move memory fields above README in STAT (15 min)
4. Add profile editor modal (1-2 hours)
5. Adaptive status bar (30 min)
6. Inventory Portfolio Board (3-4 hours)
7. Hook Profiles / Guardrails (3-4 hours)

Items 1-5 are polish/fixes. Items 6-7 are the last two features worth building before shifting to daily use and iteration based on real experience.

## Architecture Notes for Implementor

- All data models are frozen dataclasses in `pipnav/core/` (no Textual imports)
- One widget per file in `pipnav/ui/`, all CSS in `pipnav/ui/app.tcss`
- Background work uses `@work(exclusive=True, thread=True)` with `call_from_thread`
- State is stored as JSON in `~/.pipnav/` (config, memory, profiles, sessions, cache)
- Claude session data is read from `~/.claude/projects/{encoded-path}/*.jsonl`
- 4 color themes via Textual theme variables (`$primary`, `$secondary`, `$surface`)
- Keybindings blocked when Input is focused via `_CHAR_ACTIONS` set and `check_action`
- Watcher polls every 10s, triggers `_load_projects` but skips session center rebuild
- Tests use `monkeypatch` to redirect filesystem paths to `tmp_path`
- Never merge feature branches to main without explicit user permission
