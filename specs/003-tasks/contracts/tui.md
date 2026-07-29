# Contract: the task surface in the TUI

Extends [001's TUI contract](../../001-meeting-notes/contracts/tui.md). The command bar, status bar,
and reserved-key rules are unchanged and still binding.

---

## Layout

`TaskListScreen` is a full-width list with the shared bottom bar. **No preview pane** — a task is one
line, and there is nothing to preview ([research.md R9](../research.md#r9-the-task-surface-in-the-tui)).

```
┌──────────────────────────────────────────────────────────┐
│ [ ] 2026-07-27  followup  send the vendor comparison  pr… │
│ [x] 2026-07-26            book the room                   │  ← struck through when shown
│ [ ] 2026-07-28  admin     file the expense report         │
├──────────────────────────────────────────────────────────┤
│ command bar (hidden until '/')                           │
│ / filter or command  ↑↓/jk move  space toggle  a all  …  │
└──────────────────────────────────────────────────────────┘
```

Row format: checkbox, created date (or blank when unknown), type, text, tags. Completed rows are
rendered struck through and are hidden until `a` is pressed.

Empty state: `No tasks yet. Press / then 'task <description>' to create one.`

---

## States

Two surfaces, both list states, reached through the command bar:

```
meetings list  --/tasks-->  task list
task list      --/meetings-->  meetings list
```

There is no preview or edit state for tasks. `enter` on a task row does nothing this feature —
it must not be advertised in the footer.

---

## Key bindings — task list

| Key | Action |
|---|---|
| `↑` / `↓` / `j` / `k` | Move the selection |
| `space` | Toggle the selected task complete / open |
| `a` | Show completed tasks as well; press again to hide |
| `/` | Open the command bar (filter or command) |
| `ctrl+q` | Quit |

Verified against Textual's documentation: `ListView` binds only `enter`, `up`, and `down`, so
`space` and `a` are free, and an unmatched key walks from the focused widget up to the app. Screen
-level bindings suffice; no `priority=True`, nothing rebound.

**Reserved — never bind**: `ctrl+c` (Textual), `ctrl+q` (quit), `ctrl+s` (XOFF). No `cmd` binding is
ever promised — macOS terminals intercept it.

Every binding above appears in the footer while the task list is focused (`TASK_LIST_HELP`).

---

## Command bar grammar — additions

`VERBS` gains `task` and `tasks`. The existing resolution rule is unchanged: the token before any
`.` decides command versus filter, a leading space forces filter mode, and the footer shows the
resolved mode as the user types.

| Input | Resolves to | Effect |
|---|---|---|
| `task <description>` | command | Create an untyped task |
| `task.<type> <description>` | command | Create a task of that type |
| `task.followup send the report #procurement` | command | Type `followup`, tag `procurement`, text `send the report` |
| `tasks` | command | Show the task list |
| `meetings` | command | Back to the meetings list |
| `task things I owe people` | command, then create | The first token is the verb; the rest is the description |
| ` task` (leading space) | filter | Literal filter for the word "task" |

Inline `#tag` tokens are parsed anywhere in the description and stripped from the text, exactly as
for meetings.

---

## Behaviour rules

1. **Creating a task leaves the user on the task list** with the new task visible and selected —
   not in a preview, not in an editor (FR-044). This differs from `/meeting`, which lands in
   preview, because a task has no preview to land in.
2. **`space` writes immediately.** No confirmation: the same key reverses it, so there is nothing to
   lose (Principle V).
3. **A toggle re-reads only `tasks.md`** and rebuilds the visible rows in place, keeping the
   selection on the task that was toggled.
4. **The live filter operates on the in-memory list**, matching text, type, and tags
   case-insensitively. No disk access per keystroke.
5. **`a` is a view toggle, not a filter.** It composes with the live filter rather than clearing it.
6. **Warnings from a malformed `tasks.md` surface in the status bar** as a count, in the same shape
   the meetings list already uses for scan warnings. The tasks themselves still list.
7. **A failed write shows the error in the status bar** and leaves the row unchanged — the interface
   never shows a checkbox state that is not on disk.

---

## Testing

Headless via `App.run_test()` / `Pilot`, as in feature 001:

- `/tasks` reaches the task list; `/meetings` returns.
- `space` on a row flips the checkbox in `tasks.md` and in the row, and the metadata comment is
  unchanged.
- `a` reveals completed rows; pressing it again hides them.
- Creating through the bar lands on the task list with the new row selected.
- The footer text contains every binding in the table above.
- A workspace whose `tasks.md` has a broken comment still lists its other tasks, with a warning
  count in the status bar.
