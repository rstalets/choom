# Quickstart: Validating the `/link` Picker

**Feature**: `015-link-picker` | **Plan**: [plan.md](./plan.md)

How to prove the feature works, by hand and by test. Details of the data and the keys live in
[data-model.md](./data-model.md) and [contracts/tui.md](./contracts/tui.md).

---

## Prerequisites

```bash
uv sync
```

## Automated checks

```bash
uv run pytest tests/unit/test_link_candidates.py tests/unit/test_rendering.py   # ordering, rows
uv run pytest tests/integration/test_links.py                                    # the picker flows
uv run pytest                                                                    # everything
uv run ruff format --check . && uv run ruff check . && uv run mypy src           # the CI gates
```

Expected: all green. `tests/integration/test_links.py` is where the behaviour change is visible — the
old "several matches names candidates" test is rewritten as the too-short-terminal fallback, and the
picker flows are new.

---

## Manual validation

Set up a workspace with a deliberate collision. A workspace is found by walking up from the current
directory, so the commands run from inside it; `--project` keeps `uv` pointed at this checkout:

```bash
REPO=$PWD
cd "$(mktemp -d)"
uv run --project "$REPO" choom init
uv run --project "$REPO" choom meeting new "Q3 planning" --type standup
uv run --project "$REPO" choom note new "Q3 planning"
uv run --project "$REPO" choom note new "Q3 planning retrospective"
uv run --project "$REPO" choom note new "vendor landscape"
uv run --project "$REPO" choom          # bare `choom` opens the TUI
```

### Scenario 1 — the picker, inline (US1, US3)

1. Highlight `vendor landscape` in the list and press `e`. The editor opens **in the preview pane**;
   the list and scope pane stay visible.
2. Type `/link q3 planning` on an empty line and press `enter`.
3. **Expect**: a list rises above the status bar with the three Q3 records, first row highlighted. The
   list and scope panes have not moved. The footer reads `↑↓ move   enter insert   esc cancel`.
4. Press `↓` twice, then `↑` once. **Expect**: the highlight moves and wraps at the ends.
5. Press `enter`. **Expect**: the line becomes `[Q3 planning](../../…#meeting_…)` for the highlighted
   record, the list closes, the footer returns to the edit help, and the cursor is back in the editor.

### Scenario 2 — cancelling changes nothing (US1)

1. Submit `/link q3 planning` again.
2. Press `esc`. **Expect**: the list closes and the line still reads exactly `/link q3 planning`, ready
   to be edited and resubmitted.

### Scenario 3 — rows you can choose from (US2)

1. Submit `/link q3 planning`.
2. **Expect**: each row shows title, collection, and date — the meeting and the note called
   `Q3 planning` are distinguishable, and the newest record is first.

### Scenario 4 — the fast paths are untouched (US3)

1. Submit `/link vendor landscape` (one match). **Expect**: the link is inserted directly, no list.
2. Submit `/link nothing matches this at all`. **Expect**: `no record matches …` in the status bar, no
   list, line left as typed.

### Scenario 5 — full-screen parity (FR-004)

1. Press `esc` to leave the editor, `enter` on a record to open the full-screen reading view, then `e`.
2. Repeat scenarios 1, 2, and 4. **Expect**: identical behaviour in every respect.

### Scenario 6 — a short terminal (FR-017)

1. Resize the terminal to fewer than 12 rows.
2. Submit `/link q3 planning`. **Expect**: no list; the status bar names the candidates, as it did
   before this feature.
3. Submit it again in a tall terminal, and while the list is open, resize narrower.
   **Expect**: rows re-truncate, the highlight survives, the typed line is unchanged.

---

## What "done" looks like

- Every scenario above behaves as described in both hosts.
- `uv run pytest` is green, as are `ruff format --check`, `ruff check`, and `mypy src`.
- No new file appears anywhere in the workspace — the picker writes nothing but the link itself.
