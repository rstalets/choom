# Contract: the task surface in the TUI

Extends [001's TUI contract](../../001-meeting-notes/contracts/tui.md) and the collection menu
feature 002 added. The command bar, status bar, and reserved-key rules are unchanged and still
binding.

**Revised 2026-07-28** after 002 merged: tasks are a third collection inside the existing
`ListScreen`, not a second screen. See [research.md R9](../research.md#r9-the-task-surface-in-the-tui).

---

## Layout

No new screen and no new pane. The existing three-pane `ListScreen` gains a third menu entry.

```
┌────────┬───────────────────────────────────┬───────────────────┐
│Meetings│ [ ] 2026-07-27 followup send the… │                   │
│Notes   │ [x] 2026-07-26          book the… │   (empty on the   │
│Tasks ◀ │ [ ] 2026-07-28 admin    file the… │    tasks          │
│        │                                   │    collection)    │
├────────┴───────────────────────────────────┴───────────────────┤
│ command bar (hidden until '/')                                 │
│ [tasks]  / filter or command  ↑↓/jk move  h/l pane  space toggle  a all  ctrl+q quit │
└────────────────────────────────────────────────────────────────┘
```

- `COLLECTIONS` becomes `("meetings", "notes", "tasks")`; the menu label is `Tasks`.
- Row format: checkbox, created date (blank when unknown), type, text, tags. Completed rows are
  struck through and hidden until `a`.
- **The preview pane stays visible and empty on tasks.** It is not collapsed and its width does not
  change, so the layout never reflows when the user crosses collections. The pane is reserved for a
  future feature; this one puts nothing in it.
- Empty state: `No tasks yet. Press / then 'task <description>' to create one.`

---

## States

Unchanged from 002 — collections switch inside one screen, and there is no task preview or edit
state:

```
meetings ⇄ notes ⇄ tasks        (menu pane, or /meetings /notes /tasks)
document row --enter--> preview screen --esc--> list
task row     --enter--> nothing
```

`enter` on a task row does nothing this feature and MUST NOT be advertised in the footer.

---

## Key bindings

Existing `ListScreen` bindings (`j`, `k`, `h`, `l`, arrows, `/`) are unchanged and work on every
collection. Two are added:

| Key | Action | Active |
|---|---|---|
| `space` | Toggle the selected task complete / open | tasks collection only |
| `a` | Show completed tasks as well; press again to hide | tasks collection only |

Both are bound once at screen level and **no-op when `app.active != "tasks"`** — a binding that
exists and does nothing is simpler than a binding set that changes shape under the user. The status
bar text is per-collection, so the footer advertises `space` and `a` only where they fire, which is
what Principle V's "every active binding is visible" requires in both directions.

Verified against Textual and the merged code: `ListView` binds only `enter`, `up`, and `down`, so
`space` and `a` are free, and an unmatched key walks from the focused widget up the DOM. No
`priority=True`, nothing rebound.

**Reserved — never bind**: `ctrl+c` (Textual), `ctrl+q` (quit), `ctrl+s` (XOFF). No `cmd` binding is
ever promised — macOS terminals intercept it.

---

## Command bar grammar — additions

`VERBS` gains `task` and `tasks`, following the shape 002 established for `note` / `notes`.

| Input | Resolves to | Effect |
|---|---|---|
| `task <description>` | command | Create an untyped task; switch to the tasks collection |
| `task.<type> <description>` | command | Create a task of that type |
| `task.followup send the report #procurement` | command | Type `followup`, tag `procurement`, text `send the report` |
| `task` (no description) | command | **Error in the bar** — unlike `note`, a bare `task` has no idempotent meaning. Posts `BarError("task needs a description")` |
| `tasks` | command | `CollectionRequested("tasks")` — switch collection |
| `meetings` / `notes` | command | Switch away, unchanged |
| ` task` (leading space) | filter | Literal filter for the word "task" |

`task` posts `CreateRequested("task", description, type)`, extending the `kind` field 002 added.
Inline `#tag` tokens are parsed anywhere in the description and stripped from the text, as for every
other create command.

---

## Behaviour rules

1. **Creating a task switches to the tasks collection** and leaves the user there with the new task
   visible and selected — not in a preview, not in an editor (FR-044). This mirrors how 002 lands the
   user on the collection they just created into, and differs from `/meeting` and `/note` only in
   that there is no preview screen to push.
2. **`space` writes immediately.** No confirmation: the same key reverses it, so there is nothing to
   lose (Principle V).
3. **A toggle re-reads only `tasks.md`** and rebuilds the visible rows in place, keeping the
   selection on the task that was toggled.
4. **The live filter operates on the in-memory list**, matching text, type, and tags
   case-insensitively, and applies per collection exactly as it does for documents.
5. **`a` is a view toggle, not a filter.** It composes with the live filter rather than clearing it,
   and its state persists while the user crosses collections and comes back.
6. **Warnings from a malformed `tasks.md` surface in the status bar** as a count, using the
   `warnings[collection]` mechanism 002 already established. The tasks themselves still list.
7. **A failed write shows the error in the status bar** and leaves the row unchanged — the interface
   never shows a checkbox state that is not on disk.
8. **The preview pane is cleared, not hidden, on entering the tasks collection**, and repopulated on
   returning to meetings or notes.

---

## App state

`app.documents` and `app.warnings` are dicts keyed by collection, but a `Task` is not a `Document` —
different fields, no path. The app therefore carries tasks alongside rather than inside:

```python
self.tasks: list[Task]              # loaded on mount via load_tasks
self.visible_tasks: list[Task]      # after filter + show_done
self.show_done: bool = False        # toggled by `a`
self.warnings["tasks"]: list[ScanWarning]
```

`ListScreen.refresh_rows` branches once on `app.active` to choose its row type. That single
conditional is the whole cost of not having a second screen.

---

## Testing

Headless via `App.run_test()` / `Pilot`, extending 002's collection-menu tests:

- The menu lists three collections; selecting `Tasks` shows tasks.
- `space` on a row flips the checkbox in `tasks.md` and in the row, with the metadata comment
  unchanged.
- `space` and `a` on the meetings and notes collections do nothing and raise nothing.
- `a` reveals completed rows; pressing it again hides them; the state survives a round trip through
  another collection.
- The preview pane is empty on tasks and repopulates on returning to meetings.
- Creating through the bar switches to tasks with the new row selected.
- The footer contains `space` and `a` on tasks, and does not on meetings or notes.
- A workspace whose `tasks.md` has a broken comment still lists its other tasks, with a warning count
  in the status bar.
