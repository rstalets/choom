# Implementation Plan: UI Layout Refresh

**Branch**: `005-ui-layout-refresh` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-ui-layout-refresh/spec.md`

## Summary

Move the collection menu from the left pane to a top bar walked with Tab, and spend the reclaimed
left pane on a month list (Notes, Meetings) or a To-Do/Done pair (Tasks). Fill the middle pane from
one month at a time so start-up cost stops growing with workspace age. Add two entry points into the
existing editor (`e` from the list; straight into the editor on create), make `filter` an explicit
command verb with a permanent `/` prefix, and add a `/help` pane and a version indicator.

The technical shape is: two new read functions in `core` (`list_months`, `scan_month`) plus one new
`TaskFilter` selector, and a rearranged `ListScreen` that holds a per-session month cache instead of
one eagerly-scanned list. No new dependency, no new file on disk, no new configuration.

The version indicator pulls one more piece of work in with it. `__version__` is a hardcoded literal
today and can drift from the version the built package actually carries, so displaying it would put
a number on screen that nothing guarantees is true. It is replaced with a value stamped in at build
time, reading `0.0.0` from a source checkout, and a `workflow_dispatch` dry-run workflow rehearses
the release pipeline — build, install, assert the stamp, publish the artifact to the workflow run
rather than to PyPI.

Two design decisions extend the spec and are called out for the author rather than absorbed
silently: an **Unfiled** left-pane entry so hand-placed documents outside the `YYYY/MM` layout do not
become invisible ([research R6](./research.md#r6-documents-outside-the-yyyymm-layout-an-unfiled-entry)),
and a new `endpaper task list --done` flag so the Done view is not TUI-only, which Principle II
forbids ([research R8](./research.md#r8-a-done-only-view-needs-a-core-selector-and-principle-ii-makes-it-a-cli-flag-too)).

A third addition was directed by the author after the initial plan: build-time version stamping and
the release dry-run workflow ([research R9](./research.md#r9-the-version-string-stamped-at-build-time-000-from-source)
and [R9a](./research.md#r9a-a-release-dry-run-workflow-dispatched-with-a-proposed-version),
contract in [contracts/versioning.md](./contracts/versioning.md)). It reaches outside
`src/endpaper/tui/` into packaging and CI, which no other part of this feature does — worth knowing
when reviewing the diff.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Textual >= 8.2 (TUI), PyYAML >= 6.0 (frontmatter). No runtime additions.
Build-time only: `hatch-vcs`, already required by `[build-system]`, gains its `version-file` build
hook.

**Storage**: Markdown files in the user's workspace. Documents live at
`<collection>/YYYY/MM/*.md`; daily notes at `notes/daily/YYYY/MM/*.md`; tasks in a single
`tasks.md`. Unchanged by this feature.

**Testing**: pytest with `pytest-asyncio` (`asyncio_mode = "auto"`); Textual's `App.run_test()`
pilot for TUI integration tests; `tests/{unit,integration,contract,performance}`. The version stamp
is additionally verified against a real built artifact by the release dry-run workflow, which a unit
test cannot do.

**Build & versioning**: `hatch-vcs` derives the version from VCS tags and writes
`src/endpaper/_version.py` at build time; `__init__.py` falls back to `0.0.0` when that file is
absent, which is the source-checkout case (FR-043). See
[contracts/versioning.md](./contracts/versioning.md).

**Target Platform**: Windows, macOS, Linux terminals — Windows Terminal, iTerm2, macOS Terminal,
PuTTY, and tmux (constitution, Development Workflow).

**Project Type**: Single Python package — a library core with two peer front-ends (CLI and TUI).

**Performance Goals**: Opening a collection reads only the displayed month's files, measured as the
set of paths opened rather than wall-clock (research R11). A cross-month filter reads each month at
most once per session and never blocks the event loop.

**Constraints**: No network. No admin rights. No new on-disk state. Paths stay well under the
Windows 260-character limit. Bindings use no modifier other than `ctrl`/`shift`, and `ctrl+c` /
`ctrl+q` stay reserved.

**Scale/Scope**: Hundreds to low thousands of documents per workspace; three collections; one
screen with three panes plus a top bar, a bottom bar, and a modal help pane.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Initial evaluation (pre-Phase 0): PASS** — recorded below.
**Post-design re-evaluation (post-Phase 1): PASS.** The three additions beyond the original spec all
*reduce* gate pressure rather than adding it: R6 preserves the Principle IV guarantee that a user's
hand-placed file stays visible; R8 exists specifically to satisfy Principle II; and R9/R9a remove a
duplicated version literal, which Principle VI treats as public surface. Two later amendments were
re-checked against the gates and change no verdict: the single `open_editor` route (R10) is what
makes FR-023's "behaves identically" structural rather than duplicated, and re-pointing
`refresh_document` at the month cache keeps the save path's data guarantees intact under Principle
IV.

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `endpaper.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. | **PASS** — the three new pieces of behaviour (`list_months`, `scan_month`, `TaskFilter.only_done`) are pure core functions over paths and dataclasses, callable with no terminal. The TUI holds only the *selection* (which month, which category), which is view state, not behaviour. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS, with one addition** — the Done view forced `endpaper task list --done` (R8); without it the TUI would have a non-interactive capability the CLI lacks. Layout, Tab navigation, the help pane, and live filtering are inherently interactive and correctly TUI-only. Month scoping is a browsing concern; the CLI's `--since` already narrows by date. The CLI still opens no editor — FR-026's editor is a TUI screen, not `$EDITOR`. No `--json` key, exit code, or existing flag changes. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. No new configuration knob that could be a default. | **PASS** — nothing new is written to the workspace and no new runtime dependency is added. The month cache is per-session memory that is discarded on exit; the app already holds every scanned document in memory today, and this makes that memory lazily rather than eagerly filled. Principle III targets on-disk indexes and their invalidation and corruption hazards, neither of which a process-lifetime dict has. `_version.py` is a generated build artifact inside the package, not workspace state, and it removes a duplicated value rather than adding one. `hatch-vcs` is already in `[build-system]`; only its build hook is newly enabled, and no binary is required at runtime. No new configuration: the startup collection, the default month, the default category, and the fallback version are fixed defaults, not settings. |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. | **PASS** — `scan_month` reuses `_parse_document` unchanged, so malformed frontmatter still yields a `ScanWarning` rather than an exception. This feature adds no writer; `e`-from-list and create-into-editor both reach the existing `EditScreen`/`core.editing` save path. R6's Unfiled entry exists specifically so month scoping cannot make a user's hand-placed file invisible. |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; bindings avoid `ctrl+c`, `ctrl+q`, and rely on no non-`ctrl` modifier. | **PASS** — still one list screen; list → preview → edit is intact, with `e`-from-list and create-into-editor adding two edges into `edit`, each one keystroke. New bindings are `tab` / `shift+tab` (shift is unavoidable for a reverse-direction key and is what the issue specifies) and `e`; all appear in the footer, and `check_action` removes Tab from the footer while it is disabled. The help pane makes bindings *more* discoverable. No new confirmation dialog. `ctrl+c` and `ctrl+q` untouched. |
| VI | Type hints and docstrings on new public `core` functions; every acceptance criterion maps to a test; public API changes recorded in the changelog. | **PASS** — `list_months` and `scan_month` ship with type hints and docstrings stating what they return and what they raise; `YearMonth` is a frozen slotted dataclass like its neighbours. Every FR maps to at least one test (see [quickstart.md](./quickstart.md)). Changelog entries required for `TaskFilter.only_done` and `task list --done` (public API), for the retired `a` binding and the changed startup collection (user-visible behaviour), and for the versioning change — `__version__` becoming build-stamped with a `0.0.0` source-checkout value is exactly the kind of public-surface change Principle VI says must be written down with its version. |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS** — no network or path-length change; month discovery uses `pathlib` globbing, which is separator-agnostic. `tests/integration/test_unicode_paths.py` continues to cover spaces and non-ASCII, and must be extended to the month-scoped read path. No per-user state is added. Installation is unchanged for users — `uv tool install` and `pipx` still work without admin rights, and version resolution is a plain import with no git or network at runtime. |

## Project Structure

### Documentation (this feature)

```text
specs/005-ui-layout-refresh/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── core-api.md      # New/changed endpaper.core signatures
│   ├── tui-keys.md      # Key bindings and pane/focus contract
│   ├── commands.md      # Command bar verbs, aliases, errors, help text
│   └── versioning.md    # Version resolution + release dry-run guarantees
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
pyproject.toml           # fallback-version 0.0.0; [tool.hatch.build.hooks.vcs] version-file
.gitignore               # + src/endpaper/_version.py
.github/workflows/
└── release-dry-run.yml  # NEW — workflow_dispatch, builds and uploads, never publishes

src/endpaper/
├── __init__.py          # __version__ from _version.py, falling back to "0.0.0"
├── _version.py          # generated at build time, never committed
├── core/
│   ├── documents.py     # + list_months(), scan_month(), _month_dirs(), _stray_paths()
│   ├── models.py        # + YearMonth; TaskFilter gains only_done
│   ├── tasks.py         # filter_tasks() honours only_done
│   ├── meetings.py      # + list_meeting_months(), scan_meeting_month() (thin wrappers)
│   ├── notes.py         # + list_note_months(), scan_note_month() (thin wrappers)
│   └── editing.py       # unchanged
├── cli/
│   └── main.py          # + `task list --done`
└── tui/
    ├── app.py           # month cache, collection/month/category selection, worker load
    ├── list_screen.py   # three panes re-pointed; tab/shift+tab; `e`; create → editor
    ├── collection_bar.py  # NEW — top bar (R1)
    ├── scope_pane.py      # NEW — left pane: months | To-Do/Done | Unfiled
    ├── command_bar.py   # `/` prefix widget; filter/f verb; unknown-verb error
    ├── help_screen.py   # NEW — ModalScreen help pane (R4)
    ├── status_bar.py    # version in the bottom-right; footer text per collection
    ├── edit_screen.py   # + open_editor() — the one route in; EditScreen class unchanged
    ├── preview_screen.py# action_edit routes through open_editor()
    └── app.tcss         # top bar, pane widths, help pane, prefix

tests/
├── unit/                # list_months, scan_month, only_done, command parsing
├── integration/         # Tab navigation, month panes, categories, e/create → editor,
│                        # /filter, /help, version indicator; plus the rewrites in R12
├── contract/            # unchanged except the new --done flag
├── performance/         # + month-scope read-count tests (R11)
└── fixtures/generate.py # + spread documents across months
```

**Structure Decision**: The existing single-package layout is kept — `core` holds behaviour, `cli`
and `tui` are peer adapters. Two new TUI modules (`collection_bar.py`, `scope_pane.py`) and one new
screen (`help_screen.py`) are added rather than growing `list_screen.py`, which is already the
largest TUI module at ~350 lines and gains the most behaviour in this feature.

The versioning and workflow changes sit outside the package entirely (`pyproject.toml`,
`.gitignore`, `.github/workflows/`) apart from the four-line fallback in `__init__.py`. They are
sequenced first in `tasks.md` because FR-042 cannot be honestly tested until the version being
displayed is the version the artifact carries.

## Phase Outputs

- **Phase 0** — [research.md](./research.md): 12 decisions, all NEEDS CLARIFICATION resolved.
- **Phase 1** — [data-model.md](./data-model.md), [contracts/](./contracts/),
  [quickstart.md](./quickstart.md).

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

No violations. All seven gates pass; the table is intentionally empty.

The one judgement call worth recording without being a violation: the per-session month cache
(research R7) was checked against Principle III and found outside its scope, because Principle III's
stated rationale is on-disk indexes — invalidation logic, staleness bugs, and corruption inside a
synced folder. A dict that lives and dies with the process has none of those failure modes, and the
current implementation already holds the same data in memory. Should a reviewer read Principle III
more broadly, the simpler alternative is to re-read each month on every visit; it was not chosen
because FR-035 forbids it.
