# Implementation Plan: A Picker for Ambiguous `/link`

**Branch**: `015-link-picker` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/015-link-picker/spec.md`

## Summary

When `/link <terms>` matches more than one record, raise a selection list in the status-bar region
instead of naming the candidates and giving up. The list is a `ListView` in the screen's `#bottom-bar`,
hidden until a choice is pending — the same shape as the preview's Links section, which already does
`↑`/`↓` to move, `enter` to open, `esc` to close, with its own footer string.

The ordering and the data each row needs are core's job: a new `link_candidates()` returns every match
as a `LinkCandidate` (target, collection, date), newest first with ties by title. `find_link_targets()`
becomes a thin projection of it, so there is one scan and the single-match fast path is untouched.
Both editor hosts (inline in the preview pane, full-screen) compose the picker into their bottom bar
and `EditorPane` reaches it exactly the way it already reaches the status bar —
`self.screen.query_one(...)` — so 014's parity rule holds by construction rather than by vigilance.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Textual (TUI), already in use. No new dependency.

**Storage**: Markdown files in the workspace. Nothing new is persisted; the pending choice lives only
in the widget.

**Testing**: pytest, with Textual's `run_test` pilot for the TUI layers. Layers: `unit/` for core
ordering and row rendering, `integration/` for the end-to-end editor flows.

**Target Platform**: Windows, macOS, Linux terminals.

**Project Type**: Single project — `choom.core` plus two adapters (`choom.cli`, `choom.tui`).

**Performance Goals**: The list appears with no perceptible pause in a workspace of ~1000 records
(SC-006). The search it displays is the scan `/link` already runs today; this feature adds a sort over
the matches, not a second scan.

**Constraints**: Terminal-only rendering, no network, no new files on disk. The picker occupies a
bounded slice of the bottom bar and falls back to the existing message when the terminal is too short.

**Scale/Scope**: One new core function and dataclass, one new TUI widget, one new footer string, one
new row renderer, and the `_insert_link` branch that opens the picker. Roughly five source files
touched.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `choom.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. **List the `core` functions this feature's reads and writes go through**, and justify any assembly done in an adapter that an existing `core` function already performs. | **PASS** — reads go through the new `core.links.link_candidates()` (the scan, the match rule, and the newest-first ordering); inserts go through the existing `core.links.resolve_id()`, `core.links.format_link()`, and `core.links.relative_destination()`. `find_link_targets()` is re-expressed as a projection of `link_candidates()`, so the two can never disagree about what matches. The adapter does only what a terminal forces: width-aware row text (`tui/rendering.py`, precedent `render_link_row` and `in_flight_status`) and key handling. No ordering, no matching, and no date normalisation happens in a widget. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS** — inherently interactive. A picker is a prompt, and Principle II forbids the CLI to block on one; the CLI's equivalent is naming the id explicitly, which is never ambiguous. No CLI command, `--json` schema, or exit code changes. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. No new configuration knob that could be a default. Date stays the only axis the directory tree encodes; `type` never becomes a directory. | **PASS** — the candidate list is built per invocation and discarded on dismissal. Nothing is written, cached, or configured; the visible row count and the fallback threshold are constants, not settings. |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. No user file is moved to match its partition, and no tag can be silently dropped. | **PASS** — cancelling leaves the typed line byte-identical (FR-008); inserting reuses the replacement the single-match path already performs. A record that stops resolving between listing and `enter` is reported, never written as a broken link (FR-015). Truncation is display-only and never reaches the buffer. |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; `ctrl+c` is never bound to anything, `ctrl+q` quits immediately unless something is dirty (in which case it MAY raise the existing confirmation); no non-`ctrl` modifier. | **PASS** — the picker is a widget in the bottom bar, not a fourth state: no screen is pushed and no pane is displaced. A new `LINK_PICKER_HELP` states every key while it is open, swapped in exactly as `LINKS_SECTION_HELP` already is. No confirmation is added — cancelling loses nothing. `ctrl+c` gains no binding, and `ctrl+q` keeps quitting immediately: the gate that suspends the pane's own actions while a choice is pending covers `save`, `save_and_close`, `close`, and `cancel_request` only, never the app-level quit. |
| VI | Type hints and docstrings on new public `core` functions; test coverage is risk-based (chosen for what could break, not one test per acceptance scenario) and placed in the right layer; no test depends on the wall clock. | **PASS** — `link_candidates()` and `LinkCandidate` are typed and documented. Coverage targets what can actually break: the ordering rule (unit), row truncation (unit), the picker flow and both fast paths (integration), and host parity (integration, exercised against both hosts). Fixture dates are derived from `date.today()` with offsets, never written as literals. |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS** — no new files, no network, no state outside the widget. Inserted paths come from `relative_destination()`, which already carries the path-length budget. |

**Post-design re-check (after Phase 1)**: unchanged. The design added one core function, one dataclass,
one widget, one row renderer, and one footer string. No gate moved, and Complexity Tracking stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/015-link-picker/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── core-api.md      # link_candidates() and LinkCandidate
│   └── tui.md           # the picker's keys, rows, and states
├── checklists/
│   └── requirements.md  # written by /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/choom/
├── core/
│   ├── links.py          # + link_candidates(), ordering; find_link_targets() becomes
│   │                     #   a projection of it
│   ├── models.py         # + LinkCandidate dataclass
│   └── __init__.py       # + exports
└── tui/
    ├── link_picker.py    # NEW — the LinkPicker widget (ListView + wrapping cursor)
    ├── rendering.py      # + render_candidate_row(candidate, width)
    ├── status_bar.py     # + LINK_PICKER_HELP; link_ambiguous_status() kept for the
    │                     #   too-short-terminal fallback
    ├── edit_screen.py    # _insert_link opens the picker; EditScreen composes it;
    │                     #   check_action suspends pane actions while it is open
    ├── list_screen.py    # composes the picker into its #bottom-bar
    └── app.tcss          # #link-picker sizing, mirroring #links-section

tests/
├── unit/
│   ├── test_link_candidates.py   # NEW — ordering, dates, collections
│   └── test_rendering.py         # + row truncation
└── integration/
    └── test_links.py             # picker flow, both hosts, fast paths unchanged
```

**Structure Decision**: The existing single-project layout is unchanged. The one new module is
`tui/link_picker.py`, which follows `tui/links_pane.py` — the widget that already implements this
exact interaction for the preview's Links section.

## Complexity Tracking

> No Constitution Check gate failed. No entries.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
