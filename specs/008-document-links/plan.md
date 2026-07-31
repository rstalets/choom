# Implementation Plan: Document Links

**Branch**: `008-document-links` | **Date**: 2026-07-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-document-links/spec.md`

## Summary

Give any record in a workspace the ability to point at any other, as a reusable primitive rather than
a field on one record type. A link is an ordinary CommonMark inline link — `[text](path#id)` — whose
`#id` fragment is authoritative and permanent and whose path is derived, computed by endpaper from
two real file locations, and repaired whenever it goes stale. Inbound links are computed by scanning
at the moment they are asked for; nothing is indexed, cached, or written back into a target.

The technical approach, settled by measurement in [research.md](research.md):

- **A stdlib `re` scanner** for inline links, run over text with fenced code blocks and inline code
  spans masked out. It returns exact source offsets, so repair splices a new destination into the
  original string and changes nothing else. No new dependency — 15/15 probe cases pass (R1).
- **A candidate-filter scan** for inbound links: substring-test each file's bytes for the target id,
  then run the link scanner only on files that hit. Measured **155 ms** across 6,000 documents
  (50.3 MB) against a 500 ms budget, and 5.4× cheaper than merely parsing the corpus's frontmatter
  (R2).
- **Repair lands in `core.editing.save_buffer`**, which has exactly one production caller, so both
  adapters inherit save-time healing rather than re-implementing it (R5).
- **Full collection-name id prefixes** (`meeting_`, `note_`, `task_`) ship first, because every link
  carries an id and changing the scheme later is a migration. Four production literals; the reach is
  in tests and documentation (R6).

Work is ordered by the spec's story priorities: ids (P1) → the link primitive and save-time repair
(P2) → backlinks (P3) → `links check`/`heal` (P4) → the task `links:` field (P5) → `/link` (P6) →
the preview Links section (P7) → the README's cloud-storage warning (P8).

## Technical Context

**Language/Version**: Python 3.11+ (`requires-python = ">=3.11"`), `from __future__ import
annotations` throughout, `mypy --strict` over `src/`.

**Primary Dependencies**: `textual>=8.2`, `PyYAML>=6.0` — **unchanged**. This feature adds no runtime
dependency. `markdown-it-py` is available transitively via `textual` and was deliberately not used
(R1): `core` may not import `textual` (ruff banned-api), relying on a transitive dependency is
fragile, and its token stream does not expose the character offsets byte-preserving repair needs.

**Storage**: Markdown files only. No index, no cache, no database, no new file written anywhere in
the workspace. Links live in document bodies as markdown and in `tasks.md` as a `links:` field in the
existing metadata comment. No new frontmatter key (FR-021).

**Testing**: `pytest` with `pytest-asyncio` (auto mode) and `pytest-xdist`. Existing layers:
`tests/contract/` (the CLI's AI-facing surface), `tests/integration/` (one end-to-end path per story,
parametrized across adapters), `tests/unit/` (core logic worth isolating),
`tests/performance/` (only where a real budget exists — marked `@pytest.mark.performance`).
Baseline before this feature: **407 tests pass** in 74s.

**Target Platform**: Windows, macOS, Linux terminals. Windows is first-class.

**Project Type**: Single project — a `core` library with two peer adapters (`cli/`, `tui/`).

**Performance Goals**:

- Inbound links for one id: **< 500 ms** on a 6,000-document workspace (SC-006). Measured 155 ms.
- Save-time repair: no perceptible addition to a save. It scans one file already in memory, and
  resolves ids only when a link's path is actually stale.
- `links heal` over a whole workspace: bounded by the same read cost as the scan above.

**Constraints**:

- No network access; no admin rights; nothing outside the workspace directory.
- Link destinations use forward slashes on every platform — a Windows-authored link must resolve on
  macOS (R3).
- Byte preservation: repair alters link destinations and nothing else — not link text, not
  surrounding prose, not line endings (FR-026).
- `AGENTS.md.tmpl` must end at **≤ 60 lines**. It is already at 63, so this feature must tighten it
  while adding to it (R9).
- Ruff (`E,F,I,UP,B,TID`, line length 100) and `mypy --strict` gate every change.

**Scale/Scope**: Hundreds to low thousands of files in normal use; verified to 6,000. Eight user
stories; ~4 production literals for the id change plus one new core module, one new CLI subcommand
group, one editor command, and one preview-pane region.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Mark each gate PASS / FAIL / N/A with a one-line justification. Any FAIL must appear in
Complexity Tracking below with a rejected simpler alternative, or the plan does not proceed.

**Initial evaluation (pre-research)** and **post-design re-check** agree; the table below is the
re-checked version, with any change from the initial pass noted in the justification.

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `endpaper.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. | **PASS** — link scanning, resolution, path derivation, healing, and the inbound scan all land in a new `core/links.py`. `cli/main.py` only parses arguments and formats output; `tui/` only renders. Every new function is callable with a `Workspace` and a `Path`. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS** — save-time repair is in `save_buffer`, so both adapters get it from one place. Following links is `endpaper links <id>` and the preview Links section. `links check`/`heal` are batch audit operations over a whole workspace, which is inherently non-interactive; the TUI's equivalent is that its saves repair continuously, so a TUI user never accumulates the staleness the batch pass exists to clear. `--json` schema fixed in [contracts/cli.md](contracts/cli.md); no prompts, no pager, no colour. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. No new configuration knob that could be a default. | **PASS** — the central design commitment. Inbound links are computed per call and nothing persists (FR-027/FR-028). No new dependency: R1 chose ~40 lines of stdlib `re` over `markdown-it-py`, and R2 measured the scan at 155 ms to show there is nothing an index would buy. No new setting. |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. | **PASS** — a dead link is left byte-identical and produces a warning, never an exception (FR-025). Code-fence and code-span masking means a note *about* link syntax is never rewritten. The link scanner cannot raise on any input. Repair rewrites only the destination span. R7 notes this gate is strengthened, not just held: adding `links` to `_RECOGNIZED_KEYS` fixes a live case where a hand-written `links:` silently drops a task from every listing. |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; bindings avoid `ctrl+c`, `ctrl+q`, and rely on no non-`ctrl` modifier. | **PASS** — the Links section is a region inside the existing `PreviewScreen`, not a fourth state; list → preview → edit is unchanged. `l` toggles, `enter`/`o` opens, both shown in the footer (63 chars, fits 80 columns). No modifier keys, no confirmation — nothing is discarded. |
| VI | Type hints and docstrings on new public `core` functions; test coverage is risk-based (chosen for what could break, not one test per acceptance scenario) and placed in the right layer; public API changes recorded in the changelog. | **PASS** — `mypy --strict` already covers `src/`. Coverage is chosen per risk in [quickstart.md](quickstart.md): unit tests concentrate on the scanner's masking and path derivation (where subtle breakage hides), one integration path per story, contract tests for the JSON schema and exit codes, one performance test guarding SC-006. The id prefix change, the task line format change, the new commands, and the new JSON schema are all recorded in the changelog (FR-054). |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS, with one pre-existing condition this feature must repair.** No network, no admin, no new state. Forward-slash destinations verified across depths (R3); angle-bracket destinations handle spaces (R4); the worst-case 117-character destination is text in a file, not a filesystem path. **The condition**: `AGENTS.md.tmpl` is already 63 lines against a "roughly 60" limit, and FR-052 adds to it. R9 shows ≤ 60 is reachable only with deliberate tightening, so that tightening is a required task with an explicit line-count check — not a nice-to-have. Had the plan simply appended, this gate would fail. |

**Result: no FAIL. Complexity Tracking is empty and this plan proceeds.**

## Project Structure

### Documentation (this feature)

```text
specs/008-document-links/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── link-format.md   # The on-disk syntax: what is a link, how it resolves, how it is repaired
│   ├── core-api.md      # endpaper.core public surface added by this feature
│   ├── cli.md           # `endpaper links` argument shapes, JSON schema, exit codes
│   └── tui.md           # Preview Links section and the `/link` editor command
├── checklists/
│   └── requirements.md  # Spec quality checklist (/speckit-specify output)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/endpaper/
├── core/
│   ├── links.py            # NEW — the whole primitive: scan, resolve, derive path, heal, inbound
│   ├── models.py           # Link, LinkReport, LinkStatus, LinkDirection; Task gains `links`;
│   │                       #   SaveResult gains `warnings`; ScanWarningReason gains link reasons
│   ├── editing.py          # save_buffer gains `workspace=`; heals before stamping `updated`
│   ├── tasks.py            # `links` in _RECOGNIZED_KEYS, validated, parsed, rendered
│   ├── text.py             # id prefixes: new_meeting_id, new_task_id
│   ├── meetings.py         # Collection("meeting_", ...)
│   ├── notes.py            # Collection("note_", ...)
│   ├── documents.py        # resolve-by-path helper reuse; otherwise unchanged
│   ├── editor_commands.py  # `/link` registered in EDITOR_COMMANDS
│   ├── __init__.py         # re-export the new public surface
│   └── templates/
│       └── AGENTS.md.tmpl  # link syntax, links: field, endpaper links — and tightened to ≤60 lines
├── cli/
│   ├── main.py             # `links` subparser: <id> | check | heal
│   └── output.py           # print_links_json / _table, print_link_reports_json / _table
└── tui/
    ├── preview_screen.py   # Links section region, `l` toggle, enter/o open
    ├── edit_screen.py      # handle the `/link` EditorCommandSubmitted case
    ├── status_bar.py       # PREVIEW_HELP gains `l links`; a links-section help string
    └── rendering.py        # render the Links section

tests/
├── contract/               # links JSON schema, exit codes, stream separation, non-blocking
├── integration/            # one end-to-end path per user story, parametrized across adapters
├── unit/                   # scanner masking, path derivation, task links parse/render, id prefixes
└── performance/            # SC-006: inbound links under 500 ms at 6,000 documents
```

**Structure Decision**: The existing single-project layout is unchanged — one `core` library with
`cli/` and `tui/` as peer adapters over it. The feature adds exactly one new module,
`src/endpaper/core/links.py`, which holds the entire primitive: the inline-link scanner with its code
mask, id and path resolution, relative-path derivation, the heal transform, and the inbound
candidate-filter scan. Everything else in the tree is an edit to a file that already exists.

Putting all of it in one module is deliberate. The scanner, the resolver, and the healer are three
views of one grammar — splitting them across modules would mean the mask rules and the offset
arithmetic live apart from the code that splices new destinations in, which is where a byte-preserving
guarantee gets quietly broken. The module is expected to land around 300 lines, well inside what one
file should hold.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. No new dependency, no new source of truth, no new configuration, no new screen, and no
new state. The table is intentionally empty.

The one item that came close is recorded rather than hidden: the platform-constraints gate passes only
because this plan includes tightening `AGENTS.md.tmpl` back under 60 lines (R9). That is not a
justified violation — it is a required task, tracked with an explicit acceptance check in
[quickstart.md](quickstart.md).
