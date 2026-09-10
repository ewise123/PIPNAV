# PipNav Fleet — Blueprint

Date: 2026-09-10 (revised same day, see *Revision* below)
Status: phases 0-1 merged to `main`; plan revised, phase 2 not started
Lane: real system

## What PipNav becomes

**A project browser and launcher that lives in a pane beside your agents.**

herdr owns every terminal. PipNav owns your projects: the folder tree, the git
state, the memory notes, the launch recipes, and the ability to start or resume
Claude Code, Codex or OpenCode in any folder with one key. PipNav runs as a
**herdr plugin pane**, so launching an agent opens it in the split next to you.

```
┌─ one window: herdr ────────────────────────────────────────────────┐
│ ┌ PipNav (plugin pane) ───┐ ┌ the agent, live ───────┐ ┌ sidebar ┐ │
│ │  ai-pulse         [!M]  │ │  ● Claude Code         │ │ scratch │ │
│ │ ▸PIPNAV           [!M]  │ │    Writing tests…      │ │  claude │ │
│ │  project-iq    [!M][~]  │ │                        │ │ PIPNAV  │ │
│ │  c claude  x codex      │ │                        │ │  codex! │ │
│ │  o opencode  r resume   │ │                        │ │         │ │
│ └─────────────────────────┘ └────────────────────────┘ └─────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

## Revision — why this plan shrank

The first version of this blueprint had PipNav building a live agent status
board (the FLEET tab). That was wrong: **herdr's own sidebar already shows every
agent's status across every project, permanently, two inches to the left.** We
were about to build a status board next to a status board.

Two alternatives were considered and ruled out:

- **PipNav hosting terminals itself** (becoming the multiplexer). Not viable.
  Textual has no terminal widget; the only third-party one emulates a terminal in
  pure Python, is unmaintained, and is too slow for a full-screen agent TUI. This
  would mean writing a terminal emulator in Python — precisely what herdr already
  is, in Rust.
- **Keeping FLEET as a status board anyway.** Rejected: duplicates the sidebar.

So PipNav keeps the jobs herdr cannot do, and drops the rest:

| Job | Owner |
|---|---|
| Terminals, panes, persistence, live agent status, blocked-agent notifications | **herdr** |
| Your projects, folder navigation, git state, memory notes, launch recipes | **PipNav** |
| Launching and resuming Claude / Codex / OpenCode per project | **PipNav** |
| Session history across all three harnesses | **PipNav** |

## Decisions taken

| Question | Decision |
|---|---|
| Runtime | herdr. PipNav never owns a terminal. |
| PipNav's home | A herdr plugin pane, split placement. Standalone TUI kept as fallback. |
| Project-management layer | Not in scope. GitHub issues parked. |
| Placement | One herdr workspace per project; a second agent in a project gets its own tab. |
| FLEET tab | **Deleted.** It duplicated herdr's sidebar, and could never show agents herdr did not start. Folded into CONSOLE. |
| Blocked-agent chime | herdr's (`notification show --sound request`). Dropped from our scope. |

## The plugin

`herdr-plugin.toml` at the repo root, plus `herdr/pipnav-pane.sh`. Link with:

```
herdr plugin link /path/to/PIPNAV
```

The wrapper resolves the project virtualenv from `HERDR_PLUGIN_ROOT`, so no path
is hardcoded. Verified working: PipNav renders fully inside a herdr split pane,
with real git state and README, from a repo-relative link.

Plugin panes receive a useful environment for free:

| Variable | Use |
|---|---|
| `HERDR_SOCKET_PATH` | the API socket, already honoured by `core/herdr.py` |
| `HERDR_ENV=1` | tells PipNav it is inside herdr (`in_herdr()`) |
| `HERDR_PLUGIN_ROOT` | locate the virtualenv without hardcoding a home directory |
| `HERDR_PLUGIN_CONTEXT_JSON` | workspace id and label, workspace cwd, focused pane cwd and status |
| `HERDR_PLUGIN_STATE_DIR` / `_CONFIG_DIR` | per-plugin storage, if ever needed |
| `HERDR_BIN_PATH` | the herdr binary, for CLI calls |

`HERDR_PLUGIN_CONTEXT_JSON` is worth using: it tells PipNav which project
workspace it was opened in, so the pane can preselect that project.

## Architecture

### Built and merged

- **`core/herdr.py`** — socket client over `~/.config/herdr/herdr.sock`. Stdlib
  only. Degrades to unavailable/empty, never raises at PipNav. Includes
  `agent_name()` (herdr's naming rules) and `_undo_placement` (clean up a pane
  whose agent failed to start).
- **`core/launcher.py`** — `launch_claude` prefers herdr, falls back to WT/tmux
  only when herdr is not running. `_claude_flags` shared by both routes.
- **`main.py`** — `_launch_note` names the destination when PipNav is not itself
  inside herdr.
- **`ui/session_center_tab.py`** — CONSOLE, now cross-project and cross-tool with LIVE badges. `ui/fleet_tab.py` is deleted.

### Still to build

**`core/agents.py`** — the harness registry, and now the centre of PipNav's
value. One frozen dataclass per harness: display name, binary, herdr `kind`,
launch argv builder, resume argv builder, session store reader. Adding a fourth
harness becomes a data change.

Verified per harness (2026-09-10, on this machine):

| Harness | herdr kind | Session store | Resume |
|---|---|---|---|
| Claude Code | `claude` | `~/.claude/projects/<encoded-path>/*.jsonl` | `claude --resume <id>` |
| Codex | `codex` | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`, line 1 `session_meta` carries `id` + `cwd` | `codex resume <id>` |
| OpenCode | `opencode` | `~/.local/share/opencode/opencode.db`, `session` table: `id`, `directory`, `title`, `time_updated`, `cost`, tokens | `opencode -s <id>` |

herdr recognises 21 agent kinds; all three of ours are among them.

**`core/codex_sessions.py`** — walk the dated rollout tree, read **only the
first line** of each file, take recency from mtime. Rollouts reach tens of MB.

**`core/opencode_sessions.py`** — read-only SQLite (`mode=ro` URI) against a live
database. Return empty on lock contention rather than raising. Stdlib `sqlite3`.
Richest rows of the three: title, folder, last touched, cost, tokens.

**`core/sessions_all.py`** — one list of every past session across the three
harnesses, per project, newest first, each resumable. Live ones get a LIVE badge
from `herdr.list_agents()`. Absorbs `core/session_center.py`.

The live badge is an *annotation*, not a board. PipNav does not rank, filter or
alert on live status; herdr does that.

## Phasing

| Phase | Deliverable | Demo | State |
|---|---|---|---|
| 0 | herdr socket client | PipNav lists live agents | **done, merged** |
| 1 | launch into herdr panes | `c` opens Claude in a pane | **done, merged** |
| 1b | plugin manifest | PipNav opens as a split beside an agent | **verified, uncommitted** |
| 2 | `core/agents.py`; Codex + OpenCode launch | `c`/`x`/`o` start any of three | next |
| 3 | Codex + OpenCode session readers | resume any of three by id | |
| 4 | CONSOLE: all tools, one list, LIVE badges; FLEET deleted | one place to resume anything | **done** |
| ~~5~~ | ~~events + chime~~ | **dropped — herdr notifies** | |
| — | GitHub issues | parked | |

Phase 4 also settles the open defect in `docs/next-steps.md`: the SESSIONS and
CONSOLE tabs both showing Claude sessions. One list replaces both, and the FLEET
tab built in phase 0 folds into it. The `HERDR` status-bar indicator stays — it
is cheap and answers "is the runtime up".

## Test plan

Write-first. Heavy coverage where being wrong is silent:

- **`core/agents.py`** argv construction. A dropped flag launches an agent in the
  wrong permission mode with no visible symptom.
- **`core/codex_sessions.py`**, **`core/opencode_sessions.py`**. Outside data at a
  trust boundary: malformed JSON, truncated rollouts, missing `cwd`, a locked
  database, schema drift after an update.
- **`core/sessions_all.py`** dedup and ordering across three stores, and the LIVE
  badge matching the right session.
- **`core/herdr.py`** error paths — done, 47 tests.

Assert wire payloads, not just return values. Phase 0 shipped a bug
(`focus_agent` sending `pane_id` where herdr wants `target`) that a return-value
test could not catch.

Unit tests must not depend on whether herdr is running. `tests/test_launcher.py`
has an autouse `_herdr_absent` fixture; anything touching the socket needs the
same. Before it existed, running the suite on a machine with herdr up started a
real Claude process and left a stray workspace behind.

Not tested: pane layout, styling, keybinding wiring.

## Risks

1. **herdr is young** — v0.9.0, five months old. Treat every method as optional
   and degrade. Plugin v1 has no runtime action registration and no native
   non-terminal UI; we need neither.
2. **PipNav becomes a thing you run inside herdr.** Standalone mode stays, but
   the good experience is the plugin one. This is the real adoption cost.
3. **`opencode.db` is live** — another process writes it while we read.
4. **Codex rollout size** — first line only, always.
5. **WSL fallback untested.** The dev host `ca-agent-host` is plain Linux, so the
   fallback there takes the tmux path. The `wt.exe` branch has unit tests but has
   not been watched working.

## The user's actual setup (2026-09-10)

Worth recording, because it corrected an assumption in the first draft. The user
SSHes from a Windows machine to `ca-agent-host` and already lives in a **tmux**
session named `pipnav`, created Aug 31:

```
tmux session "pipnav"
  1: pipnav   python     ← PipNav
  2: SSAPRO   claude     ← sessions PipNav launched, as tmux windows
  3-6: …      claude
```

So "one window, switch inside it" is not a change for this user — it is what
they already do, via tmux. herdr replaces tmux in that role, with the same `C-b`
prefix and mouse already on in both. Earlier warnings in this document about
losing per-project Windows Terminal tabs were wrong: `_is_wsl()` is false on this
host, so that code path never ran for them.

Sessions started outside herdr (their five long-running ones) cannot be adopted
into it retroactively. They remain visible via session history, never as live
agents.

## herdr findings

Verified against herdr 0.9.0, protocol 22. Several contradict or are absent from
herdr's published docs. `herdr api schema --json` is the authoritative contract —
102 methods with full request and response shapes; prefer it over the website.

1. **The server closes the connection after every response.** One request per
   connection. Event subscriptions are presumably the exception; unverified.
2. **`params` is required on every request**, even when empty.
3. **`agent.*` methods address by `target`; only `agent.start` takes `pane_id`.**
   Copying the `agent.start` shape elsewhere gives `missing field 'target'`.
   Shipped as a bug in phase 0, now fixed.
4. **Agent names: `^[a-z][a-z0-9_-]{0,31}$`, unique among live agents.** A fixed
   name per kind allows exactly one Claude to exist anywhere. Not in the schema.
5. **Creating a pane and running an agent are two calls.** Neither
   `workspace.create`, `tab.create` nor `pane.split` takes a command.
   `workspace.create` also makes a first tab and pane, so the first agent in a
   project needs no `tab.create`. `agent.start` returns the argv it ran.
6. **A failed `agent.start` leaves a stray workspace or tab** unless closed.
7. **A freshly started agent is not ready for input.** Claude Code opens on its
   "do you trust this folder?" prompt; text sent then answers the dialog and
   exits the agent. Gate any prompt-sending on `launch_pending` /
   `interactive_ready`.
8. **`pane.report_agent` accepts only `idle | working | blocked | unknown`.**
   `done` is server-derived and readable but not reportable. Per herdr's own
   skill doc, `idle` and `done` both mean "ready for input"; only `blocked`
   means a human is needed.
9. **Activity text is weak.** A real Claude pane's terminal title was the launch
   command, then `Claude Code` — an app name, not activity. Useful activity text
   needs `agent.read`, not the terminal title.
10. **Plugin panes**: `[[panes]]` in the manifest; `width`/`height` are accepted
    only for `popup` placement, not `split`.
11. `pane.read` nests its payload under `read`.
12. Multiple clients attach to one server, each viewing its own workspace — two
    terminal windows onto the same session is supported (verified).
13. herdr warns if tmux `focus-events` is off. Better not to nest herdr inside
    tmux at all: both use `C-b`.

Also: the project venv had lost `pytest`; reinstalled with
`uv pip install --python .venv/bin/python pytest`.


## Phase 4 findings (2026-09-10)

17. **herdr cannot see agents it did not start.** Proved with five Claude
    sessions running in the user's tmux session while `agent.list` returned
    zero. So a "live agents" board in PipNav could only ever show a subset of
    what herdr shows, which is why the FLEET tab was deleted rather than grown.
18. **herdr records a Claude session id within about 8 seconds** of the agent
    starting, as an `id`-kind session reference. That is what the LIVE badge
    matches on.
19. **A brand-new session has nothing to mark LIVE.** Claude does not write its
    `.jsonl` until first prompted, so PipNav cannot list it, so there is no row
    to badge. LIVE therefore means "a session with history that is running right
    now" — which is the useful case: it stops you starting a second agent on
    work already open.
20. **Only id-kind references are matched.** Where herdr reports no session
    reference, nothing is marked. A false LIVE badge is worse than none.
21. Resuming from PipNav a session that is already alive outside herdr opens a
    SECOND agent, because herdr cannot attach to a process it did not start.
    Unavoidable; worth knowing.
