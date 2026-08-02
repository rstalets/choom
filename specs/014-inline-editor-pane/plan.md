# Implementation Plan: Editor Replaces the Preview Pane

**Branch**: `014-inline-editor-pane` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/014-inline-editor-pane/spec.md`

## Summary

Edit mode becomes a state of the list screen instead of a screen pushed over it. `EditScreen`'s entire
body — the text area, the save and discard paths, the mirror baseline, and the `/ai` request machinery —
moves into an `EditorPane` widget. `EditScreen` keeps its name and becomes a thin host that composes
that widget plus a status bar; `ListScreen` mounts the same widget inside `#preview-pane`, hiding the
preview and its links section for the duration.

One implementation in two places is what makes "identical capability inline and full-screen" (FR-019)
true by construction. Everything else in the plan follows from the list no longer being covered: the
list's periodic refresh must not disturb an open buffer (FR-021), `tab` must stop leaking past the
editor into the collection switcher (FR-007), and the two places that ask "is an editor dirty?" —
`ctrl+q` and task-state propagation — must find a pane rather than a screen (research R9).

No `core` change. No file format, CLI, or stored-state change.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Textual 8.2.8 (pinned). No new dependency.

**Storage**: Markdown files in the workspace — unchanged by this feature; the save path is the existing
`core.editing.save_buffer` / `core.tasks.set_task_body`.

**Testing**: pytest, with `App.run_test()` pilots for TUI behaviour. New coverage is integration-level,
in `tests/integration/`, plus one narrow-terminal case.

**Target Platform**: Windows, macOS, Linux terminals

**Project Type**: Single project — `src/choom/{core,cli,tui}` with `tests/{contract,integration,unit,performance}`

**Performance Goals**: No new budget. Mounting and unmounting one widget per edit is not a measurable
cost; the pause-and-refresh cycle around an edit does exactly the work the current suspend/resume cycle
does.

**Constraints**: The editor must wrap to the pane's edge with no horizontal scrolling at any supported
width (FR-004); no keystroke may reach the list while the editor is open (FR-007); a background refresh
may not touch the buffer (FR-021).

**Scale/Scope**: 3 source files carry the change (`edit_screen.py`, `list_screen.py`, `app.py`), plus
`app.tcss`. Roughly 15 existing test files reference `EditScreen`; most reach it through one helper
(research R10).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `choom.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. **List the `core` functions this feature's reads and writes go through**, and justify any assembly done in an adapter that an existing `core` function already performs. | **PASS** — no `core` file is touched, and none needs to be: this is where an existing widget renders, which is adapter-only by definition. Reads and writes continue to go through `core.editing.load_for_edit`, `core.editing.save_buffer`, `core.tasks.set_task_body`, `core.tasks.parse_tasks`, `core.mirrors.{reconcile_on_open, reconcile_on_save, find_mirrors, capture_task, capture_reply_tasks, write_document}`, `core.links.{find_link_targets, format_link}`, `core.documents._read_document`, `core.assistants.{resolve_assistant, compose_prompt, start_request}`, and `core.config.get_assistant`. The other half of the gate: `core.editing` and `core.tasks` were read for logic being written into the adapter instead — none is. The code being moved is already adapter code (widget state, focus, key handling) and stays adapter code; not one line of it becomes eligible for `core` by moving from a `Screen` to a `Widget`. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS** — editing is inherently interactive, and the CLI must never open an editor (Principle II, explicit). No CLI file, exit code, or `--json` schema is touched. FR-020 states this as a requirement so it is checkable rather than assumed. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. No new configuration knob that could be a default. Date stays the only axis the directory tree encodes; `type` never becomes a directory. | **PASS** — no new dependency, no new state beyond one nullable field on `ListScreen` holding the mounted pane, no configuration. Nothing about the directory tree is in scope. |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. No user file is moved to match its partition, and no tag can be silently dropped. | **PASS** — no parser or writer changes. The buffer→disk path is byte-for-byte the current one. The user's words are protected at two new points that this feature's own structure creates: a background refresh may not alter the buffer (FR-021), and `ctrl+q` must still find a dirty inline editor (research R9) or bug #64 reopens in a new shape. |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; `ctrl+c` is never bound to anything, `ctrl+q` quits immediately unless something is dirty (in which case it MAY raise the existing confirmation); no non-`ctrl` modifier. | **PASS**, and this feature is the gate's own subject: it removes the last state that left the one screen behind. Transitions stay one keystroke. The footer swaps whole (`EDIT_HELP` in, list help out — FR-009), never concatenating. Confirmations are unchanged and still fire only on unsaved work. `ctrl+q` keeps its amended behaviour, extended to reach inline editors. `ctrl+c` carries `006`'s pre-existing justified deviation, recorded in Complexity Tracking below; no new deviation is added. No non-`ctrl` modifier is introduced; `tab`/`shift+tab` gain a no-op, which declines to act rather than binding anything new. |
| VI | Type hints and docstrings on new public `core` functions; test coverage is risk-based (chosen for what could break, not one test per acceptance scenario) and placed in the right layer; no test depends on the wall clock. | **PASS** — no new `core` function; the new widget and helper carry hints and docstrings to the same standard. Coverage is risk-based and integration-level, chosen for the four things that can actually break: a key leaking to the list, `ctrl+x` losing to `TextArea`'s cut, a refresh touching the buffer, and the full-screen path regressing. No new test reads the clock. |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS** — no filesystem, path, or install surface is touched. The narrow-terminal case is covered because the pane is narrower than the screen the editor used to have, not because any platform rule changed. |

**Post-Phase 1 re-check**: unchanged. The design Phase 1 produced (one widget, two hosts, a frozen list)
added no `core` dependency, no new binding beyond the `tab` no-op, and no state beyond
`ListScreen._editor_pane`. Gate V reads better after the design than before it, since the design's whole
shape is "fewer screens".

## Project Structure

### Documentation (this feature)

```text
specs/014-inline-editor-pane/
├── plan.md              # This file
├── research.md          # Phase 0 output — R1..R11
├── data-model.md        # Phase 1 output — in-memory state, messages, widget tree
├── quickstart.md        # Phase 1 output — automated + manual validation
├── contracts/
│   └── tui.md           # Phase 1 output — inline edit mode's observable contract
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/choom/
├── core/                     # untouched by this feature
├── cli/                      # untouched by this feature
└── tui/
    ├── edit_screen.py        # EditorPane extracted; EditScreen becomes its host;
    │                         # open_editor/open_task_editor route by active screen;
    │                         # open_editors() helper for dirty checks
    ├── list_screen.py        # mounts/unmounts EditorPane in #preview-pane; freezes
    │                         # the list while it is open; restores status and focus
    ├── preview_screen.py     # unchanged — still pushes a full-screen EditScreen
    ├── app.py                # ctrl+q dirty check and task propagation skip now
    │                         # find panes, not screens
    └── app.tcss              # EditorPane sizing inside #preview-pane

