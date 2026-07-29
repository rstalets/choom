# Implementation Plan: Meeting Notes (with project scaffolding)

**Branch**: `001-meeting-notes` | **Date**: 2026-07-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-meeting-notes/spec.md`

## Summary

Stand up the endpaper project and deliver meeting capture and retrieval on top of it.

`endpaper.core` owns every behaviour: workspace discovery and creation, frontmatter reading and
writing, slugging, id generation, meeting creation, and the tolerant scan. A `argparse` CLI and a
Textual TUI are peer adapters over it — neither shells out to the other, and both call the same
`create_meeting`. Markdown preview uses Textual's built-in `Markdown` widget, which costs no
dependency beyond Textual itself.

Four architecture decisions were taken with the requirements owner and are recorded in
[research.md](./research.md): PyYAML for reading frontmatter paired with a deterministic
hand-written emitter for writing; `argparse` rather than Typer or Click; one `/` input bar that
resolves to filter or command by sniffing its first token; and 8-hex-digit random ids that need no
uniqueness lookup.

The result declares **two runtime dependencies**, stores nothing but markdown files, and installs
with `uv tool install endpaper` without admin rights.

## Technical Context

**Language/Version**: Python 3.11+ (`requires-python = ">=3.11"`)

**Primary Dependencies**: `textual>=8.2` (TUI + `Markdown` widget), `PyYAML>=6.0` (frontmatter
read). Textual transitively supplies `markdown-it-py`, `rich`, `platformdirs`, `pygments` —
verified against a clean install of Textual 8.2.8.

**Storage**: Markdown files on disk. No database, no index, no cache (Principle III).

**Testing**: `pytest` + `pytest-asyncio`; TUI driven headless through `App.run_test()` / `Pilot`.

**Target Platform**: Windows, macOS, Linux. Windows is first-class.

**Project Type**: Single project — installable CLI + TUI application, `src/` layout.

**Performance Goals**: Open a 1,000-meeting workspace in <2s (SC-004); filter keystroke to redraw
<100ms (SC-005).

**Constraints**: No network. No admin rights to install. No external binaries. Generated paths ≤120
chars below workspace root. Never opens an editor, prompts, or writes ANSI to a non-TTY.

**Scale/Scope**: Hundreds to low thousands of files per workspace; one user per workspace, many
workspaces per shared folder (later feature).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Mark each gate PASS / FAIL / N/A with a one-line justification. Any FAIL must appear in
Complexity Tracking below with a rejected simpler alternative, or the plan does not proceed.

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `endpaper.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. | **PASS** — `core` holds workspace, frontmatter, meetings, text helpers. A test walks `core`'s imports and fails if `argparse`, `textual`, `rich`, or `sys.stdout` appears. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS** — `create_meeting` is the single write path called by both front doors; US2 scenario 2 diffs their output. CLI uses no Rich at all, so no ANSI can leak; a test asserts zero `\x1b` bytes in redirected output. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. No new configuration knob that could be a default. | **PASS** — files are the only state; scan is in-memory and per-session. Two runtime dependencies, each justified in [research.md R8](./research.md#r8-packaging-layout-and-distribution). PyYAML is a deliberate deviation from the planner's recommendation; see Complexity Tracking. |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. | **PASS** — `scan_meetings` never raises and returns `ScanWarning` as data; a skipped file is never rewritten, and a quickstart check diffs it before and after. Creation uses `O_EXCL`, so an existing file cannot be opened for writing at all. |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; bindings avoid `ctrl+c`, `ctrl+q`, and rely on no non-`ctrl` modifier. | **PASS** — list ⇄ preview, one keystroke each; footer renders the active binding set per state; `ctrl+c`/`ctrl+q` unbound by us. No confirmations exist this feature because nothing is destructive. |
| VI | Type hints and docstrings on new public `core` functions; every acceptance criterion maps to a test; public API changes recorded in the changelog. | **PASS** — `mypy src` in CI; [contracts/core-api.md](./contracts/core-api.md) is the signature source of truth; CHANGELOG.md starts at this feature and records the CLI contract as v0.0.1. |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS** — `uv tool install` needs no admin; no network calls anywhere; path budget computed in [research.md R10](./research.md#r10-windows-path-length) and asserted by test. No per-user state exists yet (single workspace only). |

**Post-Phase-1 re-check**: still PASS on all seven. Phase 1 design introduced no new dependency, no
new persistent state, and no new binding. The one item that moved is PyYAML, which was an open
question at gate time and is now a recorded, justified decision.

## Project Structure

### Documentation (this feature)

```text
specs/001-meeting-notes/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output — 10 decisions
├── data-model.md        # Phase 1 output — entities, validation, file format
├── quickstart.md        # Phase 1 output — runnable validation guide
├── contracts/           # Phase 1 output
│   ├── cli.md           #   command surface, exit codes, JSON schema
│   ├── core-api.md      #   endpaper.core public API
│   └── tui.md           #   screens, bindings, command-bar grammar
├── checklists/
│   └── requirements.md  # spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml               # hatchling, deps, entry point, ruff + mypy + pytest config
CHANGELOG.md
README.md

src/endpaper/
├── __init__.py              # __version__
├── __main__.py              # python -m endpaper
├── core/
│   ├── __init__.py          # the public API re-exported; nothing else is public
│   ├── errors.py            # EndpaperError hierarchy, exit_code class var
│   ├── models.py            # Workspace, Meeting, ScanWarning, MeetingFilter
│   ├── workspace.py         # find_workspace, init_workspace
│   ├── frontmatter.py       # tolerant reader (PyYAML) + deterministic emitter
│   ├── text.py              # slugify, parse_tags, new_meeting_id
│   ├── meetings.py          # create_meeting, scan_meetings, filter_meetings, match_meeting
│   └── templates/
│       └── AGENTS.md.tmpl   # packaged data file, <= 60 lines
├── cli/
│   ├── __init__.py
│   ├── main.py              # argv inspection, argparse wiring, error -> exit code
│   └── output.py            # tab-separated and JSON emitters, stdout/stderr split
└── tui/
    ├── __init__.py
    ├── app.py               # EndpaperApp, startup scan, in-memory list
    ├── list_screen.py       # list + preview panes, bindings, footer
    ├── preview_screen.py    # full-screen Markdown
    ├── command_bar.py       # verb sniffing, filter vs command
    └── app.tcss

tests/
├── conftest.py              # tmp workspace fixture, frozen clock, seeded ids
├── contract/                # CLI surface: exit codes, JSON keys, stdout/stderr, no ANSI
├── integration/             # end-to-end per user story, incl. headless TUI via Pilot
├── unit/                    # slugify, parse_tags, frontmatter round-trip, filters
├── performance/             # SC-004 scan < 2s, SC-005 filter < 100ms
└── fixtures/
    └── generate.py          # N-meeting workspace generator for performance tests
```

**Structure Decision**: Single project, `src/` layout, mandated by FR-006. The three-package split
under `src/endpaper/` is the constitution's Principle I made structural: `core/` imports neither
adapter, and `cli/` and `tui/` never import each other. The import-direction rule is enforced by a
test, not by convention — see Constitution Check gate I.

`core/templates/AGENTS.md.tmpl` ships as package data so `init` can write it without network or a
source checkout; hatchling includes it from `src/` with no `MANIFEST.in`.

## Implementation Sequencing

Ordered so each stage is independently verifiable, matching the spec's user story priorities.

| Stage | Delivers | Verified by |
|---|---|---|
| 0. Scaffolding | `pyproject.toml`, package skeleton, entry point, ruff/mypy/pytest config, CHANGELOG | `uv sync`, `endpaper --version` exits 0, gates run clean |
| 1. Core foundations | `errors`, `models`, `text`, `frontmatter` | Unit tests: slug table, tag parsing, YAML 1.1 coercion cases, emitter determinism |
| 2. Workspace (US1) | `find_workspace`, `init_workspace`, `AGENTS.md` template, `endpaper init` | US1 scenarios 2, 3, 5; AGENTS.md line count and `--tag` mention |
| 3. Create (US2) | `create_meeting`, `endpaper meeting new` | US2 scenarios 1–7; collision, `O_EXCL` race, untyped, empty-slug fallback |
| 4. Read (US3, CLI) | `scan_meetings`, `filter_meetings`, `meeting list` + `--json` | US3 scenarios 4–6; malformed-file tolerance; contract tests on the 7 keys |
| 5. TUI (US1, US3) | `EndpaperApp`, list + preview, command bar, bare-`endpaper` launch | US1 scenario 4; US3 scenarios 1–3; headless `Pilot` tests |
| 6. AI contract (US4) | `AGENTS.md` content, stderr/stdout audit, no-ANSI test, timeout tests | US4 scenarios 1–4 |
| 7. Hardening | Performance fixtures, path-budget test, cross-platform run | SC-004, SC-005, SC-010 |

Stage 3 is the MVP boundary: after it, a user can install endpaper and capture a meeting note, which
is the whole premise. Stages 4–5 make the notes findable.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No gate failed. One decision is recorded here because Principle III requires every third-party
dependency to justify itself in writing, and because this one was taken against the planner's
recommendation.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Runtime dependency on PyYAML | Frontmatter is YAML and users hand-edit it. Reading arbitrary hand-written YAML with a parser we own is precisely where Principle IV ("never lose the user's words") gets broken by accident. Requirements owner's decision. | A hand-rolled reader for the fixed six-field schema (~100 lines, zero dependencies) was recommended and rejected. Accepted cost: one dependency plus a normalization layer that coerces YAML 1.1's booleans and datetimes back to strings, so a tag of `no` does not become `False`. Mitigated by keeping the *write* path hand-written and deterministic, so `safe_dump`'s key sorting and 80-column wrapping never touch a user's file. |

## Follow-ups outside this plan

- **REQUIREMENTS.md §4.6 shows `m_20260728_a1b2`** (4 hex). The chosen id format is 8 hex. The
  example needs updating; the spec's FR-019 only requires uniqueness and stability, so no spec change
  is needed.
- **REQUIREMENTS.md §3.1 acceptance criterion 2** asks for byte-identical files from the CLI and TUI
  create paths, which cannot hold once ids and timestamps differ. Already restated in the spec's
  Assumptions as "identical except `id`, `created`, `updated`"; worth correcting at the source.
