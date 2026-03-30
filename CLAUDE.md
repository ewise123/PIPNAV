# CLAUDE.md — PipNav

This file is read by Claude Code before starting any task. Follow all instructions here throughout the project.

---

## What This Project Is

PipNav is a Fallout Pip-Boy themed TUI (terminal UI) for navigating and launching development projects from WSL. Built with Python + Textual. See `SPEC.md` for full requirements.

---

## How to Run

```bash
# Install in development mode (run once)
pip install -e .

# Launch the app
pipnav

# Run without installing
python -m pipnav.main
```

---

## How to Test

```bash
# Run all tests
pytest

# Run with output (useful for debugging TUI logic)
pytest -s

# Run a specific file
pytest tests/test_git.py
```

There is no automated TUI rendering test — test the business logic (git parsing, config, project discovery, launcher commands) in unit tests. Manual testing covers the visual layer.

---

## Project Structure

```
pipnav/
├── pipnav/
│   ├── main.py           # App entry point
│   ├── ui/               # Textual widgets and screens
│   ├── core/             # Business logic (no Textual imports here)
│   └── data/             # Runtime state (gitignored)
├── tests/
├── CLAUDE.md             # This file
├── SPEC.md               # Full feature specification
└── pyproject.toml
```

Keep `core/` free of Textual imports. Business logic must be independently testable.

---

## Conventions

### Python Style
- Python 3.10+
- Type hints on all function signatures
- Docstrings on all public functions and classes (one-line is fine for simple ones)
- `pathlib.Path` for all filesystem operations — never raw string paths
- No global mutable state — pass config and state explicitly

### Textual Conventions
- One widget per file in `ui/`
- All CSS in `app.tcss` — no inline styles
- Use `reactive` for any state that affects rendering
- Use `worker` for any blocking I/O (git calls, filesystem scans) to keep the UI responsive

### Error Handling
- Never let metadata failures crash the app — catch exceptions in git/filesystem calls and return a degraded result
- Log errors to a debug log file at `~/.pipnav/debug.log`, not to stdout (stdout breaks the TUI)
- User-visible errors go in the status bar, not as popups

### Configuration and State
- Config: `~/.pipnav/config.json` — user settings, persisted across runs
- Sessions: `~/.pipnav/sessions.json` — Claude Code session state
- Notes: `~/.pipnav/notes.json` — per-project notes
- All three files are created with defaults on first run if missing
- Never hardcode paths — always use `Path.home() / ".pipnav" / "filename.json"`

---

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `textual` | TUI framework |
| `gitpython` | Git repo introspection |
| `rich` | Text rendering (comes with Textual) |

No other third-party dependencies unless clearly justified. Prefer stdlib.

---

## Pip-Boy Aesthetic — Non-Negotiable

The visual theme is the point of this project. Do not compromise it for convenience.

- **Colors:** Amber `#FFB000` text on black `#0A0A0A` background. No other text colors except:
  - Dimmed/secondary info: `#996600` (darker amber)
  - Error states: `#FF4444` (red)
  - Success/clean state: `#00FF41` (matrix green, used sparingly)
- **Font:** Monospace throughout. No proportional fonts anywhere.
- **Borders:** Box-drawing characters only (`─`, `│`, `┌`, `┐`, `└`, `┘`, `├`, `┤`, `┬`, `┴`, `┼`)
- **CRT effects** (scanlines, flicker) are toggleable. Default OFF. Implement as a CSS overlay.

---

## External Tool Integration

**VS Code:**
```python
subprocess.Popen(["code", str(project_path)])
```

**Claude Code — auto-mode:**
```python
subprocess.Popen(["claude", "--permission-mode", "auto", str(project_path)])
```

**Claude Code — resume:**
```python
subprocess.Popen(["claude", "--resume", str(project_path)])
```

> Before using these commands, verify the exact flags with `claude --help` and `code --help`. Update this file and the launcher if the flags differ.

Launch in a new process (non-blocking). PipNav stays open after launching.

---

## What To Build First (Suggested Order)

1. Project scaffold: `pyproject.toml`, entry point, empty Textual App that launches
2. Config system: read/write `~/.pipnav/config.json` with defaults
3. Project discovery: scan root dir, return list of project paths
4. Git metadata: branch, status, ahead/behind, last commit time
5. Basic UI: project list (left) + detail panel (right), keyboard navigation
6. Pip-Boy theme: `app.tcss` with full amber-on-black styling, box borders
7. Launcher: VS Code and Claude Code launch actions
8. Session tracking: read/write `sessions.json`, show session status in detail panel
9. Fuzzy search: `/` to enter search, filter project list
10. FILES tab: file tree for selected project
11. LOG tab: git log for selected project
12. Tags and Notes
13. CRT effects: scanlines + flicker toggle
14. Boot screen animation
15. Polish: keybinding help overlay, error states, status bar hints

Build and manually test each step before moving to the next. Do not skip ahead.

---

## Out of Scope — Do Not Build

- Web interface
- Multi-user or sync features
- File editing within the TUI
- Plugin system
- Anything not described in SPEC.md

If something seems like a natural extension, add it to the "Future Ideas" section of SPEC.md instead of building it.
