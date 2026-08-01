# Implementation Plan: Assistant Discovery File

**Branch**: `013-assistant-discovery-file` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/013-assistant-discovery-file/spec.md`

## Summary

Naming an assistant installs a short, choom-owned pointer in that assistant's own user-scope
directory — what choom is, the absolute workspace path, and "the instructions are in that
workspace's `AGENTS.md`" — so an assistant started anywhere on the machine can find the workspace.
The same install is offered once, at launch, to users who never run the command, through the shared
confirmation `011-ui-refinements` introduced.

Technically: one new core module (`core/discovery.py`) owning path resolution, rendering, install
and removal; one new field on the existing `AssistantProfile`; one generalised config helper so a
second key can be written into `[assistant]` without a second regex path; and thin adapter changes —
one stderr line and two `--json` keys in the CLI, one deferred `ConfirmDialog` in the TUI.

## Technical Context

**Language/Version**: Python 3.11+ (`from __future__ import annotations` throughout)

**Primary Dependencies**: standard library only for this feature. Textual is already present and is
used only for the existing `ConfirmDialog`; no new third-party dependency is added.

**Storage**: plain files. The workspace's `.choom/config.toml` gains one key; the discovery file is
a generated artifact in the user's profile directory, never read back by choom.

**Testing**: pytest — `tests/unit/`, `tests/contract/`, `tests/integration/` as laid out in R12,
with an autouse fixture redirecting the profile root to `tmp_path` (R13).

**Target Platform**: Windows, macOS, Linux. Windows is first-class; no admin rights; no network.

**Project Type**: single project — a library core with two peer adapters (CLI and TUI).

**Performance Goals**: the launch check must be imperceptible. It is a `stat` of one path plus a
TOML read choom already performs, so the budget is met by construction rather than by measurement;
no performance test is warranted (SC-007, SC-011).

**Constraints**: no network, no admin rights, no prompt or block in the CLI, Windows 260-character
path limit, workspace paths containing spaces and non-ASCII characters, and a 20-line backstop on
the generated file.

**Scale/Scope**: two supported assistants; one generated file at a time; five user stories.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Gate | Status |
|---|------|--------|
| I | All logic in `choom.core` | **PASS** — reads and writes go through `core/discovery.py` (`discovery_path`, `render_discovery_file`, `install_discovery_file`, `remove_discovery_files`, `installed_discovery_path`) and `core/config.py` (`get_assistant`/`set_assistant`, new `get_launch_offer_made`/`set_launch_offer_made`). Read of `core`'s existing API first: `write_text_atomic` already creates parent directories and cleans up its temp file, so FR-011 needs no new code; `_apply_assistant_value` already does the comment-preserving line edit FR-025's config write needs, so it is generalised rather than duplicated. Adapters only choose wording and streams. |
| II | Both interfaces; CLI never blocks; stable `--json` and exit codes | **PASS** — install and removal are reachable from the CLI (`config assistant <value>`, `init --assistant`) and the TUI (`/config assistant`). The launch *question* is TUI-only under the constitution's own "inherently interactive" exemption; its outcome, the install, has a non-interactive peer in the set command. `--json` gains two keys and renames none. Exit codes unchanged. No prompt, block, or pager is added to any CLI path. |
| III | No new source of truth; no new binary dependency; no needless knob | **PASS** — no index, database, or cache. The discovery file is a derived artifact regenerated from the workspace path, never read back, so it is not a second source of truth. No new dependency. The one new config key records that an interaction happened; it is not a user-tunable preference and has no sensible default to collapse into. |
| IV | Parsers tolerate malformed input; writes preserve the user's words | **PASS** — the new config read never raises: missing file, missing table, malformed TOML, or a non-boolean value all read as "not offered". The write is line-targeted and preserves comments, key order, and unknown keys. No user file is moved. The only file overwritten in full is choom's own, marked as generated, and deletion is guarded by that marker (R11). |
| V | TUI one screen; confirmations fire only when data would be lost | **FAIL** — the launch offer is a confirmation that guards no loss. Recorded in Complexity Tracking. Everything else holds: the dialog is the existing shared one, one keystroke either way, no new binding, and it consumes its own keystrokes. |
| VI | Type hints, docstrings, risk-based tests, no wall-clock dependency | **PASS** — every new `core` function is typed and documented with what it raises. Tests are placed by risk (R12), not one per acceptance scenario. Nothing in this feature reads a date. |
| — | Platform constraints | **FAIL on one clause** — no admin rights, no network, short target paths, spaces and non-ASCII handled, `Path.home()` resolves `%USERPROFILE%`. But the record of the launch offer is per-user state stored inside the shared workspace. Recorded in Complexity Tracking. |

**Post-Phase 1 re-check**: unchanged. The design added no new violation; both FAILs are the ones the
spec named in advance, and Phase 1 narrowed rather than widened them — the marker-guarded removal
(R11) and the single profile-root seam (R13) both reduce blast radius outside the workspace.

## Project Structure

### Documentation (this feature)

```text
specs/013-assistant-discovery-file/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── cli-config-assistant.md
│   └── discovery-file.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/choom/
├── core/
│   ├── assistants.py        # CHANGED: AssistantProfile gains its discovery location
│   ├── config.py            # CHANGED: generalised key writer; launch-offer read/write
│   ├── discovery.py         # NEW: paths, rendering, install, removal
│   ├── models.py            # CHANGED: AssistantProfile field
│   └── workspace.py         # CHANGED: init --assistant installs (US5)
├── cli/
│   └── main.py              # CHANGED: stderr reporting, two --json keys
└── tui/
    ├── app.py               # CHANGED: deferred launch offer in on_mount
    └── list_screen.py       # CHANGED: accepts the offer's outcome as pending status

tests/
├── unit/
│   ├── test_discovery_paths.py      # NEW
│   ├── test_discovery_content.py    # NEW
│   ├── test_discovery_install.py    # NEW
│   └── test_config_write.py         # CHANGED: the new key, hand-edited configs
├── contract/
│   └── test_config_assistant_cli.py # NEW or extended
├── integration/
│   └── test_launch_offer.py         # NEW
└── conftest.py                      # CHANGED: autouse profile-root redirect
```

**Structure Decision**: the existing single-project layout is unchanged. The one new module,
`core/discovery.py`, sits beside `core/assistants.py` — separate because installing a file into a
profile directory shares no machinery with spawning and cancelling a subprocess (R4).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **Gate V** — a confirmation that guards no loss (US2, FR-022–FR-034) | It is the only moment choom writes outside the workspace, into a directory belonging to another program, and the only route by which users who never run `config assistant` get the feature at all. Bounded so it cannot become a reflex: at most once per workspace ever, one keystroke either way, and the shared dialog with its usual key meanings. | **Install silently** — writing into the user's profile for another program without asking is a larger liberty than the dialog it avoids. **A status-bar hint instead** — carries no answer, so either it nags every launch or it is missed once and never seen again. **Cut US2** — leaves the feature reachable only through a command the affected users have no reason to run; this remains the fallback if the trade is rejected, and the other four stories stand without it. |
| **Platform clause** — per-user state (the launch-offer record) inside the shared workspace | Directed by the feature request, and it sits with the `[assistant] name` setting it qualifies, which is already per-workspace. | **A per-user state file** — splits one decision across two stores and contradicts the explicit direction. The rule exists to stop one person's state silently becoming another's; that failure is not reachable here, because what a colleague on a synced folder inherits is a missing question, not an overwritten selection — the discovery file itself is per-profile and never shared. |
