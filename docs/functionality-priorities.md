# PipNav Functionality Priorities

Date: 2026-03-31

## Goal

Evolve PipNav from a stylish project launcher into a Claude-centric operations console for local development, orchestration, and automation.

The best strategic framing is:

- Core role: local command center for projects, sessions, worktrees, and agent activity.
- Secondary role: bridge between local workflows and Claude surfaces like Remote Control, agent teams, hooks, scheduled tasks, channels, and GitHub Actions.
- Tertiary role: delight layer that makes the app memorable and fun to use.

## Priority Model

- `P0` = highest leverage, should shape the next major iterations.
- `P1` = strong follow-on work that compounds the P0 foundation.
- `P2` = strategic or higher-risk expansion.
- `P3` = novelty and delight; worth doing only after the core loop is strong.

## Ordered Roadmap

| Rank | Priority | Feature | Why It Matters |
| --- | --- | --- | --- |
| 1 | P0 | Session Control Center | Makes PipNav feel like the home screen for Claude work, not just a launcher. |
| 2 | P0 | Workspace Profiles + Launch Recipes | Reduces friction and standardizes repeatable workflows. |
| 3 | P0 | Background Indexer + Live Watchers | Required foundation for a truly live UI. |
| 4 | P0 | Remote Control Manager | High-value Claude feature with immediate user benefit. |
| 5 | P0 | Project Memory Layer | Gives every project durable context and handoff state. |
| 6 | P0 | Workflow Recipes / Quick Actions | Converts common tasks into one-key operational flows. |
| 7 | P1 | Agent Team Board | Strong fit for PipNav once session management is solid. |
| 8 | P1 | Inventory Portfolio Board | Turns project inventory into a true operational overview. |
| 9 | P1 | Hook Profiles / Guardrails | Adds safety, consistency, and automation policy. |
| 10 | P1 | Loop + Automation Panel | Makes Claude scheduling visible and manageable. |
| 11 | P1 | Headless / Stream JSON Console | Unlocks structured non-interactive Claude workflows. |
| 12 | P1 | Subagent Pack Launcher | Helps standardize specialized local workflows. |
| 13 | P2 | Channels Hub | Potentially huge, but preview-stage and security-sensitive. |
| 14 | P2 | GitHub Actions Bridge | Useful, but less central than local session orchestration. |
| 15 | P2 | Threat Meter / Trust Panel | Important once channels and automation expand. |
| 16 | P2 | Patrol Routes | Durable automation layer for recurring repo health checks. |
| 17 | P3 | Radio Feed | Great ambient UX once enough live events exist. |
| 18 | P3 | Wasteland Map | Strong visual identity, lower direct leverage. |
| 19 | P3 | Holotape Replay | High-cool-factor session archaeology tool. |
| 20 | P3 | Worktree Bunker Mode | Great thematic polish around worktree isolation. |

## Recommended Phase Plan

- Phase 1: ranks 1 through 4. Make PipNav an excellent Claude launcher and live session dashboard.
- Phase 2: ranks 5 through 10. Add memory, orchestration, safety, and scheduling.
- Phase 3: ranks 11 through 16. Expand into structured automation and external event integration.
- Phase 4: ranks 17 through 20. Add high-character novelty once the operational core is strong.

## Detailed Specs

### 1. Session Control Center

Priority: `P0`

Spec:
Replace the current narrow session view with a primary operational screen that shows all known Claude activity across projects. This becomes the default place to start and resume work.

Complete looks like:

- Shows active, resumable, idle, blocked, and failed sessions across all tracked projects.
- Displays branch, worktree, last user prompt, message count, age, permission mode, and whether Remote Control is enabled.
- Supports core actions from one place: launch, resume, interrupt, open project, open worktree, and jump to transcript details.
- Refreshes automatically in the background without freezing the UI.

Failure modes:

- Session state is stale or wrong because PipNav only sees old transcript data.
- Session rows flicker or reorder too aggressively while files update.
- Resuming the wrong session becomes easy because metadata is too shallow.

Risks:

- Relies on Claude local storage layout staying parseable.
- Live scanning can become expensive with many projects and many sessions.

Potential mitigation:

- Separate "observed from transcript" from "confirmed running" status.
- Cache parsed session metadata and update incrementally.
- Prefer stable sort keys and explicit session IDs in the UI.

### 2. Workspace Profiles + Launch Recipes

