# Implementation Plan: Viewing and Editing

**Branch**: `004-viewing-editing` | **Date**: 2026-07-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-viewing-editing/spec.md`

## Summary

Complete the list → preview → edit state machine by adding the edit state, and fix `endpaper init` to
drop a `CLAUDE.md` pointing at `AGENTS.md`.

The whole feature turns on one requirement: **FR-016, a save writes the buffer exactly, changing only
`updated`.** That rules out the obvious implementation. `render_frontmatter()` rebuilds all six fields
in a fixed order with JSON quoting, so round-tripping a buffer through `Document` would reorder keys,
requote values, and silently discard anything the user hand-added — the opposite of "the buffer wins
on frontmatter". So the save path never parses the buffer. `core/editing.py` gets a **surgical text
stamp** that finds the `updated:` line inside the frontmatter block and rewrites that line alone,
leaving every other byte untouched, and reports whether it could.

Everything else falls out of that. Line endings and the trailing newline are captured at load and
restored at write, because the editing widget normalises to `\n`. Dirty state is `buffer !=
original_text`, not an edited flag, which makes "no prompt after a save" and "no prompt after you
undo your own typing" the same rule. The write is `tempfile` + `os.replace` in the same directory, so
a failure mid-write cannot truncate the file.

The interface work is small: a new `EditScreen` pushed over `PreviewScreen`, a `ModalScreen[bool]`
for the discard prompt, and one line added to `PreviewScreen` so it re-reads on resume. Textual's
`TextArea` needs exactly **one** non-default option — `show_line_numbers=True`. Soft wrapping and
non-inserting `tab` are already the defaults; `TextArea.code_editor()` is what breaks both, which is
precisely what REQUIREMENTS.md §4.5 warns about.

**No new dependency, no new state, no new configuration.** One breaking change to a public `core`
signature is recorded in Complexity Tracking.

## Technical Context

**Language/Version**: Python 3.11+ (unchanged)

**Primary Dependencies**: `textual>=8.2`, `PyYAML>=6.0` — **unchanged**. `TextArea`, `ModalScreen`,
and `Button` all ship with Textual; this feature adds nothing to `pyproject.toml`.

**Storage**: Markdown files on disk. No database, no index, no cache (Principle III).

**Testing**: `pytest` + `pytest-asyncio`; TUI driven headless through `App.run_test()` / `Pilot`,
the pattern already used by `tests/integration/test_list_tui.py`.

**Target Platform**: Windows, macOS, Linux. Windows is first-class — CRLF preservation and
`os.replace` behaviour on OneDrive-synced files are explicit design points, not afterthoughts.

**Project Type**: Single project — installable CLI + TUI application, `src/` layout.

**Performance Goals**: Save to disk and preview refresh <1s for any targeted document size (SC-002).
Opening the edit state on a 1 MB document must not block the event loop perceptibly.

**Constraints**: No network. No admin rights. A save may change only the `updated` line. A failed
write must leave the file byte-identical. `ctrl+c` and `ctrl+q` stay unbound by us; `ctrl` is the
only modifier.

**Scale/Scope**: One document open at a time. Documents are hundreds of lines typically, and must
stay editable at a few thousand.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Mark each gate PASS / FAIL / N/A with a one-line justification. Any FAIL must appear in
Complexity Tracking below with a rejected simpler alternative, or the plan does not proceed.

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `endpaper.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. | **PASS** — the new `core/editing.py` holds load, stamp, line-ending restoration, and atomic write; `EditScreen` only calls it and renders the outcome. The existing import-walk test (`tests/unit/test_core_imports.py`) covers the new module with no edit. Every FR-014 through FR-023 behaviour is testable without a terminal. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS** — interactive text entry is inherently interactive, the exemption the gate names, and the spec's FR-036/037 make that explicit. The one CLI-side change is `endpaper init`'s reporting, and `init` has been CLI-only since feature 001. No `--json` schema and no exit code changes; init still exits 0 (FR-051). |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. No new configuration knob that could be a default. | **PASS** — zero new dependencies; `TextArea` and `ModalScreen` are already-paid-for Textual widgets. `CLAUDE.md.tmpl` is packaged data, not state. No knob: the save keys, wrap behaviour, and gutter are fixed, not configurable. |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. | **PASS** — the load path never parses the buffer, so there is nothing to raise; `stamp_updated` returns `(text, False)` rather than throwing when it cannot find the block (FR-018). `tempfile` + `os.replace` makes truncation unreachable (FR-020). `created` is never on the write path at all — only the `updated:` line is rewritten. Guidance files use `O_EXCL`, so an existing `CLAUDE.md` cannot be opened for writing. |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; bindings avoid `ctrl+c`, `ctrl+q`, and rely on no non-`ctrl` modifier. | **PASS** — three states, one keystroke per transition (FR-001). `EDIT_HELP` joins `LIST_HELP`/`PREVIEW_HELP` in `status_bar.py`, so the footer is per-state by construction. The discard modal is gated on `buffer != original_text`, which is the "something to lose" test stated literally. `ctrl+o` canonical, `ctrl+s` alias, `ctrl+q`/`ctrl+c` untouched, no Cmd anywhere. |
| VI | Type hints and docstrings on new public `core` functions; every acceptance criterion maps to a test; public API changes recorded in the changelog. | **PASS** — `mypy --strict` already covers `src`. [contracts/core-api.md](./contracts/core-api.md) is the signature source of truth; [quickstart.md](./quickstart.md) maps all 20 acceptance scenarios to checks. The `init_workspace` return-type change is recorded in Complexity Tracking and goes in CHANGELOG as 0.0.3. |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS** — no network, no admin, no new paths generated so the path budget is unmoved. CRLF and trailing-newline preservation are designed in ([research.md R2](./research.md#r2-line-endings-and-the-trailing-newline)); `os.replace` failure on a locked OneDrive file is caught and reported rather than raised ([R7](./research.md#r7-atomic-write)). |

**Post-Phase-1 re-check**: still PASS on all seven. Phase 1 added no dependency, no persistent state,
and no binding beyond those the spec fixes. The one item that moved is `init_workspace`'s return
type, which was an open question at gate time and is now a recorded, justified decision with a
one-line migration.

## Project Structure

### Documentation (this feature)

```text
specs/004-viewing-editing/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output — 10 decisions
├── data-model.md        # Phase 1 output — entities, save pipeline, validation
├── quickstart.md        # Phase 1 output — runnable validation guide
├── contracts/           # Phase 1 output
│   ├── core-api.md      #   endpaper.core additions and the one breaking change
│   ├── tui.md           #   the three states, bindings, footer strings
│   └── cli.md           #   endpaper init's changed output (the only CLI surface touched)
├── checklists/
│   └── requirements.md  # spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

Only the marked files change. Everything else in the tree is untouched by this feature.

```text
src/endpaper/
├── core/
│   ├── editing.py           # NEW — load_for_edit, save_buffer, stamp_updated, line-ending policy
│   ├── models.py            # CHANGED — + EditableFile, SaveResult, InitResult
│   ├── workspace.py         # CHANGED — init_workspace writes CLAUDE.md, never clobbers, reports
│   ├── __init__.py          # CHANGED — re-export the new public names
│   └── templates/
│       ├── AGENTS.md.tmpl   # unchanged (58 lines, stays under 60)
│       └── CLAUDE.md.tmpl   # NEW — packaged pointer file, <= 12 lines
├── cli/
│   └── main.py              # CHANGED — init reports written/skipped guidance files on stderr
└── tui/
    ├── edit_screen.py       # NEW — EditScreen: TextArea, save/discard bindings
    ├── discard_dialog.py    # NEW — DiscardDialog(ModalScreen[bool])
    ├── preview_screen.py    # CHANGED — bind `e`, re-read on resume (FR-007)
    ├── status_bar.py        # CHANGED — + EDIT_HELP, PREVIEW_HELP gains the edit key
    └── app.tcss             # CHANGED — styles for the editor pane and the modal

tests/
├── unit/
│   ├── test_stamp_updated.py     # NEW — the surgical stamp, incl. every not-stampable shape
│   └── test_line_endings.py      # NEW — CRLF/LF and trailing-newline round-trips
├── integration/
│   ├── test_edit_save_tui.py     # NEW — US1
│   ├── test_discard_tui.py       # NEW — US2
│   ├── test_edit_presentation.py # NEW — US3: gutter, wrap, footer
│   ├── test_save_failure.py      # NEW — read-only file, FR-020, SC-011
│   ├── test_external_edits.py    # NEW — FR-041, SC-010
│   └── test_init_guidance.py     # NEW — US4: CLAUDE.md written, existing files preserved
└── contract/
    └── test_guidance_files.py    # NEW — CLAUDE.md is a pointer, not a copy (SC-013)
```

**Structure Decision**: Unchanged single project, `src/` layout. The new code respects the same
import direction the earlier features established — `core/editing.py` imports nothing from `tui/`,
and the two new screens import `core` but never each other's internals.

`core/templates/CLAUDE.md.tmpl` ships as package data through the existing
`[tool.hatch.build.targets.wheel.force-include]` entry, which already covers the whole `templates`
directory. **No `pyproject.toml` change is needed** — verified against the current force-include rule.

## Implementation Sequencing

Ordered so each stage is independently verifiable, matching the spec's user story priorities.

| Stage | Delivers | Verified by |
|---|---|---|
| 0. Core save path | `core/editing.py`: `load_for_edit`, `stamp_updated`, `save_buffer`; `EditableFile`, `SaveResult` | Unit tests only, no terminal: stamp table, CRLF/LF matrix, atomic-write failure injection |
| 1. Edit state (US1) | `EditScreen`, `e` binding on preview, `ctrl+o`/`ctrl+s`/`ctrl+x`, preview re-read on resume | US1 scenarios 1–7; headless `Pilot` |
| 2. Discard (US2) | `DiscardDialog`, dirty comparison, `esc` routing | US2 scenarios 1–6, incl. the undo-by-hand case |
| 3. Presentation (US3) | `show_line_numbers=True`, `EDIT_HELP`, footer per state | US3 scenarios 1–5; gutter starts at the opening `---` |
| 4. Guidance files (US4) | `CLAUDE.md.tmpl`, `InitResult`, `O_EXCL` writes, init reporting | US4 scenarios 1–5; SC-012, SC-013 |
| 5. Hardening | Read-only save, externally-modified documents, unicode, resize, large file | SC-003, SC-007, SC-009, SC-010, SC-011 |

**Stage 1 is the MVP boundary.** After it a user can fix a typo without leaving endpaper, which is
the premise of the whole feature. Stages 2 and 3 make it safe and legible; Stage 4 is independent of
all of them and can land in any order.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No gate failed. One item is recorded because Principle VI requires public API changes to be written
down, and this one breaks an existing signature.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| `init_workspace()` return type changes from `Workspace` to `InitResult` | FR-051 requires init to report which guidance files it wrote and which it left alone. That fact is known only inside `init_workspace`, at the moment the `O_EXCL` create either succeeds or raises `FileExistsError`. | Having the CLI stat `CLAUDE.md` and `AGENTS.md` before calling init was rejected twice over: it is a time-of-check/time-of-use race against the very create it is trying to describe, and it forces the CLI to hard-code knowledge of which files init writes, which is exactly the kind of behaviour Principle I keeps out of adapters. **Cost: 8 call sites across 6 files**, each a mechanical `.workspace` suffix — enumerated in [contracts/core-api.md](./contracts/core-api.md#changed-function--breaking). Recorded in CHANGELOG as 0.0.3. |

## Follow-ups outside this plan

- **`scan_documents` is not recursive.** `src/endpaper/core/documents.py:154` uses
  `directory.glob("*.md")`, and `create_document` writes straight into the collection root — so the
  `YYYY/MM/` partitioning REQUIREMENTS.md §4.6 mandates is not implemented anywhere yet. This feature
  neither needs nor blocks it: editing addresses a document by the path the scan already handed it.
  It remains real, unclaimed work.
- **`read_frontmatter` rejects unknown fields.** A user who hand-adds a seventh frontmatter key in
  the edit state gets a file that saves correctly (the buffer is written verbatim) but then drops out
  of the list as an `unexpected_fields` warning. That is existing, correct-per-spec behaviour and
  FR-050 requires it stay non-destructive, but it will read as surprising. Worth a spec question of
  its own rather than a silent change here.
- **REQUIREMENTS.md §4.3 specifies `AGENTS.md` only** and should be updated to mention `CLAUDE.md`,
  as already flagged in the spec's Source note.
