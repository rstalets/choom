# Implementation Plan: Vertical Layout for a Half-Width Window

**Branch**: `020-vertical-tui-mode` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/020-vertical-tui-mode/spec.md`

## Summary

Add a second arrangement of the list screen's existing regions, chosen by `/config view
vertical|horizontal` and remembered per user. In vertical, the body becomes two bands: an upper band
holding the scope pane and record list side by side, and a lower band holding the preview/edit region
full width beneath them. The collection bar, the status bar, and the bottom strip are untouched.

The feature is three pieces with hard lines between them:

1. **`choom.core` gains one small module**, `preferences.py`: the two legal values, the default, one
   overridable resolver for the per-user location, and a read/write pair. It knows nothing about
   panes. It is the *only* new state in the feature.
2. **`choom.tui` gains one pure module**, `layout.py`: the effective-orientation decision and the
   `MIN_VERTICAL_SCREEN_HEIGHT` threshold, with no widget imports — the arrangement `columns.py`
   already established for layout arithmetic (research R8).
3. **`ListScreen` composes a different body subtree per orientation** and rebuilds it in place with
   `await body.recompose()`.

Four findings from reading the code and the installed `textual==8.2.8` shaped the design, and are
recorded in [research.md](./research.md):

- **A static tree cannot serve both orientations** (R1). Vertical needs the scope pane and list
  *grouped* so the preview can span beneath both; grouping them in horizontal shifts the pane
  boundaries by ~8 columns at 80 wide, because `14 + (2/5)(W-14)` is not a fixed fraction of `W` and
  Textual CSS has no `calc()`. So the tree differs — and the payoff is that horizontal composes
  *exactly today's tree*, making FR-020's "no residual difference" true by construction rather than by
  matching numbers.
- **`recompose()` is awaitable and scoped** (R2, `textual/widget.py:1704`). Calling it on `#body`
  leaves the collection bar and the bottom strip — including the command bar still mid-dispatch —
  alone, and awaiting it gives a deterministic point at which to repopulate.
- **The threshold is derived, not picked** (R7). `MIN_VERTICAL_SCREEN_HEIGHT = 11` is
  `1 + 1 + 1 + 4 + 4`: collection bar, status bar, divider, and the two bands' stated minimums. At
  exactly 11, `1fr`/`1fr` yields 4 and 4 — precisely both minimums, so the constant and the split rule
  are the same rule rather than two numbers that must be kept in step.
- **The one data-loss risk is a resize during an inline edit** (R10). The command path cannot change
  orientation mid-edit — 014 FR-008 makes the command bar unopenable while the editor is open — but a
  *resize* crossing the threshold would recompose `#body` and destroy the editor and its unsaved
  buffer. FR-025's guard exists for that path specifically.

No new dependency. `tomllib` and `os.environ` are standard library; `platformdirs` is rejected in
research R4.

## Technical Context

**Language/Version**: Python 3.11+ (repo targets 3.11, CI runs 3.11 and 3.13)

**Primary Dependencies**: `textual==8.2.8` (unchanged). **No new dependency.** Reading TOML uses
stdlib `tomllib`, already used by `core/config.py` and `core/workspace.py`.