tests/
├── integration/              # where this feature's new coverage lives
│   ├── test_inline_editor_tui.py       # new — mounting, keys, focus, close
│   ├── test_edit_from_list_tui.py      # updated — the list path is now inline
│   ├── test_create_opens_editor_tui.py # updated — inline, with the row selected
│   ├── test_daily_note_tui.py          # updated — same
│   ├── test_discard_tui.py             # updated — confirmation over the list
│   ├── test_ctrl_q_confirm.py          # updated — dirty inline editor
│   ├── test_narrow_terminal_tui.py     # updated — inline wrap at a narrow width
│   └── test_edit_presentation.py       # unchanged in substance — full-screen contract
├── unit/
│   └── test_footer_bindings.py         # updated — footer text while inline
└── helpers.py                          # open_edit asserts an editor is open, not a screen
```

**Structure Decision**: Single project, existing layout. The change is confined to `src/choom/tui/` and
its tests; `core/` and `cli/` are not touched, which is what Gate I's second half asks to be checked
rather than assumed.

## Implementation Sequence

The order matters — each step is observable before the next one depends on it.

1. **Extract `EditorPane`** from `EditScreen`, with `EditScreen` composing it. The suite should pass at
   this point with no behaviour change at all: full-screen editing still works, nothing is inline yet.
   This is the step that must land clean, because everything after it is small.
2. **Route by active screen** in `open_editor` / `open_task_editor`, and mount inline from `ListScreen`
   — hiding `#preview` and `#preview-links-section`, swapping the status bar, focusing the editor.
3. **Close the loop**: handle `EditorPane.Closed` in `ListScreen` — unmount, unhide, restore the status
   bar, refresh the list, refocus `#meeting-list`.
4. **Stop the leaks**: `tab`/`shift+tab` no-op on the pane, `check_action` gating on `ListScreen`,
   command bar unopenable.
5. **Freeze the list**: pause the refresh timer, guard `_refresh_tick`, `_update_preview`, and
   `on_screen_resume` (research R6).
6. **Fix the dirty checks** in `app.py` via `open_editors()` (research R9).
7. **Create paths select first** (research R8).
8. **Tests**: repair the existing ones, then add the new ones.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| `ctrl+c` bound to `cancel_request` on `EditorPane` (Principle V reserves `ctrl+c` absolutely) | Inherited verbatim from `006-ai-assistant-invocation`, where it was justified and accepted: the binding is live only while an assistant request is in flight, and the cancel hint is on screen for the whole wait via `in_flight_status()`. Moving the code from a screen to a widget carries the binding with it; this feature neither widens nor narrows it. | Dropping the binding as part of this move would remove a shipped capability under cover of a presentation change — a scope expansion in the guise of a cleanup. Re-litigating it belongs with the AI feature that owns it, not here. |
