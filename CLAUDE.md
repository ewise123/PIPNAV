# CLAUDE.md — PipNav

Fallout Pip-Boy themed TUI for navigating and launching dev projects from WSL. Built with Python + Textual.

## Run

```bash
cd ~/projects/PIPNAV
source .venv/bin/activate
pipnav
```

## Test

```bash
pytest
pytest -s  # with output
```

## Structure

- `pipnav/core/` — business logic, no Textual imports, independently testable
- `pipnav/ui/` — one widget per file, all CSS in `app.tcss`
- `tests/` — unit tests for core modules

## Conventions

- Python 3.10+, type hints, `pathlib.Path` for filesystem
- Frozen dataclasses for all data types (immutability)
- `@work(thread=True)` for blocking I/O (git, filesystem)
- Colors: `#8EFE55` (primary green), `#1A8033` (dim), `#0D2B0D` (background)
- Config/state in `~/.pipnav/` as JSON
- Errors: never crash, degrade gracefully, log to `~/.pipnav/debug.log`

## Keybindings

- `j/k` navigate, `h/l` switch focus left/right
- `Enter` drill into folder, `Backspace` go back
- `v` VS Code, `c` Claude Code, `r` resume Claude
- `Tab` or `1-4` switch tabs (STAT/FILES/LOG/SESSIONS)
- `/` search, `t` tag, `n` note, `~` CRT effects, `?` help, `q` quit