**Storage**: One new per-user file, `preferences.toml`, holding `[view] orientation`. Located at
`%LOCALAPPDATA%\choom\` on Windows and `$XDG_CONFIG_HOME/choom/` (default `~/.config/choom/`) on macOS
and Linux — **outside every workspace** (FR-007). Nothing is written inside a workspace by this
feature (FR-024). Rationale in research R4; the constitutional argument for not using
`.choom/config.toml` is in spec.md §"Decision: where the orientation is remembered".

**Testing**: `pytest` via `scripts/dev-tests.sh`. New coverage in `tests/unit/` (the preference
read/write, the geometry functions), `tests/integration/` (the switch and its state preservation, the
short-terminal boundary), and one extension to the autouse fixture in `tests/conftest.py`.

**Target Platform**: macOS, Linux, Windows. Verified before release on Windows Terminal, iTerm2, macOS
Terminal, PuTTY, and inside tmux (`docs/REQUIREMENTS.md` §4.3), at 120x40, 80x24, and a window short
enough to trigger the fallback.

**Project Type**: Single project — `src/choom/{core,cli,tui}` over `tests/{unit,contract,integration}`.

**Performance Goals**: One extra file read at startup (a few hundred bytes, no workspace scan). The
switch itself is one recompose plus the refresh that `on_screen_resume` already performs on every
return from a full-screen editor, so it is bounded by work the app already does routinely. No
per-frame or per-keystroke cost is added — the effective-orientation call is integer comparison. No
performance test is added; there is no budget here to protect.

**Constraints**: No admin rights, no network, no new third-party dependency. Per-user state must live
outside the workspace. `MIN_VERTICAL_SCREEN_HEIGHT = 11`. Vertical must be usable at 80x24.

**Scale/Scope**: Roughly 120 lines of new source across two new modules, plus the `ListScreen` compose
branch, the switch handler, the resize guard, and five added CSS rules. One new `core` module with
three public functions.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution v2.1.0. **Result: all gates PASS. Complexity Tracking is empty because
no gate failed** — not because the table was skipped.

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `choom.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. **List the `core` functions this feature's reads and writes go through**, and justify any assembly done in an adapter that an existing `core` function already performs. | **PASS.** Reads and writes go through exactly three new `core` functions, all in the new `src/choom/core/preferences.py`: `preferences_root() -> Path` (the single location resolver, research R5), `get_view_orientation() -> str` (the read; returns `"horizontal"` for every failure mode), and `set_view_orientation(value: str) -> None` (the write; raises `UsageError` on an illegal value, `WorkspaceError` on an I/O failure). The write goes through the existing `write_text_atomic` (`core/atomic_write.py:19`) rather than a fourth hand-rolled temp-file dance — that module exists precisely because this sequence was duplicated four times before. No adapter assembles anything a `core` function already does: the TUI calls `get_view_orientation`/`set_view_orientation` and never touches `tomllib`, a path, or an environment variable. **The two-way half**: the logic that is deliberately *not* in core is the band geometry, and that is not core logic being left in an adapter — `columns.py`'s docstring records the repo's settled position that layout arithmetic is interface code which earns testability by having no widget imports, and a function about band heights in `core` would make `core` know a terminal exists, inverting Principle I (research R8). Ruff's TID251 ban on `argparse`/`textual`/`rich` in core holds: `preferences.py` imports `os`, `tomllib`, `pathlib`, and two core siblings. Signature note: these functions take no `Workspace` — deliberately, per FR-008, since the preference is per user and not per workspace, and passing one would imply a scoping that does not exist. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS, as an explicit inherently-interactive carve-out**, argued in spec.md §"Interface parity" rather than asserted. The argument, in short: the setting's entire effect is how the interactive screen is drawn, so there is no CLI behaviour missing — only a value the CLI could mutate but never demonstrate. The contrast that makes this a carve-out rather than an omission is `config assistant`, which *does* have a CLI form because it installs a discovery file outside the interface, an effect a setup script has reason to cause; a pane arrangement has no such effect. Structurally: `argparse` is untouched, no subparser is added (`cli/main.py:195-204` unchanged), so no CLI dispatch path can reach this setting. No `--json` key changes, no exit code is added or altered (FR-030), nothing prompts or blocks, and nothing is written to any stream. Adding `choom config view` later would be purely additive if a reason ever appears. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. Any new setting has a sensible default. Date stays the only axis the directory tree encodes; `type` never becomes a directory. | **PASS.** No index, database, or cache: `preferences.toml` holds one display preference and no copy of any record, so it is not a second source of truth for anything in the vault — delete it and the only effect is that the default applies. No new third-party dependency (`platformdirs` rejected in research R4 for eight lines of stdlib). **Sensible default**: `horizontal`, per the repo owner's binding ruling recorded in the constitution's own 2.1.0 sync-impact report — a user who never types the command gets today's behaviour, with no first-launch question and nothing to configure (FR-002). This is the amendment that unblocked this feature, and it is worth stating plainly that **a second amendment is not sought and would be the wrong answer**: 2.1.0 removed Principle III's blanket ban on workspace configuration, and the remaining rule that governs storage location — the per-user-state rule under Platform & Distribution Constraints — is one this design *complies with* rather than one it needs relaxed. Directory layout untouched; no file is created, moved, or named by this feature inside any workspace. |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. No user file is moved to match its partition, and no tag can be silently dropped. | **PASS.** No document, task, or frontmatter parser is touched, and no user file is read, written, moved, or renamed (FR-024) — `created`/`updated` and CommonMark validity are out of range because no markdown is written at all. The gate still bites in two places and both are honoured. First, `preferences.toml` is a file a user can hand-edit: unreadable, malformed, missing key, wrong type, and illegal value all resolve to `horizontal` and choom opens normally (FR-011), following `get_assistant`'s documented precedent that "a hand-edited config must not stop choom from opening". Second, the write preserves comments, key order, and unknown keys via the same line-targeted edit `config.py:115-142` uses, and goes through `write_text_atomic` so a crash mid-write cannot leave a truncated file (FR-012). **The real data-loss risk in this feature is not a file**: it is a terminal resize crossing the threshold while an inline editor holds an unsaved buffer, which would recompose `#body` and destroy the editor. FR-025's guard in the resize path closes it, and it is covered by a dedicated integration test rather than left to inspection (research R10). |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; `ctrl+c` is never bound to anything, `ctrl+q` quits immediately unless something is dirty (in which case it MAY raise the existing confirmation); no non-`ctrl` modifier. | **PASS.** **No binding is added, removed, or changed** (FR-027), so the footer is unchanged in every state (FR-028) and there is no hidden key — the feature's whole surface is one argument to an existing command verb. Still one screen (FR-026): the switch is `await body.recompose()` on the mounted `ListScreen`, never a `push_screen`, and `list → preview → edit` remain the states in both orientations. `h`/`l` keep their meaning because the scope pane and record list stay left-and-right of each other in both arrangements — this is a property of the chosen layout, not a compatibility shim. `ctrl+c` and `ctrl+q` are untouched; no confirmation is added, which is correct because a layout switch discards nothing (a dialog here would be exactly the reflex-dismissal trap the principle warns about). State preservation across a switch is specified rather than improvised: collection, scope, filter and its matches, highlighted record, and backlinks-expanded all survive (FR-021), the preview shows the same record (FR-022), and focus lands on the record list by the *existing* `_on_command_bar_closed` rule rather than a new one (FR-023, research R3). Error messages name the rejected value and both accepted values (FR-044), and the unknown-setting message gains the list of settings that do exist (FR-045) — a Principle V gap in today's bare `unknown setting: 'x'` that having a second setting makes worth closing. |
| VI | Type hints and docstrings on new public `core` functions; test coverage is risk-based (chosen for what could break, not one test per acceptance scenario) and placed in the right layer; no test depends on the wall clock. | **PASS.** All three new `core` functions carry full type hints and docstrings stating what they return and what they raise. Coverage is chosen by failure mode, not generated from the spec's 30 acceptance scenarios: `unit/` for the preference read's five corruption modes and the write's preserve-other-content guarantee, and for `layout.py`'s threshold either side of 11; `integration/` for the switch and what survives it, the resize guard over a dirty editor, and the terminal-size boundary matrix in research R11. No `contract/` additions — the CLI surface is deliberately unchanged (gate II), and asserting the absence of a subparser is a test of argparse, not of choom. Nothing in the feature reads a clock, so no wall-clock dependency is possible. |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS, and this gate is the feature's central design question rather than a checklist line.** Per-user state is outside the workspace by explicit decision (FR-007), argued at length in spec.md §"Decision" against the rule by name: a view orientation is a property of one person's monitor, and a workspace can be a shared OneDrive folder, so storing it in `.choom/config.toml` would relayout a colleague's screen on sync and invite conflict copies of the one file that identifies a workspace. The issue's own wording ("via the config toml") is therefore not followed, deliberately. Windows uses `%LOCALAPPDATA%`, not `%APPDATA%` — roaming would carry an ultrawide preference onto the same user's laptop, a smaller replay of the same problem (research R4). Path length: `C:\Users\<user>\AppData\Local\choom\preferences.toml` is ~52 characters and is not built from the long OneDrive workspace root the 260-character constraint concerns. No admin rights (inside the user's own profile, no registry, no installer) and no network (one local file). Spaces and non-ASCII in the profile path go through `pathlib` and `write_text_atomic`, covered in `tests/integration/test_unicode_paths.py`. |

