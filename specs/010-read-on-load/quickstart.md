# Quickstart: Validating Read From Disk on View Load

**Feature**: 010-read-on-load | **Date**: 2026-08-01 | **Plan**: [plan.md](./plan.md)

How to reproduce the bug this feature fixes, confirm the fix by hand, and run the automated checks. Nothing
here is implementation code — see [contracts/view-refresh.md](./contracts/view-refresh.md) for the rules
being validated and [data-model.md](./data-model.md) for the state involved.

## Prerequisites

```bash
uv sync                      # dependencies, pinned
uv run choom --version       # confirms the CLI entry point resolves
```

choom finds its workspace by walking up from the current directory — there is no `--workspace` flag — so
each command below runs with the scratch vault as its working directory. `uv run` resolves the project from
*its* working directory, so pin it to the checkout with `--project`:

```bash
export CHOOM_REPO="$PWD"                       # the choom checkout
export CHOOM_TEST_WS="$(mktemp -d)/vault"      # a scratch vault, so no real notes are touched
mkdir -p "$CHOOM_TEST_WS"
choomctl() { (cd "$CHOOM_TEST_WS" && uv run --project "$CHOOM_REPO" choom "$@"); }

choomctl init
choomctl meeting new "Existing meeting"
choomctl task add "Follow up on the thing"
```

## 1. Reproduce the bug (before the change)

This is the reproduction from issue #51, run by hand. Two terminals.

**Terminal A** — open the TUI (bare `choom`, no subcommand) and leave it on the Meetings list:

```bash
cd "$CHOOM_TEST_WS" && uv run --project "$CHOOM_REPO" choom
```

**Terminal B** — act as the assistant would, from a separate process (redefine `choomctl` here, or just
`cd "$CHOOM_TEST_WS"` first):

```bash
choomctl meeting new "Assistant wrote this"
choomctl task list --json          # a JSON array of task objects; note the "id"
choomctl task done task_2b2e       # substitute the id from the line above
```

**Back in Terminal A**: press `tab` to cycle collections and return to Meetings; visit Tasks.

- *Before this feature*: one meeting, and the task still reads open. Only `ctrl+q` and a relaunch reconcile
  either.
- *After US1*: both meetings are listed and the task reads done, without leaving the app.
- *After US2*: the same, without pressing anything — within about two seconds.

## 2. Verify each user story by hand

**US1 — read on load.** With the app on any list, from Terminal B: create a document, delete a file, and
edit a title. Navigate away and back in Terminal A after each. Every change is visible. Open a document with
`enter` after editing it externally — the preview shows the current text.

**US2 — refresh timer.** Park on Tasks, touch nothing, and complete a task from Terminal B. The row flips to
done on its own. Then leave the app idle on an unchanged workspace for a minute: nothing flickers, nothing
scrolls, and a selected row stays selected. Open the preview and leave it open — the body must not re-render
underneath you.

**US3 — filter.** On a workspace with many months (see the fixture generator below), press `/` and confirm
the bar opens with no pause. Type `filter ` then a term — matches appear across months. Type `task` first,
backspace it away, then `filter <term>`: still immediate.

A larger workspace for the filter and performance checks:

```python
# tests/fixtures/generate.py provides generate() and generate_notes()
from pathlib import Path
from tests.fixtures.generate import generate
workspace = generate(Path("/tmp/choom-big"), 1000, spread_months=12)
```

## 3. Run the automated checks

```bash
uv run pytest tests/integration -q         # US1/US2/US3 end-to-end paths
uv run pytest tests/unit -q                # change-detection key
uv run pytest tests/performance -q         # SC-003 and SC-004 budgets
uv run pytest -q                           # everything, as CI runs it
```

Quality gates, all of which must pass before review:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
```

## 4. What each check proves

| Check | Requirement | Passes when |
|---|---|---|
| Out-of-process create/delete/edit observed after navigation | FR-001, FR-002, FR-004, SC-001 | The view matches disk with no restart |
| Preview opened after an external edit | FR-003 | Rendered body is current |
| Checkbox ticked in a body, then Tasks visited | FR-006, SC-007 | Task reads done with no refresh call wired for that path |
| Malformed file added out of process | FR-007, FR-008 | File skipped, rest of list renders, warning count current |
| Tick invoked directly against an unchanged workspace | FR-010, SC-006 | No rebuild; selection and scroll intact |
| Tick invoked directly after an external change | FR-009, FR-011, SC-005 | List updates, same record still selected |
| Interval registration | FR-009 | Timer registered at `REFRESH_SECONDS`; **no test sleeps or waits for a tick** (Principle VI) |
| Tick while command bar open / filter active | FR-012, FR-013 | Returns without reading or rendering |
| `/` on a 1,000-document workspace | FR-016, SC-004 | Keypress returns before hydration finishes |
| Second filter term in one bar session | FR-018, FR-019 | No additional file reads |
| Existing month-scope test | C3, SC-003 | A list load still reads only the displayed month |
| Scan cost per displayed month | research R5 | A representative month scans inside one 60 fps frame (~15 ms); breaching it is the trigger to move the tick's read to a worker |

## 5. Cleanup

```bash
rm -rf "$(dirname "$CHOOM_TEST_WS")" /tmp/choom-big
```

## Troubleshooting

- **The list does not update on its own but does on navigation.** US1 landed, US2 did not — check that the
  interval is registered and that the timer is resumed on `ScreenResume`.
- **The list updates but the selection jumps to the top.** `refresh_rows` is being called without
  `select_id`; C4 requires selection by record id.
- **Typing in the command bar feels heavy.** Something is scanning per keystroke — most likely
  `_render_status` calling `visible_warnings()` (research R3) or hydration being started from the
  `ModeChanged` handler rather than from `action_open_command_bar` (research R6).
- **A test hangs for seconds.** Something is waiting for a real tick. Invoke the callback directly instead
  (research R9).
