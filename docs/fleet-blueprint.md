# PipNav Fleet — Blueprint

Date: 2026-09-10
Status: approved in principle, not started
Lane: real system (spans sessions, replaces the launch layer, full test coverage)

## What changes

PipNav stops spawning its own terminals and starts driving [herdr](https://herdr.dev)
as its runtime. PipNav remains the control plane — projects, filesystem navigation,
memory, launch recipes — and herdr owns every agent terminal.

Two consequences drive the whole design:

1. **Status stops being a guess.** `session_center.classify_session_status` currently
   infers status from message age. herdr watches the live terminal and reports
   `working | blocked | done | idle | unknown` per agent. "Blocked waiting on you"
   becomes knowable.
2. **PipNav sees agents it did not launch.** Anything running in herdr shows up,
   including sessions started by hand.

Three harnesses are in scope: Claude Code, Codex, OpenCode. All three support
launch-and-resume-by-id today (verified 2026-09-10).

## Decisions taken

| Question | Decision |
|---|---|
| Runtime | herdr as engine. WT/tmux launcher retained as graceful fallback only. |
| Project-management layer | **Not in scope.** PipNav keeps exactly the project browsing / filesystem / launch surface it has. |
| GitHub issues integration | Parked. Revisit after the core lands. |
| Landing view | FLEET. Project browser stays first-class with folder navigation and launch-in-any-folder intact — not demoted. |

## Architecture

```
                 ┌────────────────────────────────────────┐
    user  ─────► │  PipNav — control plane                │
                 │  projects · files · memory · recipes   │
                 └──────────────┬─────────────────────────┘
                                │  newline-delimited JSON
                                │  over ~/.config/herdr/herdr.sock
                 ┌──────────────▼─────────────────────────┐
                 │  herdr — runtime                       │
                 │  owns every pty, survives detach       │
                 └──┬───────────┬──────────┬──────────────┘
                    │           │          │
                 Claude       Codex     OpenCode
```

### New core modules

**`core/herdr.py`** — socket client. Newline-delimited JSON over a unix domain
socket. Stdlib `socket` + `json` only; no new dependency. Socket resolution order
matches herdr's own: `HERDR_SOCKET_PATH` env, then `HERDR_SESSION` env, then
`~/.config/herdr/herdr.sock`.

Methods PipNav needs:

| Method | Used for |
|---|---|
| `ping` | availability probe, drives the fallback decision |
| `session.snapshot` | bootstrap the fleet view in one round trip |
| `agent.list` | live status per agent |
| `agent.focus` | jump to a pane from the fleet view |
| `agent.prompt` | send a prompt without leaving PipNav |
| `workspace.create` / `workspace.list` / `workspace.focus` | one workspace per project |
| `tab.create`, `pane.split` | place a new agent |
| `events.subscribe` | push status changes, replaces polling |

The API negotiates supported methods at connect time and returns ordinary errors for
unsupported ones. **Every call must tolerate `method not supported` and a dead socket
without crashing** — herdr is at v0.9.0 and moving fast.

**`core/agents.py`** — the harness registry. One frozen dataclass per supported
agent describing: display name, binary, launch argv builder, resume argv builder,
and which session store to read. Adding a fourth agent is a data change, not a code
change.

Verified facts per harness:

| Agent | Session store | Resume |
|---|---|---|
| Claude Code | `~/.claude/projects/<encoded-path>/*.jsonl` | `claude --resume <id>` |
| Codex | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`; line 1 is a `session_meta` record carrying `id`, `cwd`, `timestamp` | `codex resume <id>` |
| OpenCode | `~/.local/share/opencode/opencode.db`, `session` table: `id`, `directory`, `title`, `time_updated`, `cost`, token counts | `opencode -s <id>` |

**`core/codex_sessions.py`** — walk the dated rollout tree, read **only the first
line** of each file for `session_meta`, take recency from file mtime. Rollout files
reach tens of megabytes; never parse them whole.

**`core/opencode_sessions.py`** — read-only SQLite query against a live database.
Open with `mode=ro` via URI, join `session` to `project`, and handle a locked or
mid-WAL-checkpoint database by returning empty rather than raising. Stdlib `sqlite3`.

OpenCode gives the richest row of the three: title, folder, last touched, cost, and
tokens all come free.

**`core/fleet.py`** — merges herdr's live view with on-disk history from all three
stores into one `FleetEntry` list. Absorbs `core/session_center.py`.

Precedence rule: **herdr is authoritative wherever it has an opinion; disk history
fills the rest** — yesterday's sessions, sessions on another machine, sessions
started outside herdr. Anything herdr does not see falls back to the existing
age-based classification, clearly marked as inferred rather than observed.

### Changed modules

- **`core/launcher.py`** — gains a herdr path: create a workspace for the project if
  absent, open a pane at the project directory, run the built argv. Existing
  `_build_launch_argv` WT/tmux code stays as the fallback when `ping` fails. PipNav
  must never become unusable because herdr is down.
- **`core/profiles.py`** — `LaunchRecipe` gains `agent: str = "claude"` and
  `claude_flags` generalises to `flags`. Existing profiles on disk keep working
  unchanged because the default is `claude`.
- **`core/audio.py`** — already exists, already plays sounds. Wire the blocked-agent
  event to a chime. No new code beyond the event handler.

### UI shape

Tabs become `FLEET | PROJECTS | FILES | LOG | INV`.

FLEET is the landing view: one row per live-or-recent agent across every project —
harness, project, observed status, current activity, age. `Enter` focuses that pane
in herdr, `r` resumes, `p` sends a prompt, `k` kills.

PROJECTS is today's left panel plus STAT, unchanged in behaviour: folder navigation,
drill in and out, launch an agent in any folder from one key.

This absorbs open defect #2 from `docs/next-steps.md` — the SESSIONS/CONSOLE tab
overlap disappears, because both collapse into FLEET.

## Phasing

Every phase ends with something visible on screen.

| Phase | Deliverable | Demo |
|---|---|---|
| 0 | herdr installed; `core/herdr.py` connects | PipNav lists live agents |
| 1 | Launch through herdr, fallback intact | `c` opens Claude in a herdr pane |
| 2 | `core/agents.py` registry; Codex + OpenCode launch | `c` prompts for which harness |
| 3 | Codex + OpenCode session readers | resume works for all three |
| 4 | `core/fleet.py` merge; FLEET as landing view | one screen, every agent, real status |
| 5 | `events.subscribe`; chime on blocked | walk away, get called back |
| — | GitHub issues | parked |

## Test plan

Write-first, per project convention. Show it failing before the code exists.

Heavy coverage — being wrong here is silent:

- **`core/fleet.py`** merge precedence. Two sources, explicit priority rules, and a
  wrong merge silently misreports which agent needs attention.
- **`core/agents.py`** argv construction. A dropped or misordered flag launches an
  agent in the wrong permission mode without any visible symptom.
- **`core/codex_sessions.py`** and **`core/opencode_sessions.py`**. Outside data
  entering the system: malformed JSON, truncated rollouts, missing `cwd`, locked
  database, schema drift. Validate at the boundary.
- **`core/herdr.py`** error paths: socket absent, socket dead mid-request, unknown
  method, malformed response, partial line.

No tests for: FLEET view layout, styling, keybinding wiring. Those get caught by
looking at the screen.

## Risks

1. **herdr is young.** v0.9.0, five months old, moving fast. The socket API version-
   negotiates, which helps, but treat every method as optional and degrade.
2. **Windows Terminal tabs go away.** The biggest habit change in this work, and the
   thing most likely to feel worse before it feels better. Phase 1 keeps the fallback
   partly so this is reversible.
3. **`opencode.db` is live.** Read-only access to a database another process is
   writing. Handle lock contention by returning empty, never by raising.
4. **Codex rollout size.** First line only, always.

## Notes for the implementor

Existing conventions hold and are not up for renegotiation here:

- `core/` has no Textual imports and is independently testable.
- Frozen dataclasses for every data type.
- One widget per file in `ui/`; all CSS in `ui/app.tcss`.
- `@work(exclusive=True, thread=True)` plus `call_from_thread` for blocking I/O.
- State as JSON under `~/.pipnav/`.
- Never crash; degrade and log to `~/.pipnav/debug.log`.
- Never merge to main without explicit permission.

The event subscription in phase 5 is a long-lived socket read. It needs its own
thread and a clean shutdown path — it is the first genuinely long-lived connection
PipNav has owned.

## Phase 0 findings (2026-09-10)

Verified against herdr 0.9.0, protocol 22, on this machine. Two of these
contradict or are absent from herdr's published docs.

1. **The server closes the connection after every response.** One request per
   connection; there is no persistent client to hold open. `core/herdr.py` opens
   a socket per call accordingly. Phase 5's `events.subscribe` is presumably the
   exception (the server keeps streaming) but that is unverified — confirm before
   building the event reader.
2. **`params` is required on every request**, including methods whose params are
   empty. Omitting the key is rejected as an invalid request.
3. **`pane.report_agent` accepts only `idle | working | blocked | unknown`.**
   `done` is derived by herdr itself — an agent that finished while its tab was
   unviewed — and cannot be reported. It *is* a valid value to read back from
   `agent.list`, so the client accepts all five.
4. **`herdr api schema --json` is the authoritative contract** — 102 methods with
   full request and response shapes. Prefer it over the website docs, which are
   thinner and in places out of date.
5. `AgentInfo` carries everything the fleet board needs: `pane_id`, `tab_id`,
   `workspace_id`, `agent`, `agent_status`, `cwd`, `agent_session` (`kind` +
   `value`, for resume), and `focused`.
6. **Activity text is weak for agents herdr detects but that set no title.**
   `AgentInfo.title` was absent entirely on a reported pane, leaving
   `terminal_title_stripped`, which on a shell pane is just the prompt. Real
   Claude and Codex panes are expected to set a useful title — verify in phase 1
   before adding any heuristic.

Also note: the project venv had lost `pytest`. Reinstalled via
`uv pip install --python .venv/bin/python pytest`.