**Post-Phase-1 re-check**: re-evaluated after the Phase 1 artifacts below were written. No gate
changed status. The design added no module beyond the two named in gate I, no dependency, no binding,
no screen, and no CLI surface. The one thing Phase 1 sharpened was gate IV's real risk — the
resize-during-edit path — which is now an explicit contract clause and a named test rather than an
implicit consequence. Complexity Tracking remains empty.

## Project Structure

### Documentation (this feature)

```text
specs/020-vertical-tui-mode/
├── spec.md                    # Approved
├── plan.md                    # This file
├── research.md                # Phase 0
├── data-model.md              # Phase 1
├── quickstart.md              # Phase 1
├── contracts/
│   ├── core-api.md            # Phase 1 — preferences.py's contract
│   ├── layout.md              # Phase 1 — the geometry rules and the threshold
│   └── tui.md                 # Phase 1 — the command, the switch, what survives it
└── tasks.md                   # Phase 2 — NOT created by /speckit-plan
```

### Source Code (repository root)

```text
src/choom/
├── core/
│   ├── preferences.py         # NEW: preferences_root(), get_view_orientation(), set_view_orientation()
│   └── __init__.py            # MODIFIED: export the three in __all__
├── tui/
│   ├── layout.py              # NEW: ORIENTATIONS, MIN_VERTICAL_SCREEN_HEIGHT, effective_orientation()
│   ├── app.py                 # MODIFIED: read preference in __init__; /config view in handle_config_command
│   ├── app.tcss               # MODIFIED: + 5 rules, all vertical variants (research R9)
│   ├── list_screen.py         # MODIFIED: compose branch, async _on_config_requested, on_resize guard
│   └── commands.py            # MODIFIED: /config verb's argument text covers both settings
└── cli/                       # UNCHANGED — no CLI surface (gate II)

tests/
├── conftest.py                        # MODIFIED: autouse fixture also isolates preferences_root
├── unit/
│   ├── test_preferences.py            # NEW: read/write, corruption modes, preserve-other-content
│   └── test_layout.py                 # NEW: threshold either side of 11, derivation holds
└── integration/
    ├── test_vertical_layout_tui.py    # NEW: the switch, state preservation, resize guard, boundary sizes
    └── test_narrow_terminal_tui.py    # MODIFIED: width degradation identical in vertical (FR-039)
```

**Structure Decision**: The existing single-project layout is kept unchanged. Two new modules, each
placed by which side of the Principle I line it falls on: `core/preferences.py` because storing and
validating a setting is logic with no terminal in it, and `tui/layout.py` because band geometry is
interface arithmetic — the split `columns.py` already established and research R8 confirms.
`preferences.py` is a new module rather than an addition to `core/config.py` because that module is
specifically the *workspace's* config file, and putting a per-user setting inside it would blur the
exact distinction this feature exists to get right; a reader opening `config.py` should not find
something that never touches a workspace. `tui/layout.py` is new rather than an addition to
`columns.py` because that module is about the four labelled columns within one pane, not about panes.

The layout also keeps the rebase surface against `019-completed-tasks-partition` small (research R13):
the new geometry lives entirely in files that feature cannot touch, and `compose` is the one genuinely
shared hunk.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*Empty. Every gate above is PASS, so there is no violation to justify. No entry here is a placeholder
or an "N/A" — the table has no rows because the design introduces no new dependency, no new key
binding, no new screen, no new CLI surface, and no second source of truth. The one new piece of state
is a single per-user display preference, which the Platform & Distribution gate above addresses
directly rather than deferring to this table.*
