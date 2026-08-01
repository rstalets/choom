# Contract: TUI chrome

**Feature**: `011-ui-refinements` | **Covers**: FR-009–FR-014, FR-021–FR-043 (US1, US2, US5, US6, US7)

Four surfaces. Each section states what is rendered, what keys do, and what must not change.

---

## 1. Confirmation

**Component**: `ConfirmDialog(ModalScreen[bool])` — the only confirmation in the product (FR-026).

**Construction**: question text, plus a label for each of the two options.

```text
+------------------------------------------------------------------------------+
|            You have unsaved changes. Are you sure you want to exit?           |
|                (Esc) Continue Editing       (Enter) Exit Without Saving       |
+------------------------------------------------------------------------------+
```

| Key | Result | Always |
|---|---|---|
| `Esc` | `dismiss(False)` — halts the request, changes nothing | FR-023 |
| `Enter` | `dismiss(True)` — proceeds with what the user asked for | FR-024 |
| anything else | consumed, no effect, dialog stays up | FR-025 |

Rules:

- Centred on the whole screen, regardless of which pane raised it (FR-021).
- No `Button`, no focusable child — there is no highlight to move (FR-022).
- Each label names its key **and** the outcome. No bare "OK", "Yes", "No", or "Cancel" (SC-006).
- Raised only where something would be lost: discarding unsaved edits, and deleting a record (FR-027).

**Call sites**: exactly two.

| Site | Question | `Esc` | `Enter` |
|---|---|---|---|
| Editor, unsaved changes | `You have unsaved changes. Are you sure you want to exit?` | `Continue Editing` | `Exit Without Saving` |
| List, `ctrl+d` | `Delete "<title>"? This cannot be undone.` | `Keep It` | `Delete` |

`discard_dialog.py` is removed. No second dialog class exists after this feature.

---

## 2. Delete from the list

| Element | Contract |
|---|---|
| Binding | `ctrl+d`, shown in the footer wherever active (FR-014) |
| No highlight | Inert — no dialog, no error (FR-014) |
| Command bar open | The keystroke belongs to the bar; no dialog |
| Record identity | Captured when the dialog is raised, acted on when it returns (FR-010) |
| On confirm | `core.deletion.delete_by_id`, then the list re-reads |
| Highlight after | The next record; the previous one if the deleted record was last; the empty state if it was the only one (FR-011, FR-012) |
| On failure | The reason in the status bar; the session stays usable (FR-013) |

The refresh timer is already paused while a modal screen is up, and the captured id makes the outcome
correct even if it were not (research R11).

---

## 3. List columns

**Module**: `tui/columns.py` — pure, no widget imports, unit-tested without a terminal.

```python
column_widths(total: int) -> ColumnLayout
render_row(cells: Sequence[str], layout: ColumnLayout) -> str
render_header(layout: ColumnLayout) -> str
```

| Column | Content (documents) | Content (tasks) |
|---|---|---|
| Date | `created[:10]` | `task.created` |
| Type | `document.type` | `task.type` |
| Title | `document.title` | `task.text` |
| Tags | comma-joined | comma-joined |

Rules:

- A header row sits above the list and does not scroll (FR-029).
- An empty value leaves an empty cell; no column shifts (FR-030).
- Overflow truncates with `…`; a row never wraps (FR-031).
- When width is short, whole columns drop **with their headers**, tags first, then type. Date and title
  always survive (FR-032).
- Tasks use the same four columns; the done state stays visible as its existing leading marker and
  struck-through text (FR-033).

`DocumentRow.document` and `TaskRow.record` keep their names and types — `list_screen`, the links pane,
and `tests/helpers.py` read them.

---

## 4. Top bar

**Widget**: `CollectionBar`, unchanged in structure. The workspace path is appended, flush right.

```text
Choom >>   Tasks   Notes   Meetings                        ~/OneDrive/notes/work
```

| Rule | Requirement |
|---|---|
| Anchored to the right edge, across resizes | FR-034 |
| `$HOME` prefix shown as `~` | FR-035 |
| Too long → elide from the left (`…/`), whole components, final component always kept | FR-036 |
| Spaces and non-ASCII render as-is | FR-037 |
| Collection names never truncate to make room | FR-036 |
| No bottom-bar width is used | FR-038 |

The existing compact one-letter collection fallback still applies at the narrowest widths, and the path
keeps its final component there.

Computed with `os.path` string operations only — no filesystem access on a redraw.

---

## 5. Editor cursor

On entering edit mode, from any entry point including a task body (FR-043):

| Content | Cursor lands |
|---|---|
| `"# Notes\nfirst line"` | line 3, column 0 — one blank line below `first line` (FR-039) |
| `"# Notes\nfirst line\n\n\n"` | one blank line below `first line`; existing trailing blanks are normalised, not stacked (FR-040) |
| `""` | line 1, column 0; nothing inserted above (FR-041) |

The buffer is padded to make that position exist, and `original_text` is set to the padded text, so:

- Entering and leaving without typing raises **no** confirmation and writes nothing (FR-042).
- Saving without typing writes one trailing blank line and is idempotent (accepted; research R10).

---

## What must not change

- The `list → preview → edit` state machine, and every existing binding.
- `ctrl+c` and `ctrl+q` stay reserved.
- The bottom bar's help text and version indicator.
- The product name, divider, collection names, order, and highlight in the top bar.
- What the editor saves, when it saves, and how it handles conflicts.
