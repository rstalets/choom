# Quickstart: Editor Replaces the Preview Pane

**Feature**: `014-inline-editor-pane` | **Date**: 2026-08-01

How to validate this feature end to end. See [contracts/tui.md](./contracts/tui.md) for the rules being
checked and [research.md](./research.md) for why each one is where it is.

## Prerequisites

```bash
uv sync
```

A throwaway workspace to poke at:

```bash
uv run choom init /tmp/choom-014 && uv run choom workspace use /tmp/choom-014
uv run choom meeting new "Q3 planning" --type standup
uv run choom note new "Reading list"
uv run choom task add "call the vendor"
```

## Automated checks

```bash
uv run pytest                      # whole suite — the existing editor tests are the regression net
uv run pytest tests/integration -k "inline or edit or preview or discard or ctrl_q"
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

The suite is the primary gate. `test_edit_presentation.py` and `test_edit_from_list_tui.py` between them
cover the behaviour this feature moves; both must pass unchanged in substance.

## Manual walkthrough

Run `uv run choom` and work through these in order. Each maps to a user story.

**US1 — edit a note without losing your place**

1. Move to Notes, highlight "Reading list", press `e`.
   → The editor appears where the preview was. The list, the scope pane, and the collection bar are all
   still on screen. The bottom bar reads `ctrl+o save   ctrl+x save & back   esc discard   ctrl+q quit`.
2. Type `j k e b space slash` as literal characters, then `/`, then `tab`.
   → All of it lands in the buffer. The highlighted row never moves, no filter opens, the collection
   does not change, and focus stays in the editor.
3. Press `ctrl+x`.
   → The editor closes, the preview returns with the typed text in it, and "Reading list" is still the
   highlighted row.

**US2 — a task's details, in place**

4. Move to Tasks, highlight "call the vendor", press `e`, type a line, press `ctrl+x`.
   → Same shape as above, with the task list visible throughout.

**US3 — full-screen reading keeps its full-screen editor**

5. Move to Meetings, highlight "Q3 planning", press `enter`, then `e`.
   → A full-screen editor, not an inline one. Save and close returns to the full-screen reading view.

**US4 — creating a record keeps the list in view**

6. From the list, press `/`, type `note Weekly review`, press `enter`.
   → The editor opens in the pane, the list is still beside it, and "Weekly review" is the highlighted
   row while you type.

**Edge cases worth doing by hand**

7. With an inline editor open and unsaved text, press `escape`.
   → The confirmation appears. Decline → the editor is back with your text and the cursor in it. Repeat
   and confirm → the editor closes, the file is unchanged.
8. With an inline editor open and unsaved text, press `ctrl+q`.
   → The same confirmation, not an immediate exit.
9. Resize the terminal narrow (about 60 columns) while an inline editor holds a long paragraph.
   → It re-wraps to the pane's new edge. Nothing is cut off, nothing scrolls sideways, and the text is
   intact.
10. With an inline editor open, create a file in the workspace from another terminal
    (`uv run choom note new "From outside"`), wait past the refresh interval.
    → The list does not move and the buffer is untouched. Close the editor → the new record appears.

## Expected outcomes

| Check | Pass looks like |
|---|---|
| SC-001 | The list is visible in every screenshot taken during steps 1–6 |
| SC-002 | The same row is highlighted before and after every edit |
| SC-004 | No keystroke in step 2 changed the list |
| SC-005/006 | Step 9 wraps and loses nothing |
| SC-007 | Step 5 behaves as it did before the change |