Priority: `P0`

Spec:
Allow named workspace modes such as `client-work`, `experiments`, `infra`, or `review-mode`, each with roots, filters, default Claude flags, theme, and preferred actions.

Complete looks like:

- Users can save and switch named profiles from inside PipNav.
- A profile can define roots, tags, hidden projects, preferred model, preferred agent, worktree behavior, and default launch recipe.
- Launch recipes can encode actions like "resume latest session", "open in worktree", "start review agent", or "launch Claude with extra dirs".
- Profile switching updates the visible workspace immediately.

Failure modes:

- Profiles become a second config system that is confusing or redundant.
- Recipes become too low-level and feel like raw CLI wrappers.
- Profiles silently fail when paths or tools are missing.

Risks:

- Config complexity can outgrow the current simple JSON model quickly.

Potential mitigation:

- Keep profile schema opinionated and small.
- Validate recipes before saving and show missing dependencies clearly.
- Provide a few built-in templates so users do not start from a blank page.

### 3. Background Indexer + Live Watchers

Priority: `P0`

Spec:
Introduce a background indexer that maintains a cache of project metadata, git status, session metadata, worktrees, and automation state. Many higher-priority features depend on this.

Complete looks like:

- PipNav starts with cached data quickly, then hydrates live status in the background.
- File watchers or polling keep project, git, and Claude metadata fresh without manual refresh.
- Expensive operations are isolated from the UI thread.
- The app can explain freshness, such as "updated 8s ago" or "scan in progress".

Failure modes:

- Background work starves the UI or creates battery and CPU drain.
- Multiple watchers disagree and produce oscillating state.
- Cache corruption causes bad data to persist across launches.

Risks:

- Cross-platform filesystem watching and git/session scanning can get tricky.

Potential mitigation:

- Start with hybrid polling plus cache invalidation before adding deeper watcher complexity.
- Use bounded refresh intervals and per-project debounce.
- Make the cache disposable and rebuildable at any time.

### 4. Remote Control Manager

Priority: `P0`

Spec:
Expose Claude Remote Control as a first-class PipNav feature so a project can be made remotely steerable from Claude web or mobile with clear status and launch modes.

Complete looks like:

- PipNav can start and stop Remote Control for a selected project.
- UI exposes spawn mode choices like same-dir, worktree, or session.
- UI shows whether the local environment is eligible, authenticated, and currently serving remote sessions.
- Active remote-served sessions are visible in the main session center.

Failure modes:

- Users try to use it without a valid Claude subscription or proper auth.
- Remote Control starts but the workspace trust dialog or repo requirements block practical use.
- Multiple remote sessions collide in the same directory.

Risks:

- Claude CLI behavior or flags may evolve over time.
- Worktree mode adds complexity and can expose edge cases in dirty repos.

Potential mitigation:

- Perform capability checks before showing launch actions.
- Offer same-dir as the simplest default and worktree as an advanced mode.
- Surface prerequisites directly in the UI before launch.

### 5. Project Memory Layer

Priority: `P0`

Spec:
Expand notes and tags into durable project memory for human and agent workflows: handoff summaries, preferred prompts, known gotchas, current mission, and next action.

Complete looks like:

- Each project has structured memory fields rather than only tags plus one note.
- Users can save handoff state such as "what Claude was doing", "what is blocked", and "what to do next".
- PipNav can inject memory into launch recipes or expose it prominently before resume.
- Memory is easy to skim and easy to update during context switches.

Failure modes:

- Memory becomes stale and misleading.
- Users stop trusting the feature if it is too verbose or hard to maintain.
- It overlaps confusingly with `CLAUDE.md` or Claude's own memory systems.

Risks:

- Ambiguous boundaries between human notes, project instructions, and Claude-specific memory.

Potential mitigation:

- Keep memory fields explicit: human handoff, operational state, launch hints, durable facts.
- Timestamp edits and show recency.
- Treat `CLAUDE.md` as project instruction and PipNav memory as operational state.

### 6. Workflow Recipes / Quick Actions

Priority: `P0`

Spec:
Bundle repeatable flows into named actions, not just raw tool launches. Examples: review the current branch, open latest failed repo, start a worktree feature branch, watch a deployment, or summarize a repo.

Complete looks like:

- Users can trigger a recipe with one key or command palette action.
- Recipes can chain local setup, Claude launch flags, preferred agent, worktree mode, and follow-up UI focus.
- PipNav includes a useful starter set of recipes tuned for Claude-heavy work.
- Recipes are visible and discoverable, not buried in config.

Failure modes:

- Recipes become too custom to maintain.
- Users cannot predict what a recipe will do.
- Failures in the middle leave partial state behind.

Risks:

- Orchestration logic can sprawl if recipes are fully programmable.

Potential mitigation:

- Limit recipes to a small set of composable primitives.
- Show a dry-run style preview before first use or when advanced steps are involved.
- Record recipe execution logs for troubleshooting.

### 7. Agent Team Board

Priority: `P1`

Spec:
Add a dedicated view for Claude agent teams showing lead, teammates, task list, dependencies, and communication activity.

Complete looks like:

- PipNav can detect and display local Claude team state and task status.
- Users can see teammate roles, current tasks, idle state, and completion progress.
- The board distinguishes active teams from orphaned or stale team artifacts.
- Users can jump from a project into its team board without leaving PipNav.

Failure modes:

- Team state lingers after crashes and looks active when it is not.
- Task noise overwhelms the screen instead of helping coordination.
- The feature is hard to trust because teams are experimental.

Risks:

- Claude team internals are experimental and may change.

Potential mitigation:

- Mark the feature as experimental in PipNav too.
- Show confidence or freshness on each state source.
- Start read-only before attempting any team-control actions.

### 8. Inventory Portfolio Board

Priority: `P1`

Spec:
Upgrade the inventory tab from a static table into a portfolio view for all repos, with sort/filter/focus modes around what actually needs attention.

Complete looks like:

- Users can filter by dirty, stale, active Claude session, remote enabled, open worktree, recent commits, or custom tags.
- The view supports attention slices like "needs review", "recently active", and "abandoned".
- The table can sort by urgency, not just raw project attributes.
- The screen acts as a triage cockpit rather than a passive list.

Failure modes:

- Too many columns make the screen unreadable.
- A clever urgency score feels arbitrary and opaque.
- The board duplicates the session center without a clear difference.

Risks:

- Information architecture becomes muddled between overview screens.

Potential mitigation:

- Keep this view repo-centric and keep the session center session-centric.
- Make scoring transparent and user-tunable.
- Use saved filters instead of showing all dimensions at once.

### 9. Hook Profiles / Guardrails

Priority: `P1`

Spec:
Let users define and switch Claude hook policies from PipNav for safety, consistency, and workflow enforcement.

Complete looks like:

- Hook profiles can be attached to a project or profile.
- Users can choose templates like "tests before stop", "log all Bash", "format after edits", or "review before finish".
- PipNav surfaces which projects have strict, relaxed, or no guardrails.
- PipNav explains what each profile does in plain language.

Failure modes:

- Hook failures feel mysterious and users blame PipNav.
- Poorly designed hooks trap Claude in loops or block useful work.
- Hook scope is unclear across user, project, and local settings.

Risks:

- Hook behavior is powerful and easy to misuse.

Potential mitigation:

- Start with audited templates instead of arbitrary hook editing.
- Add guardrail diagnostics and last hook result visibility.
- Support a safe temporary bypass flow for debugging.

### 10. Loop + Automation Panel

Priority: `P1`

Spec:
Expose Claude scheduled tasks and PipNav-managed automation in a visible panel so polling jobs, reminders, and recurring checks are not hidden inside a terminal session.

Complete looks like:

- PipNav can show active `/loop` tasks for open Claude sessions when detectable.
- The UI makes a clear distinction between session-scoped Claude tasks and durable PipNav or CI automation.
- Users can start, inspect, and cancel common monitoring loops from PipNav.
- Expiry, jitter, and session-scoped limitations are explained clearly.

Failure modes:

- Users assume loops are durable when they are actually session-scoped.
- A cancelled or expired loop still appears live in PipNav.
- Too many automations create noise and alert fatigue.

Risks:

- Claude scheduling semantics are not the same as local cron or GitHub Actions.

Potential mitigation:

- Label each automation by durability and execution environment.
- Keep session-scoped jobs visually separate from durable jobs.
- Include last-fire time and expiry in the UI.

### 11. Headless / Stream JSON Console

Priority: `P1`

Spec:
Add a structured Claude runner and event viewer using `claude -p` with JSON or stream JSON output for scripted workflows, summaries, checks, and background analysis.

