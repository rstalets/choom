# Contract: CLI and TUI Surface

**Feature**: `019-completed-tasks-partition`

The compatibility surface. Principle II makes renaming or removing a `--json` key or an exit code
breaking; this feature does neither.

---

## 1. Per-command behaviour

| Command | Behaviour change | Read scope |
|---|---|---|
| `choom task add` | **None.** A new task is never complete | writes `tasks.md` |
| `choom task list` | **None.** Same rows, same order, and still **exactly one file opened** whatever the store holds (FR-018, SC-003) | `tasks.md` |
| `choom task list --done` | Union of the store and any `[x]` still in `tasks.md`, as one list. Row shape unchanged | whole store |
| `choom task list --all` | Whole store. Row shape unchanged | whole store |
| `choom task show <id>` | Finds a completed record wherever it lives | whole store |
| `choom task done <id>` | Moves the record into the day file for today. Exit code, mirror propagation, and warning behaviour unchanged | whole store |
| `choom task undone <id>` | Moves it back to `tasks.md` | whole store |
| `choom task delete <id>` | Deletes from whichever file holds the record | whole store |
| `choom links check` / `heal` | Also cover the store (FR-028). Report **no** new staleness from a completion (FR-026) | + store files |
| `choom links <id>` | Also scans the store for task-field links | + store files |
| `choom task tidy` *(P3, droppable)* | **New.** Explicit one-shot sweep. Non-interactive, no prompt, reports moved/left counts. CLI-only, on `links heal`'s precedent (research R11) | `tasks.md` → store |

Every other command is untouched.

## 2. `--json` — additive only

**Task record** (`task list --json`, `task show --json`, `task add --json`):

| Key | Status |
|---|---|
| `id`, `text`, `done`, `type`, `tags`, `links`, `created`, `line`, `body` | **Unchanged** — same name, same type, same meaning |
| `completed` | **Added.** ISO date string or `null` |
| `file` | **Added.** Workspace-relative POSIX path of the file holding the record — `"tasks.md"` or `"tasks/done/2026/08/2026-08-02-done.md"`. Required because `line` is a line number and is ambiguous without it |

**`task done` / `task undone` object**:

| Key | Status |
|---|---|
| `id`, `done`, `links`, `documents_updated`, `warnings` | **Unchanged** |
| `file` | **Added.** Where the record now lives |

Nothing is renamed, retyped, or removed. Paths use `/` on every platform, as the existing
`documents_updated` already does.

**Pinned test constants that must be edited** (a reviewed one-line change each, not a loosening):

- `tests/contract/test_json_schema.py:9` — `EXPECTED_TASK_KEYS` gains `completed`, `file`
- `tests/contract/test_task_done_json.py` — `EXPECTED_KEYS` gains `file`

## 3. Exit codes

Unchanged: `0` success, `1` not found, `2` usage error, `3` workspace error. No code added, renamed,
or removed.

| Situation | Code |
|---|---|
| Move succeeded | `0` |
| No record carries the id | `1` |
| The id is carried twice (including after a partial move) | `2` |
| Destination write failed — nothing moved | `3` |
| Source write failed — record now in both files, both named | `3` |

Stream separation is unchanged: data to stdout, warnings and errors to stderr. Nothing prompts,
blocks, opens an editor, or decorates a non-TTY stream.

## 4. TUI

| Element | Change |
|---|---|
| Todo / Done categories | **None** visible. Space still toggles; the row still leaves Todo and appears in Done |
| Bindings and footer | **None.** No key added, removed, or rebound |
| `ctrl+d` (list delete) | Deletes a completed record from the store. Same confirmation, same wording |
| `ctrl+t` (editor task delete) | Now reaches a completed record instead of silently taking the `line_only` branch — **bug 1's fix**, inside an existing confirmation, not a new one |
| Reconcile on open | A mirror of a completed task is ticked instead of warned dead — **bug 2's fix** |
| Done view refresh | A stat-fingerprint precheck skips the parse when nothing changed (plan.md, Complexity Tracking) |
| Screens, dialogs | **None added** |

## 5. Error messages

Principle V requires an error to name what went wrong and what to do.

| Condition | Message shape |
|---|---|
| Id carried twice | `id 'task_a1b2' appears at tasks.md:12 and tasks/done/2026/08/2026-08-02-done.md:3; delete one of them` |
| Source write failed after the destination succeeded | names both files, states the record now exists in both, and says which one to remove |
| Unreadable day file | one warning naming the file; the rest of the store still lists |
