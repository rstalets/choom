# Contract: the editor's behaviour on save

**Feature**: `018-automatic-link-detection`

No new binding, no new screen, no new dialog, no new state. Everything below rides `ctrl+s`, which
already exists and is already advertised in the editor footer.

---

## T1. Which saves convert

| Gesture | Path | Converts? |
|---|---|---|
| `ctrl+s` in a meeting or note | `open_editor._save` → `editing.save_buffer` | **yes** |
| `ctrl+s` in a task's body | `open_task_editor._save` → `tasks.set_task_body` | **yes** |
| Opening a document | `reconcile_on_open` → `mirrors.write_document` | no |
| Opening a task | `reconcile_on_open` → `tasks.set_task_body` | no |
| Ticking a mirror in the tasks list | mirror sync → `write_document` | no |
| `choom links heal` / `check` | `links.py` | no |

Rows 3 and 4 are the ones a refactor is most likely to break, so they are pinned by integration test
rather than left to the call graph.

---

## T2. The buffer shows what landed

`EditorPane._save` already re-syncs the buffer after a save, because the `updated:` stamp changes the
text:

```python
if result.saved_text != editor.text:
    cursor = editor.cursor_location
    editor.text = result.saved_text
    editor.cursor_location = cursor
```

This is unchanged in shape and is what delivers FR-026 for free: the converted links appear in front
of the user the instant the save completes.

**What does change** is the cursor restore. The `updated:` stamp is length-neutral, so restoring
`(row, col)` verbatim has always been correct. A conversion is not. The restore becomes:

1. Row is used as-is — no conversion inserts a newline (data-model §1, invariant 4), so the cursor
   never changes line.
2. Column is mapped through `core.links.map_cursor_offset`, using Textual's
   `Document.get_index_from_location` / `get_location_from_index` to move between coordinates and
   offsets. Both are present on `textual==8.2.8`.

| Cursor was | Cursor ends up |
|---|---|
| Before every conversion on its line | exactly where it was |
| After a conversion on its line | the same logical position, shifted by what was inserted |
| Inside the URL that was just wrapped | at the end of the new `[url](url)` |
| On a line with no conversion | exactly where it was |

The third row is the case worth having: a cursor mid-URL has no meaningful home between the two
copies, and landing after the whole link is where the user's next keystroke belongs.

The task-body editor uses the same mapping; its `_save` closure calls `format_bare_urls` itself before
`set_task_body` and returns a `SaveResult` carrying the converted text and the conversions, so the
pane's existing re-sync path handles both editors identically.

---

## T3. The status line

FR-025. Composed into the existing message chain in `_save`, which already merges the missing-stamp
note, save warnings, and mirror warnings.

| Conversions | Message |
|---|---|
| 0 | nothing — no message is added, and no existing message is suppressed |
| 1 | `formatted 1 link` |
| n > 1 | `formatted {n} links` |

Silence at zero is the requirement, not an optimisation: a message on every save is a message nobody
reads, and the constitution's confirmation rule exists because a notice that fires when nothing
happened trains the user to ignore it.

The note never replaces a warning. Where a save both converts and produces a warning, the existing
`"; ".join(...)` chain carries both, warning styling wins, and the conversion note is one more clause.

---

## T4. What is deliberately absent

| Not added | Why |
|---|---|
| A confirmation before converting | It would fire overwhelmingly on saves that convert nothing — the reflex-dismissal failure Principle V names — and would spend the twenty-second budget the principle protects. The change is shown after the fact instead (T2). |
| A binding to convert on demand | The save *is* the gesture. A second key for the same effect is a second thing to learn. |
| A binding to un-convert | FR-028. The editor's own undo covers it, and the change is visible immediately. |
| A setting | FR-027, argued in spec.md §"Why there is no setting". |
| A footer change | No new binding, so `EDIT_HELP` is unchanged and `tests/unit/test_footer_bindings.py` needs no update. |
| Any preview-pane change | A bare URL is already clickable there via markdown-it's linkify and `app.open_url`; a converted one resolves the same way. Verified — `resolve_href` returns `None` for a scheme-carrying href and the handler falls through unchanged (FR-022). |

---

## T5. Reserved keys

Untouched. `ctrl+c` is not bound, inspected, or relied on anywhere in this feature. `ctrl+q` keeps its
current behaviour, including issue #64's dirty-buffer confirmation. `ctrl+s` gains no new binding — it
already saves, and saving is where this happens.