Complete looks like:

- PipNav can launch predefined headless tasks and render structured results in a dedicated panel.
- Streaming tasks can show progress events and partial output without dumping raw terminal noise.
- Structured outputs can be saved into project memory, summaries, or reports.
- The feature works for read-heavy automation first, before write-heavy flows.

Failure modes:

- Users mistake headless execution for the same behavior as interactive Claude.
- JSON schema mismatches or event parsing errors create silent failures.
- Streaming output floods the UI.

Risks:

- Event contracts may change across Claude versions.

Potential mitigation:

- Keep parser layers version-aware and resilient to unknown fields.
- Prefer explicit task templates rather than arbitrary user-entered JSON runs.
- Use ring buffers and summarized event views instead of raw full logs.

### 12. Subagent Pack Launcher

Priority: `P1`

Spec:
Make subagent usage more intentional by offering named role packs and per-project defaults such as researcher, reviewer, implementer, or QA specialist.

Complete looks like:

- PipNav can show available subagents for a project or profile.
- Users can launch Claude with a selected default agent or pass a subagent-oriented recipe.
- Tool restrictions, MCP scope, and intended use are visible before launch.
- PipNav can recommend a subagent based on the selected workflow recipe.

Failure modes:

- Too many role options confuse more than they help.
- Subagents are chosen for tasks where the main conversation would work better.
- Role definitions drift from reality and become untrustworthy.

Risks:

- This can become an abstraction layer over Claude that is more complex than necessary.

Potential mitigation:

- Start with a small, opinionated built-in set.
- Add "best for" and "not for" guidance to each role.
- Use launch recipes to hide complexity for common cases.

### 13. Channels Hub

Priority: `P2`

Spec:
Create a panel for installing, configuring, and monitoring Claude channels so external systems can push events into running sessions.

Complete looks like:

- Users can see which channels are available, approved, connected, and active.
- The hub can show inbound event history and whether Claude replied through the channel.
- Permission relay prompts and sender identity are surfaced clearly.
- Channel setup is gated by compatibility checks and feature flags.

Failure modes:

- Users treat channels as durable background automation when the target session is not open.
- Misconfigured sender checks create prompt-injection exposure.
- Channel registration fails due to preview gating or auth mode and feels broken.

Risks:

- Channels are preview-stage and especially sensitive from a security standpoint.

Potential mitigation:

- Treat channels as an advanced feature behind explicit enablement.
- Require sender allowlists and show trust warnings aggressively.
- Keep the first version read-only and diagnostic-heavy.

### 14. GitHub Actions Bridge

Priority: `P2`

Spec:
Help users scaffold, inspect, and monitor Claude Code GitHub Actions workflows for PR review, issue work, and scheduled summaries.

Complete looks like:

- PipNav can generate or validate baseline Claude Code workflow templates.
- The UI can show whether a repo has Claude Action support configured.
- Users can see high-level status such as installed, missing secrets, or workflow present.
- PipNav can link local project state to relevant CI automation paths.

Failure modes:

- Generated workflows are too generic and not trusted.
- Users assume local PipNav state and remote GitHub state are always synchronized.
- Secrets or repo permissions are configured incorrectly and the feature feels flaky.

Risks:

- Git hosting configuration is outside PipNav's direct control.

Potential mitigation:

- Keep templates small and inspectable.
- Focus on setup assistance and status surfacing first, not deep workflow management.
- Provide validation checks instead of magic one-click setup only.

### 15. Threat Meter / Trust Panel

Priority: `P2`

Spec:
Add a trust-oriented panel that makes external automation, channels, hooks, and remote surfaces legible from a security and correctness standpoint.

Complete looks like:

- Users can see which projects have hooks, channels, remote control, or dangerous launch modes enabled.
- The panel calls out risky states like no sender allowlist, bypass permissions, or unbounded automation.
- PipNav can attach trust badges and warnings to operational screens.
- Users can audit recent high-risk events at a glance.

Failure modes:

- Warnings become noisy and ignored.
- Scoring feels arbitrary or fear-driven.
- The feature duplicates information instead of clarifying it.

Risks:

- Security UX can become performative rather than practical.

Potential mitigation:

- Focus on a few actionable states only.
- Tie warnings to concrete remediation steps.
- Show severity and confidence, not just generic danger language.

### 16. Patrol Routes

