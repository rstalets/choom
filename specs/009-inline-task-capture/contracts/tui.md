# Contract: TUI surface

**Feature**: `009-inline-task-capture`

No new key binding, no new screen, no new confirmation. The gesture is typed, and it appears in the
editor's command list the same way `/ai` and `/link` do (Principle V).

---

## The `/task` gesture

### Grammar

```
/task <description>
/task.<type> <description>
```

`#tag` tokens anywhere in the description are extracted exactly as they are by the command bar and the CLI.
The line must be the entire command (`parse_line`'s existing rule, FR-003) — `Did you know you can type
/task here?` is prose.

Promotion is the same grammar: the user puts the cursor at the start of a line that already reads
`chase the security review with Priya`, types `/task.followup ` in front of it, and presses enter.
Everything after the command token is the description. No second rule, and a trailing `/task` stays prose.

### Sequence

Enter is intercepted by `EditorTextArea` and dispatched by `EditScreen`, exactly as `/ai` is today.

1. **Validate.** Empty description → status message, line untouched, nothing saved, nothing written.
   A `.type` suffix alone is not a description.
2. **Save** the document in its pre-command state, through the existing `_save()`. Failure → its message is
   already reported; abort with the line untouched.
3. **Capture** via `core.mirrors.capture_task`. Failure → status message naming the rejected token or the
   unwritable file; line untouched.
4. **Replace** the typed line with the returned mirror line, using the same
   `TextArea.replace(..., maintain_selection_offset=False)` call `/ai` uses — so it is one undo step
   (FR-014).
5. **Place the cursor** at the end of the inserted line. Focus never leaves the editor.
6. **Record the baseline** for the new task as `False`, so the mirror the user just received is not
   mistaken at save time for a box they ticked.

No screen is pushed or popped, no collection changes, the scroll position is unchanged (FR-006). This is
the visible difference from the command bar's `/task`, which navigates to the tasks collection.

### Errors

Every failure renders in the status bar via the existing `_render_status`, leaves the typed line exactly as
entered, and returns control to the editor (FR-009):

| Condition | Message |
|---|---|
| no description | `/task needs a description` |
| suffix only | `/task needs a description` |
| rejected type token | the `UsageError` from `add_task`, naming the token |
| rejected tag token | likewise |
| `tasks.md` unwritable | the OS message, naming the file |
| document save failed | already reported by `_save()`; capture does not proceed |

---

## Reconcile on open

Three call sites, all calling `core.mirrors.reconcile_on_open`:

| Site | When |
|---|---|
| `edit_screen.open_editor` | before the buffer is handed to `EditScreen` |
| `edit_screen.open_task_editor` | same, for a task's own body |
| `preview_screen.PreviewScreen` | on mount and on resume, before rendering |

The preview is included deliberately: FR-026 and the spec's US6 scenario 6 require that what is displayed
is never a stale checkbox, and the preview is the most common way a document is looked at. Excluding it
would show something the editing path would immediately correct.

**Cost**: a document with no mirrors costs one scan of a string already in memory and no file read at all
(SC-007). `tasks.md` is read only when a mirror is present.

**Write**: only if a splice changed something, and never stamping `updated`. The corrected text is what the
editor is seeded with, so the buffer and the file agree from the first keystroke.

**Baseline**: `EditScreen` records, at this moment, the state of every mirror in the reconciled text. That
mapping is the `baseline` argument at save time.

---

## Reconcile on save

`EditScreen._save()` gains one step, before `save_buffer`:

1. `reconcile_on_save(workspace, buffer_text, source=path, baseline=self._mirror_baseline)`.
2. If the returned text differs, the buffer is updated to it — the user sees corrections land.
3. `save_buffer(...)` writes as it does today, stamping `updated` (this *is* a user edit) and healing
   stale links (008's behaviour).
4. The baseline is refreshed from the text just saved.
5. Warnings — conflicts, ambiguity, dead mirrors — render in the status bar. None of them blocks the save.

Ordering matters: reconciliation runs on the buffer, and `save_buffer` writes the result. `save_buffer`
does not grow a baseline argument
([research R5](../research.md#r5-the-two-write-paths-and-why-save_buffer-is-not-overloaded)).

---

## Propagation from the tasks list

`space` in the tasks list is unchanged as a gesture. `app.toggle_task_and_track` gains one step after
`set_task_state` succeeds:

```
set_task_state(...)                       # tasks.md, exactly as today
propagate_to_documents(workspace, task, skip=<paths open with unsaved changes>)
```

- `tasks.md` is written first and is never reversed by a document failure (FR-032).
- A document open with unsaved changes is skipped and reconciled at the user's next save (FR-033); the
  screen stack is what knows which those are, which is why the adapter supplies `skip` rather than core
  discovering it.
- Warnings surface through `last_task_error`'s existing channel, so no new reporting surface is added.
- A task with no links does no document work at all (FR-034) — the toggle costs exactly what it costs today.

---

## Discoverability

`/task` appears wherever the editor's commands are listed, because the help pane reads `EDITOR_COMMANDS`
(FR-010). Registering the command is the whole of that change; no help text is written by hand in a second
place.

The footer is unchanged. There is no new binding to show, and adding a hint for a typed command would
violate the footer's contract that it lists bindings.

---

## What the user never sees

- No dialog. Nothing here can discard data, so a confirmation would be the kind that teaches people to
  dismiss reflexively (Principle V).
- No spinner or lock. Capture is a file append; unlike `/ai`, there is nothing to wait for and the editor is
  never made read-only.
- No navigation. The whole point is that the note-taker keeps their place.
