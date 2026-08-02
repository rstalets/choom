# Contract: TUI

**Feature**: `017-editor-task-delete` | **Module**: `src/choom/tui/edit_screen.py`,
`src/choom/tui/status_bar.py`

The adapter's whole job: read the cursor's row, call core, phrase what core decided, apply the span core
computed, and render the result. It decides nothing about what gets removed.

---

## C1: The binding

Added to `EditorPane.BINDINGS`:

```python
Binding("ctrl+t", "delete_task", "Delete task", show=True)
```

No `priority=True` — `TextArea` does not bind `ctrl+t` and does not consume it as printable input
(research R1). Both hosts get it for free: `EditorPane` is what `EditScreen` and `ListScreen`'s inline
pane each mount, so FR-001's "identical in each" holds by construction rather than by duplication.

`ctrl+d` is not touched anywhere (FR-003).

## C2: The footer

`EDIT_HELP` in `status_bar.py`:

```
ctrl+o save   ctrl+x save & back   ctrl+t delete task   esc discard   ctrl+q quit
```

`LINK_PICKER_HELP` is unchanged — `ctrl+t` is inert while the picker is open, and an inert key is not
advertised. `tests/unit/test_footer_bindings.py::test_footer_advertises_every_shown_binding` already
enforces the pairing for `EditorPane`/`EDIT_HELP` and needs no new case.

## C3: When the action is live

`EditorPane.check_action` returns `False` for `"delete_task"` when either holds:

- `self._link_picker_line is not None` — a `/link` choice is pending
- `self._request is not None` — an `/ai` request is in flight

Otherwise `True`. This extends the existing gate at `edit_screen.py:384-400` rather than adding a
parallel one.

## C4: The gesture

`action_delete_task`, in order:

1. Read `row, _ = editor.cursor_location`. A multi-line selection is ignored (FR-030 edge case) — only
   the cursor's row matters.
2. `plan = plan_mirror_deletion(workspace, editor.text, row + 1, source=target.display_path,
   body_task_id=target.body_task_id)`.
3. `plan is None` → render `no task on this line` with `warn=False`. **Return. No dialog, no write**
   (FR-008).
4. Refusing outcome → render `plan.message` with `warn=True`. **Return. No dialog, no write.**
5. Otherwise push `ConfirmDialog` with the question from C5, `cancel_label="Keep It"`,
   `confirm_label="Delete"` — the same labels `ListScreen.action_delete` uses.
6. Dismissed falsy → do nothing at all. No save, no write, no status change (FR-014).
7. Dismissed truthy → run C6 against the captured `plan`.

The `plan` captured at step 2 is what step 7 acts on. Nothing is re-derived after the dialog, which is
FR-013.

## C5: The question

| Case | Text |
|---|---|
| `deletable` | `Delete "{description}"? It goes from this document and from your task list, and the document is saved. This cannot be undone.` |
| `line_only` | `Delete "{description}"? It is no longer in your task list, so only this line goes. The document is saved. This cannot be undone.` |
| `extra_text` is true | the applicable row above, plus ` This line has other text on it, which goes too.` |

`{description}` is `plan.description`. The "the document is saved" clause is required, not decorative:
`ctrl+t` commits unrelated unsaved edits in the buffer (FR-028/FR-030), and the user most at risk is the
one with a half-written paragraph elsewhere. It stays inside the existing single dialog — no second
dialog, no second stage (FR-009).

## C6: Applying a confirmed deletion

1. `commit_mirror_deletion(workspace, plan)`. On `NotFoundError` / `UsageError` / `WorkspaceError`:
   render the message and **return** — the buffer is untouched.
2. Convert core's offsets to widget coordinates and remove the line as one undoable edit:

   ```python
   doc = editor.document
   editor.delete(
       doc.get_location_from_index(plan.span[0]),
       doc.get_location_from_index(plan.span[1]),
       maintain_selection_offset=False,
   )
   ```

   `editor.text = plan.text` is **forbidden** — the setter is an alias of `load_text`, which clears the
   whole session's undo history (research R2).

   Post-condition, and the assertion that keeps the adapter honest: `editor.text == plan.text`.
3. `self._save()`, which stamps `updated`, heals links, and reconciles every remaining task line. A
   failure here leaves the task deleted and the buffer dirty with the line removed; the save's own
   message is rendered and nothing further is attempted (research R8).
4. Render `deleted "{description}"` with `warn=False`. When the save produced warnings — most commonly
   the dead-line warning for a second copy of the same task elsewhere in the document (FR-025) — the
   warning is shown and the deletion note is folded in with it rather than replacing it.

To keep step 4 from racing `_save()`'s own status render, `_save` takes an optional leading note it folds
into whatever it renders (`_save(note: str | None = None)`); the deletion passes its note there instead of
rendering separately afterwards.

## C7: Cursor and scroll

`maintain_selection_offset=False` lands the cursor at the edit's end point, which for a pure deletion is
the span's start — column 0 of whatever line now occupies the removed line's position, or the end of the
document when the removed line was last. That is FR-032 with no extra code. No scroll call is made, so
the viewport does not jump.

## C8: Status messages

| Situation | Text | `warn` |
|---|---|---|
| Not a task line | `no task on this line` | `False` |
| `unreadable_tasks` | `tasks.md:{n} could not be read; fix that line, then try again — nothing was deleted` | `True` |
| `ambiguous_id` | `delete_task`'s own message, naming the conflicting lines | `True` |
| `self_referential` | `this line is the task you are editing; close this editor and delete it from the tasks list` | `True` |
| Commit failed | the exception's message | `True` |
| Save failed | the `SaveResult` message | `True` |
| Success | `deleted "{description}"` | `False` |
| Success, save warned | the warnings, with the deletion note folded in | `True` |

Every refusal names both the cause and the next step, per Principle V.

## C9: `EditTarget`

Gains `body_task_id: str | None = None`. `open_task_editor` passes the id it already holds;
`open_editor` leaves the default. No other construction site exists.

## C10: What does not change

- `ListScreen`'s `ctrl+d`, its dialog, and `LIST_HELP` / `TASK_LIST_HELP`.
- `ConfirmDialog` — reused as-is, no new parameter, no new style.
- `/task`, `/link`, `/ai`, and their status handling.
- `PreviewScreen`, the collection bar, the scope pane, the links pane.
- Any CLI surface.
