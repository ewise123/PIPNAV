# PipNav — Project Specification

## Overview

PipNav is a Fallout Pip-Boy themed terminal UI (TUI) for navigating and launching development projects from WSL. It replaces a simple taskbar shortcut with an interactive, keyboard-driven project launcher that surfaces useful project metadata at a glance and provides fast access to VS Code, Claude Code, and common project actions.

The tool is built for a single developer (personal use), launched from WSL via a Windows Terminal profile, and is not intended to be distributed.

---

## Goals

- Fast, keyboard-first project navigation with no mouse required
- Surface useful per-project context (git status, last modified, Claude Code session state)
- Launch VS Code, Claude Code (auto-mode), or resume Claude Code in one keypress
- Look and feel like a Fallout Pip-Boy — amber on black, CRT aesthetic, retro typography
- The retro effects (scanlines, flicker) are optional and toggleable

---

## Non-Goals (Out of Scope)

- Multi-machine sync or cloud storage
- Collaboration or sharing features
- File editing within the TUI (open in VS Code instead)
- Package manager or build system integration
- Plugin system
- Any GUI/web interface

---

## Tech Stack

- **Language:** Python 3.10+
- **TUI Framework:** [Textual](https://github.com/Textualize/textual)
- **Git integration:** `gitpython`
- **Filesystem:** `pathlib` (stdlib)
- **Launching external tools:** `subprocess` (stdlib)
- **Config/state persistence:** JSON files in `~/.pipnav/`
- **Packaging:** Single entry point script, optionally installable via `pip install -e .`

---

## Layout

The UI is a single-screen layout inspired by the Pip-Boy 3000. All panels are visible simultaneously (no modals, no page navigation except tabs).

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ██████╗ ██╗██████╗ ███╗   ██╗ █████╗ ██╗   ██╗                        │
│  ██╔══██╗██║██╔══██╗████╗  ██║██╔══██╗██║   ██║    [STAT] [FILES] [LOG] │
│  ██████╔╝██║██████╔╝██╔██╗ ██║███████║██║   ██║                        │
│  ██╔═══╝ ██║██╔═══╝ ██║╚██╗██║██╔══██║╚██╗ ██╔╝    HP ██████░░  78%    │
│  ██║     ██║██║     ██║ ╚████║██║  ██║ ╚████╔╝                         │
│  ╚═╝     ╚═╝╚═╝     ╚═╝  ╚═══╝╚═╝  ╚═╝  ╚═══╝                         │
├─────────────────────────────┬───────────────────────────────────────────┤
│ PROJECTS                    │ PROJECT DETAIL                            │
│ ─────────────────────────── │ ─────────────────────────────────────────│
│ > my-cool-app        [!M]   │  NAME:    my-cool-app                     │
│   portfolio-site     [✓ ]   │  PATH:    ~/projects/my-cool-app          │
│   api-service        [!U]   │  BRANCH:  main (+3 ahead)                 │
│   data-pipeline      [~ ]   │  STATUS:  3 modified, 1 untracked         │
│   old-experiment     [S ]   │  LAST:    2 hours ago                     │
│                             │  CLAUDE:  Session resumable               │
│                             │  README:  ─────────────────────────────── │
│                             │  A full-stack app for tracking ...        │
│                             │                                           │
├─────────────────────────────┴───────────────────────────────────────────┤
│  [ENTER] Open VS Code  [C] Claude Code  [R] Resume Claude  [/] Search   │
│  [T] Tag  [N] Notes  [F5] Refresh  [Esc] Quit  [~] Toggle CRT Effects   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Panels

**Header Bar**
- ASCII art "PIPNAV" logo (amber, bold)
- Tab switcher on right: `[STAT]` `[FILES]` `[LOG]`
- STAT tab: default view described above
- FILES tab: drill into the selected project's file tree, navigate and open files in VS Code
- LOG tab: git log for the selected project (last 20 commits, abbreviated)

**Project List (left panel)**
- Scrollable list of projects from the configured root directory
- Each row: project name + status badge (see Status Badges below)
- Active selection highlighted in amber
- Fuzzy search triggered by typing `/` then a query

**Project Detail (right panel)**
- Shows metadata for the currently selected project:
  - Name, full path
  - Git branch + ahead/behind count
  - Git working tree status (X modified, Y untracked, etc.)
  - Last modified timestamp (human-readable: "2 hours ago", "3 days ago")
  - Claude Code session status (see Claude Code Integration)
  - README preview: first ~5 lines of README.md, stripped of markdown syntax

**Status Bar (bottom)**
- Contextual keybinding hints based on current focus/tab
- Updates when context changes

---

## Status Badges

Each project in the list shows a compact badge:

| Badge | Meaning |
|-------|---------|
| `[✓ ]` | Git clean, no pending changes |
| `[!M]` | Has modified/staged files |
| `[!U]` | Commits ahead of remote (unpushed) |
| `[~ ]` | Stale — not opened in 30+ days |
| `[S ]` | Has a resumable Claude Code session |
| `[? ]` | Not a git repo |

Badges can stack — show the highest-priority one (S > !U > !M > ~ > ✓ > ?)

---

## Keybindings

| Key | Action |
|-----|--------|
| `↑` / `↓` or `j` / `k` | Navigate project list |
| `Enter` | Open selected project in VS Code |
| `c` | Launch Claude Code (auto-mode) on selected project |
| `r` | Resume last Claude Code session on selected project |
| `f` | Open selected project folder in VS Code (no specific file) |
| `/` | Enter fuzzy search mode |
| `Esc` | Exit search / quit |
| `Tab` | Cycle through top tabs (STAT / FILES / LOG) |
| `1` / `2` / `3` | Jump to STAT / FILES / LOG tab directly |
| `t` | Tag/untag selected project (cycle through user-defined tags) |
| `n` | Open inline note editor for selected project |
| `F5` | Refresh all project metadata |
| `` ` `` or `~` | Toggle CRT effects (scanlines + flicker) |
| `?` | Show full keybinding help overlay |
| `q` | Quit |

---

## Project Discovery

- On launch, scan a configurable root directory (default: `~/projects`) for subdirectories
- Each immediate subdirectory is treated as a project
- Optionally support multiple root directories (configured in `~/.pipnav/config.json`)
- Hidden directories (starting with `.`) are excluded
- Depth: only scan one level deep (no recursive project discovery)

---

## Git Integration

For each project directory, check:
- Whether it is a git repo (`git rev-parse --is-inside-work-tree`)
- Current branch name
- Ahead/behind count vs. remote tracking branch
- Working tree status: count of modified, staged, untracked files
- Last commit timestamp

Use `gitpython` for this. Cache results per-project and refresh on `F5` or on project selection focus.

Do not fail hard if git is slow or unavailable — show `[?]` and continue.

---

## Claude Code Integration

Track Claude Code sessions per project using a JSON state file at `~/.pipnav/sessions.json`.

Structure:
```json
{
  "~/projects/my-cool-app": {
    "last_session": "2025-03-28T14:22:00",
    "resumable": true
  }
}
```

**Launching Claude Code (auto-mode):**
```bash
claude --dangerously-skip-permissions /path/to/project
```

**Resuming Claude Code:**
```bash
claude --resume /path/to/project
```

When the user presses `c` or `r`, PipNav updates `sessions.json` to record the launch, then hands off to Claude Code by opening a new terminal pane or running the command in the current terminal.

> Note: Verify the exact Claude Code CLI flags during implementation — check `claude --help` and update these commands if the flags differ.

Session state is shown in the detail panel as:
- `Session resumable` — a previous session exists
- `No session` — first time opening this project with Claude Code

---

## Tags and Notes

**Tags:**
- User-defined strings stored in `~/.pipnav/config.json`
- Example tags: `work`, `personal`, `archived`, `active`
- Press `t` to cycle through available tags for the selected project
- Tags shown as a small label in the detail panel (not in the list badge — too noisy)

**Notes:**
- Press `n` to open a single-line inline note editor at the bottom of the detail panel
- Notes stored per-project in `~/.pipnav/notes.json`
- Shown in the detail panel below the README preview
- Max 200 characters

---

## CRT / Pip-Boy Visual Effects

All effects are CSS-level (Textual supports custom CSS).

**Always on (core aesthetic):**
- Amber (`#FFB000`) text on black (`#0A0A0A`) background
- Monospace font throughout
- Box-drawing characters for all borders
- Subtle text glow using Textual's `text-style` where supported

**Toggleable (default: OFF, toggle with `` ` ``):**
- Scanline overlay: alternating faint dark horizontal lines over the entire screen
- Cursor flicker: the selected row pulses slightly in brightness
- Boot sequence: on first launch, animate a fake "ROBCO INDUSTRIES UNIFIED OPERATING SYSTEM" boot screen for ~2 seconds before showing the main UI (skip with any key)

Toggle state persisted in `~/.pipnav/config.json`.

---

## Configuration File

Location: `~/.pipnav/config.json`

```json
{
  "project_roots": ["~/projects"],
  "crt_effects": false,
  "tags": ["work", "personal", "archived", "active"],
  "stale_threshold_days": 30,
  "vscode_command": "code",
  "claude_command": "claude"
}
```

All fields have sensible defaults. The file is created on first run if it does not exist.

---

## Launch / Installation

The tool should be launchable with a single command: `pipnav`

Install via:
```bash
pip install -e .
```

For WSL + Windows Terminal integration:
- Add a new profile in Windows Terminal settings pointing to:
  `wsl.exe -e bash -c "pipnav"`
- Set a custom color scheme matching the Pip-Boy aesthetic (amber on black) in Windows Terminal
- Optionally set a custom icon

A `README.md` in the repo should document the Windows Terminal profile setup.

---

## File Structure

```
pipnav/
├── pipnav/
│   ├── __init__.py
│   ├── main.py           # Entry point, App class
│   ├── ui/
│   │   ├── app.tcss      # Textual CSS (Pip-Boy theme)
│   │   ├── project_list.py
│   │   ├── project_detail.py
│   │   ├── files_tab.py
│   │   ├── log_tab.py
│   │   └── boot_screen.py
│   ├── core/
│   │   ├── config.py     # Config read/write
│   │   ├── projects.py   # Project discovery and metadata
│   │   ├── git.py        # Git integration
│   │   └── launcher.py   # VS Code / Claude Code launch logic
│   └── data/
│       ├── sessions.json # Claude Code session state
│       ├── notes.json    # Per-project notes
│       └── config.json   # User config
├── CLAUDE.md
├── SPEC.md
├── pyproject.toml
└── README.md
```

---

## Error Handling

- If a project directory no longer exists: show it greyed out with a `[MISSING]` badge, offer to remove it from the list
- If git is not installed or not available: skip git metadata, show `[?]` badge
- If VS Code (`code`) is not on PATH: show an error in the status bar and prompt user to configure `vscode_command` in config
- If Claude Code (`claude`) is not on PATH: same treatment
- Never crash on metadata fetch failure — degrade gracefully and show what's available

---

## Future Ideas (Not in Scope for v1)

- Per-project environment variable loading (`.env` preview)
- "Recently opened files" per project (from VS Code history)
- Project templates / scaffolding
- Notification when a Claude Code session completes
- Quick terminal pane split to run commands in project directory