Priority: `P2`

Spec:
Add durable recurring automation for repo health checks and recurring reviews, distinct from Claude's short-lived session loops.

Complete looks like:

- Users can define named patrols like `nightly repo check`, `weekly stale branch review`, or `morning summary`.
- Patrols specify scope, cadence, output target, and failure reporting behavior.
- Patrol results are visible in PipNav without requiring raw log reading.
- Patrols can call into Claude headless tasks or lightweight local checks.

Failure modes:

- Patrols become slow, expensive, and rarely reviewed.
- Users create too many recurring tasks and stop trusting the signal.
- Local durable automation conflicts with GitHub-native automation.

Risks:

- Durable scheduling increases product surface area significantly.

Potential mitigation:

- Start with a small set of templates and strong defaults.
- Track cost and runtime per patrol.
- Make output concise and triage-oriented, not essay-oriented.

### 17. Radio Feed

Priority: `P3`

Spec:
Create a compact live event feed with short status lines from Claude sessions, automations, hooks, and patrols.

Complete looks like:

- The feed feels useful even with minimal screen space.
- Events are categorized and filterable.
- It helps users notice active work without replacing deeper views.

Failure modes:

- Turns into noisy log spam.
- Feels decorative instead of useful.

Risks:

- Needs solid event plumbing first.

Potential mitigation:

- Use summarized events, not raw output.
- Add mute and focus filters from day one.

### 18. Wasteland Map

Priority: `P3`

Spec:
Represent projects visually as zones or sectors based on health, activity, and type.

Complete looks like:

- Users can spot clusters like abandoned, active, blocked, or risky projects quickly.
- The map remains navigable and not merely ornamental.
- It reinforces the Pip-Boy identity strongly.

Failure modes:

- Looks great but provides no better decisions than a sortable table.
- Breaks down for users with many repos.

Risks:

- Visual complexity can outrun practical value.

Potential mitigation:

- Keep it optional and overview-only.
- Use it as a secondary lens, not the primary workflow.

### 19. Holotape Replay

Priority: `P3`

Spec:
Provide a time-based replay of Claude sessions, important prompts, worktree changes, and automation events.

Complete looks like:

- Users can scrub through a meaningful timeline for a project or session.
- Key events are highlighted rather than every single low-level action.
- Replay helps with handoff, debugging, and postmortem review.

Failure modes:

- Transcript parsing becomes brittle.
- The replay is too dense to understand.

Risks:

- Depends on reliable event collection and storage.

Potential mitigation:

- Start with milestone events only.
- Make timeline summaries the default and raw detail opt-in.

### 20. Worktree Bunker Mode

Priority: `P3`

Spec:
Turn worktree creation and isolated branches into a themed, visible PipNav workflow rather than a hidden advanced option.

Complete looks like:

- Users can create, inspect, switch, and retire worktrees from PipNav.
- The UI clearly shows which sessions and branches belong to which worktree.
- The theme adds flavor without obscuring the operational value.

Failure modes:

- The theming becomes cute but does not improve understanding.
- Users accidentally lose track of which worktree is canonical.

Risks:

- Worktree UX is already subtle even without heavy theming.

Potential mitigation:

- Keep the mental model simple: one card per worktree, one branch, one status, one session set.
- Treat the thematic layer as polish on top of a clear operational model.

## Cross-Cutting Risks

- Claude feature drift: CLI flags, transcript formats, and preview features may change over time.
- State ambiguity: PipNav will often infer state from files and processes rather than receiving guaranteed APIs.
- UI overload: too many modes, panels, and badges could make the app impressive but harder to use.
- Security confusion: channels, hooks, remote control, and dangerous permission modes need clear boundaries.

## Cross-Cutting Mitigations

- Add capability detection everywhere and hide or soften unsupported features.
- Prefer read-only observability first, then add control surfaces later.
- Build a durable metadata/index layer before adding multiple live dashboards.
- Keep advanced Claude features behind explicit toggles and strong explanations.
- Preserve a fast core loop: select project, see status, resume work, launch worktree, move on.

## Definition Of Success

PipNav is "complete enough" in this direction when:

- It is the fastest way to understand what Claude is doing across all local projects.
- It is the safest and clearest place to launch or resume a development workflow.
- It helps users decide what to do next, not just where code lives.
- Its visual personality supports the workflow instead of distracting from it.
