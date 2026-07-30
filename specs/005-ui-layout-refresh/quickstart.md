# Quickstart: validating the UI Layout Refresh

**Feature**: `005-ui-layout-refresh` | **Date**: 2026-07-30

How to prove this feature works, from a clean checkout. Implementation belongs in `tasks.md`; this
file is the run-and-check guide and the FR → test map.

---

## Prerequisites

```bash
# from the repo root
uv venv && uv pip install -e ".[dev]"     # or: pip install -e ".[dev]"
```

Everything runs offline. No admin rights, no services.

---

## The full gate

What CI runs and what must be green before review (constitution, Development Workflow):

```bash
ruff format --check .
ruff check .
mypy
pytest
```

The release dry-run workflow runs this same gate before building, so a rehearsal is at least as
strict as pull-request review. (`publish.yml` currently runs `pytest` only — noted in research R9a
as a gap that belongs to the release process rather than to this feature.)

---

## Scenario 1 — Collections along the top (US1)

```bash
python -m endpaper          # in a workspace created with `endpaper init`
```

1. The top line reads `Endpaper >>   Tasks   Notes   Meetings`, with **Tasks** highlighted.
2. Press `tab` → Notes highlights, the panes refill, and the cursor is on the middle pane's top row.
3. Press `tab` twice more → wraps past Meetings back to Tasks.
4. Press `shift+tab` → Meetings.
5. Press `/`, type `fil`, press `tab` → **nothing switches**; the keystroke belongs to the bar.

Automated: `tests/integration/test_collection_bar_tui.py`

---

## Scenario 2 — One month at a time (US2)

```bash
python -m tests.fixtures.generate --count 400 --path /tmp/ep-months --spread-months 12
cd /tmp/ep-months && python -m endpaper
```

1. Tab to Notes. The left pane shows `2026-07` highlighted, and the middle pane lists only July.
2. Press `h`, then `j` → `2026-06`; the middle pane refills and the preview follows.
3. Press `l` to return to the list.
4. Tab away and back → the collection reopens on the **current** month.

The read-scoping claim is not eyeballed — it is asserted by counting opened paths:

```bash
pytest tests/performance/test_month_scope.py -v
```

Automated: `tests/unit/test_list_months.py`, `tests/unit/test_scan_month.py`,
`tests/integration/test_month_pane_tui.py`, `tests/performance/test_month_scope.py`

---

## Scenario 3 — To-Do and Done (US3)

1. Tab to Tasks. The left pane shows **To-Do** (highlighted) and **Done**; the right pane is blank.
2. `space` on the top task → it leaves To-Do.
3. `h`, `j` → Done; the completed task is there.
4. `space` → it returns to To-Do.

CLI parity for the same selection:

```bash
endpaper task list --done
endpaper task list --done --json
```

Automated: `tests/unit/test_task_filter_only_done.py`, `tests/integration/test_task_category_tui.py`,
`tests/integration/test_task_cli.py` (extended for `--done`)

---

## Scenario 4 — Editing starts where you are looking (US4)

1. Tab to Notes, highlight a note, press `e` → the editor opens on its raw markdown.
2. Type, `ctrl+x` → back on the list, same note highlighted, row updated.
3. Press `/`, type `note standup follow-up`, `enter` → the **editor** opens directly; no read view.
4. `ctrl+x` → the list, in the new note's month, with it highlighted.
5. Tab to Tasks, press `e` → nothing happens.

Automated: `tests/integration/test_edit_from_list_tui.py`,
`tests/integration/test_create_opens_editor_tui.py`

---

## Scenario 5 — Commands are commands (US5)

1. Press `/` → a `/` appears and the cursor sits after it.
2. Press `backspace` repeatedly → the `/` survives and the bar stays open.
3. Type `filter budget` → the list narrows live, including matches from other months.
4. `escape` → filter cleared, the previously displayed month is back.
5. Type `/budgt` → `⚠ unknown command: 'budgt'. Press / then 'help' for the list.`, list unchanged.

Automated: `tests/unit/test_command_parsing.py`, `tests/integration/test_filter_verb_tui.py`,
`tests/integration/test_cross_month_filter_tui.py`

---

## Scenario 6 — Help and version (US6)

1. Press `/`, type `help`, `enter` → a pane covers the lower screen with the list still visible above.
2. Every verb appears with a description.
3. `escape` → the pane closes; highlighted row, month, and filter are exactly as they were.
4. The bottom-right reads `v0.0.0` from a source checkout, matching:

```bash
endpaper --version        # endpaper 0.0.0
```

The test asserts the two agree — never a literal version, which would have to be edited at every
release and would then be the drift it exists to catch.

Automated: `tests/integration/test_help_pane_tui.py`, `tests/integration/test_version_indicator.py`

---

## Scenario 7 — The version is stamped by the build (FR-043)

From a source checkout, the version is deliberately not a plausible release:

```bash
python -c "import endpaper; print(endpaper.__version__)"   # 0.0.0
endpaper --version                                          # endpaper 0.0.0
```

A real build carries the real version. The build hook is disabled by default
(`enable-by-default = false` in `pyproject.toml`) precisely so `uv pip install -e .` does not stamp
a development version — a real build opts back in with `HATCH_BUILD_HOOKS_ENABLE=1`:

```bash
HATCH_BUILD_HOOKS_ENABLE=1 uv build --no-sources
python -m venv /tmp/ep-check && /tmp/ep-check/bin/pip install --quiet dist/*.whl
/tmp/ep-check/bin/endpaper --version        # the VCS tag, e.g. endpaper 0.0.4
```

And a pretended version is honoured, which is the mechanism the dry-run workflow uses:

```bash
HATCH_BUILD_HOOKS_ENABLE=1 SETUPTOOLS_SCM_PRETEND_VERSION=9.9.9 uv build --no-sources
python -m venv /tmp/ep-pretend && /tmp/ep-pretend/bin/pip install --quiet dist/endpaper-9.9.9*.whl
/tmp/ep-pretend/bin/endpaper --version      # endpaper 9.9.9
```

**Verified during implementation** (research R9): `uv pip install -e .` stamps a development
version by default — hatch-vcs's build hook documents that it runs on install as well as build,
and scoping it to the wheel/sdist *targets* does not exempt an editable install, because an
editable install also builds the `wheel` target. The mechanism that actually works is
hatchling's own hook gate: `enable-by-default = false` plus `HATCH_BUILD_HOOKS_ENABLE=1` opt-in
for real builds (`publish.yml`, `release-dry-run.yml`). FR-043's acceptance criterion — a source
checkout reports `0.0.0` — holds under this mechanism.

Automated: `tests/unit/test_version_fallback.py`, `tests/contract/test_version_parity.py`

---

## Scenario 8 — Rehearsing a release (dry-run workflow)

On GitHub: **Actions → Release dry run → Run workflow**, enter a proposed version such as `0.0.4`.

Expected:

1. The quality gate and the test suite run.
2. The build produces `endpaper-0.0.4-*.whl` and `endpaper-0.0.4.tar.gz`.
3. The workflow installs the wheel and asserts `endpaper --version` reports exactly `endpaper 0.0.4`
   — a mismatch fails the run.
4. `dist/` is attached to the workflow run as a downloadable artifact.
5. **Nothing is published**, no tag is created, and the repository is unchanged.

Locally, the same rehearsal without GitHub:

```bash
HATCH_BUILD_HOOKS_ENABLE=1 SETUPTOOLS_SCM_PRETEND_VERSION=0.0.4 uv build --no-sources && ls dist/
```

Verify the safety property by reading the workflow rather than by running it: the job must declare
no `environment: pypi` and no `id-token: write`, so it holds no credential that could publish. See
[contracts/versioning.md](./contracts/versioning.md).

---

## Terminal verification (before release, not automated)

Constitution, Development Workflow — TUI changes must be checked on the target terminals. This
feature touches layout and key handling, so all of it needs a look:

| Terminal | What to check |
|---|---|
| Windows Terminal | `shift+tab` arrives; top bar renders; no wrapping at 80 columns |
| iTerm2 | Same, plus the help pane's alpha background |
| macOS Terminal | Same; confirm the highlight is legible without colour support assumptions |
| PuTTY | `shift+tab` arrives (the most likely place for it not to); box drawing |
| tmux | `shift+tab` and `ctrl+q` pass through; the modal help pane redraws on resize |

Also check a terminal narrower than three panes (spec edge case): the layout must degrade without
making the highlighted collection ambiguous.

---

## FR → test map

| FR | Covered by |
|---|---|
| FR-001–FR-002 | `test_collection_bar_tui.py::test_bar_lists_three_collections_with_one_active` |
| FR-003–FR-005 | `test_collection_bar_tui.py::test_tab_wraps_and_focuses_list` |
| FR-006 | `test_partitioned_layout.py` (updated) |
| FR-007 | `test_collection_bar_tui.py::test_tab_inert_while_command_bar_open` |
| FR-008 | `test_list_tui.py` (updated) |
| FR-009–FR-011 | `test_month_pane_tui.py` |
| FR-012 | `test_month_scope.py::test_opening_collection_reads_only_current_month` |
| FR-013–FR-014 | `test_list_months.py`, `test_month_pane_tui.py` |
| FR-015 | `test_create_opens_editor_tui.py::test_create_moves_scope_to_new_month` |
| FR-016 | `test_month_pane_tui.py::test_warning_count_is_per_month` |
| FR-017–FR-021 | `test_task_category_tui.py`, `test_task_filter_only_done.py` |
| FR-022–FR-026 | `test_edit_from_list_tui.py`, `test_create_opens_editor_tui.py` |
| FR-027–FR-028 | `test_command_bar_prefix.py` |
| FR-029–FR-031 | `test_command_parsing.py`, `test_filter_verb_tui.py` |
| FR-032–FR-034 | `test_cross_month_filter_tui.py` |
| FR-035–FR-036 | `test_month_scope.py::test_filter_reads_each_month_once` |
| FR-037 | `test_command_parsing.py::test_existing_verbs_unchanged` |
| FR-038–FR-041 | `test_help_pane_tui.py` |
| FR-042 | `test_version_indicator.py`, `test_version_parity.py` |
| FR-043 | `test_version_fallback.py`, plus the dry-run workflow's install-and-assert step |
| FR-044–FR-046 | `test_list_tui.py`, `test_partitioned_layout.py` (updated) |

Every functional requirement has at least one test (Principle VI). The `tests/contract/` suite must
pass unmodified apart from the new `--done` flag — it pins the CLI guarantees this feature is not
allowed to disturb.
