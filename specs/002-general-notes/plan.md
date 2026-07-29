# Implementation Plan: General Notes

**Branch**: `002-general-notes` | **Date**: 2026-07-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-general-notes/spec.md`

## Summary

Add daily notes and typed notes as a second document kind, on the machinery feature 001 already
shipped.

The work is mostly a generalisation, not an addition. `create_meeting` and `scan_meetings` differ
between the two kinds in exactly four values — a directory to write to, a set of directories to
scan, an id prefix, and a set of reserved types — so they collapse into
`create_document`/`scan_documents` parameterised by a frozen `Collection` descriptor, with
`meetings.py` and `notes.py` as thin bound modules ([research.md R1](./research.md#r1-how-notes-share-code-with-meetings)).
`Document` becomes the canonical record; `Meeting` and `Note` are aliases, so feature 001's tests and
both adapters compile untouched ([R2](./research.md#r2-naming-and-backward-compatibility-of-the-core-api)).

The genuinely new behaviour is the daily note, and its whole difficulty is idempotence. `/note` must
create today's file or open it, never both, never a second one, and never modify an existing one.
That is one `os.open(..., O_EXCL)` whose `FileExistsError` branch is the success path
([R3](./research.md#r3-making-the-daily-note-idempotent-without-a-read-modify-write)) — a code path
that never opens an existing file for writing is the strongest available form of "did not touch it".
The one subtlety is a daily note whose frontmatter a user broke by hand: it is still that day's note
and must open, but it is not a listable record, so `open_daily_note` returns
`DailyNote(path, document | None, created)` rather than inventing metadata
([R4](./research.md#r4-what-open_daily_note-returns-when-the-existing-file-is-unparseable)).

Nothing new is stored, no dependency is added, and the TUI stays one screen — `/notes` and
`/meetings` switch which collection the existing list is showing.

## Technical Context

**Language/Version**: Python 3.11+ (`requires-python = ">=3.11"`), unchanged.

**Primary Dependencies**: None added. `textual>=8.2` and `PyYAML>=6.0` as shipped in 001.

**Storage**: Markdown files on disk. No database, no index, no cache (Principle III).

**Testing**: `pytest` + `pytest-asyncio`; TUI driven headless through `App.run_test()` / `Pilot`.

**Target Platform**: Windows, macOS, Linux. Windows is first-class.

**Project Type**: Single project — installable CLI + TUI application, `src/` layout.

**Performance Goals**: Open a 1,000-note workspace in <2s and filter in <100ms (SC-005). Both
collections are scanned at TUI mount; the doubled walk stays inside the existing budget
([R6](./research.md#r6-holding-two-collections-in-a-one-screen-tui)).

**Constraints**: No network. No external binaries. Note paths are strictly shorter than the meeting
paths already budgeted for Windows ([R9](./research.md#r9-windows-path-budget-for-notes)).
`AGENTS.md` must still fit ~60 lines while documenting twice the commands
([R7](./research.md#r7-keeping-agentsmd-under-60-lines-while-documenting-twice-the-commands)).

**Scale/Scope**: Hundreds to low thousands of files per workspace; at most one daily note per day.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Mark each gate PASS / FAIL / N/A with a one-line justification. Any FAIL must appear in
Complexity Tracking below with a rejected simpler alternative, or the plan does not proceed.

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `endpaper.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. | **PASS** — `documents.py` and `notes.py` join `core`; the adapters gain no logic beyond argument wiring and widget state. The existing import-walk test covers the new modules automatically. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS** — every note behaviour has both front doors: `/note`↔`note today`, `/note.<type>`↔`note new`, `/notes`↔`note list`. `create_document` and `open_daily_note` are the only write paths, called identically by both. No new JSON key, no new exit code. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. No new configuration knob that could be a default. | **PASS** — files remain the only state; no dependency added; no setting introduced. The `Collection` descriptor *removes* the duplication a second scanner would have created ([R1](./research.md#r1-how-notes-share-code-with-meetings)). |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. | **PASS** — the strongest case in this feature: an existing daily note is never opened for writing at all ([R3](./research.md#r3-making-the-daily-note-idempotent-without-a-read-modify-write)), and an unparseable one is opened but neither repaired nor rewritten ([R4](./research.md#r4-what-open_daily_note-returns-when-the-existing-file-is-unparseable)). Verified on bytes *and* mtime ([R10](./research.md#r10-test-strategy-for-the-file-did-not-change)). |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; bindings avoid `ctrl+c`, `ctrl+q`, and rely on no non-`ctrl` modifier. | **PASS** — no new screen and no new key binding; `note`/`notes` are verbs in the existing command bar. `tab` is deliberately left unbound for §3.4's scope toggle ([R6](./research.md#r6-holding-two-collections-in-a-one-screen-tui)). Nothing destructive, so no confirmation is added. |
| VI | Type hints and docstrings on new public `core` functions; every acceptance criterion maps to a test; public API changes recorded in the changelog. | **PASS** — [contracts/core-api.md](./contracts/core-api.md) is the signature source of truth; `mypy src` covers the new modules; the additive core rename and the three new CLI commands are recorded in CHANGELOG under v0.0.2. |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS** — no install or network change. Note paths are shorter than the meeting paths already asserted by `test_path_budget.py`, which is extended to cover them ([R9](./research.md#r9-windows-path-budget-for-notes)). No per-user state introduced. |

**Post-Phase-1 re-check**: still PASS on all seven. Phase 1 introduced no dependency, no persistent
state, no screen, and no binding. The one design element that could have drawn a gate — the
`Collection` descriptor — was examined against Principle III and found to reduce duplication rather
than add indirection; it is recorded in Complexity Tracking for the record, not as a violation.

## Project Structure

### Documentation (this feature)

```text
specs/002-general-notes/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output — 10 decisions
├── data-model.md        # Phase 1 output — entities, validation, file formats
├── quickstart.md        # Phase 1 output — runnable validation guide
├── contracts/           # Phase 1 output
│   ├── cli.md           #   the three new commands, exit codes, JSON schema
│   ├── core-api.md      #   the generalised core API and what it replaces
│   └── tui.md           #   command-bar grammar, collection switching, footer
├── checklists/
│   └── requirements.md  # spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

Files marked **new** are added by this feature; **changed** are edited; everything else is untouched.

```text
src/endpaper/
├── core/
│   ├── __init__.py          # changed — export Document, Note, notes API, aliases
│   ├── models.py            # changed — Document (+ Meeting/Note aliases), DocumentFilter,
│   │                        #           DailyNote, Collection; Workspace gains notes_dir/daily_dir
│   ├── documents.py         # NEW     — create_document, scan_documents, filter_documents,
│   │                        #           match_document, _validate_token  (moved from meetings.py)
│   ├── meetings.py          # changed — shrinks to MEETINGS descriptor + bound wrappers
│   ├── notes.py             # NEW     — NOTES descriptor, create_note, scan_notes,
│   │                        #           open_daily_note
│   ├── text.py              # changed — new_document_id(when, prefix); new_meeting_id kept
│   ├── frontmatter.py       # changed — render_frontmatter takes Document (alias, so no-op)
│   └── templates/
│       └── AGENTS.md.tmpl   # changed — restructured to cover both kinds in <= 58 lines
├── cli/
│   ├── main.py              # changed — `note today|new|list` subparsers and handlers
│   └── output.py            # changed — printers renamed to documents; path-only printer
└── tui/
    ├── app.py               # changed — scan both collections, active collection, note actions
    ├── list_screen.py       # changed — collection-aware rows, empty state, status
    ├── command_bar.py       # changed — note/notes verbs, DailyRequested, collection switch
    ├── preview_screen.py    # changed — accept a path with no Document (unparseable daily note)
    ├── rendering.py         # changed — render from (path, Document | None)
    └── status_bar.py        # changed — active-collection indicator

tests/
├── unit/
│   ├── test_collection.py        # NEW — descriptor wiring, reserved types, id prefixes
│   ├── test_command_bar_resolve_mode.py  # changed — note/notes verbs, the /note grammar
│   └── test_path_budget.py       # changed — note and daily-note paths
├── integration/
│   ├── test_daily_note.py        # NEW — US1: idempotence, bytes+mtime, missing dir, malformed
│   ├── test_create_note_cli.py   # NEW — US2 via the CLI
│   ├── test_create_note_tui.py   # NEW — US2 via the command bar, incl. /note vs /note <desc>
│   ├── test_note_parity.py       # NEW — US2 scenario 2, both front doors diffed
│   ├── test_list_notes_cli.py    # NEW — US3 CLI: filters, --type daily, separation
│   ├── test_list_notes_tui.py    # NEW — US3 TUI: switching, filtering, preview
│   └── test_reserved_type.py     # NEW — FR-012 from both front doors
├── contract/
│   ├── test_agents_md.py         # changed — note commands present, line budget
│   └── test_json_schema.py       # changed — note list emits the same seven keys
└── performance/
    └── test_scan.py              # changed — 1,000-note workspace, both collections at mount
```

**Structure Decision**: Unchanged from feature 001 — single project, `src/` layout, `core/` importing
neither adapter. The one structural addition is the split of `meetings.py` into a generic
`documents.py` plus two thin binding modules, which keeps Principle I's "core is the product"
literally true for both kinds rather than making notes a second-class copy of meetings.

## Implementation Sequencing

Ordered so each stage is independently verifiable and each maps to a spec user story.

| Stage | Delivers | Verified by |
|---|---|---|
| 0. Generalise core | `Collection`, `documents.py`, aliases, `meetings.py` as wrappers | Feature 001's entire suite still passes, unchanged — this stage adds no behaviour |
| 1. Notes core | `notes.py`: `create_note`, `scan_notes`, reserved type | Unit tests: descriptor wiring, id prefix `n_`, reserved `daily` rejected before any write |
| 2. Daily note (US1) | `open_daily_note`, `DailyNote`, `Workspace.daily_dir` | US1 scenarios 1–6; bytes+mtime unchanged on re-open; missing `notes/daily/`; unparseable existing file |
| 3. Note CLI (US2, US3) | `note today`, `note new`, `note list` + filters | US2 scenarios 1–4, 6–7; US3 scenarios 4–7; parity test against the TUI path |
| 4. Note TUI (US1–US3) | verbs, collection switching, empty state, preview | US1 scenarios 1–2; US2 scenario 5; US3 scenarios 1–3, 8 |
| 5. AI contract (US4) | `AGENTS.md` restructure, stderr/stdout audit for the new commands | US4 scenarios 1–4; line-count budget |
| 6. Hardening | Path budget, 1,000-note performance fixture, cross-platform run | SC-005, SC-010, SC-011 |

Stage 2 is the MVP boundary: after it a user has a friction-free daily note, which is the highest-
value half of §3.2. Stages 3–4 make notes reachable from both front doors.

Stage 0 is worth calling out as a refactor with no user-visible effect. Its acceptance test is that
feature 001's suite passes without a single test edit; if a test needs changing, the "aliases only,
no signature changes" premise of [R2](./research.md#r2-naming-and-backward-compatibility-of-the-core-api)
has broken and the stage needs revisiting before notes are built on it.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No gate failed. One design element is recorded here because Principle III requires new structure to
justify itself in writing, and a reader who sees a descriptor object should find the reasoning
rather than infer it.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| `Collection` descriptor + generic `documents.py`, rather than a second concrete module | FR-011 requires notes to follow the meeting rules "with no note-specific variation". The rules that must not vary are the `O_EXCL` collision loop, the tolerant frontmatter walk, the warning taxonomy, the sort order, and token validation — ~130 lines that would otherwise exist twice. One descriptor of four fields names exactly what differs. | Copying `meetings.py` to `notes.py` was the obvious alternative and is what Principle III would actually punish: two scanners drift, and the first divergence is a silent behaviour difference between two kinds the spec says behave identically. A `kind` field with internal branching was also rejected — it scatters "which directory" across every function instead of stating it once. Full reasoning in [R1](./research.md#r1-how-notes-share-code-with-meetings). |

## Follow-ups outside this plan

- **`notes/daily/` was created but undocumented by 001's `AGENTS.md`**, which described it as
  "reserved for a future feature". That line becomes wrong the moment this feature ships; the
  restructure in [R7](./research.md#r7-keeping-agentsmd-under-60-lines-while-documenting-twice-the-commands)
  handles it, but workspaces initialised under 001 keep the stale file. `AGENTS.md` regeneration for
  existing workspaces is not in scope here and has no command yet — worth one when §3.4 adds
  workspace management.
- **`tasks.md` remains the last "reserved for a future feature" line** in the template after this
  feature. It goes away with §3.3.
- **REQUIREMENTS.md §3.2 does not define `/note <description>`.** The spec resolves it in Assumptions
  and [R5](./research.md#r5-disambiguating-note-note-description-and-notetype-description) implements
  that resolution; the source document is still silent and worth correcting.
