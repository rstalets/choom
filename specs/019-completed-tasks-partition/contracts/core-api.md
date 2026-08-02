# Contract: Core API

**Feature**: `019-completed-tasks-partition`

Every signature below is callable with a `Workspace` and plain data — no terminal, no TTY, no event
loop (Principle I). C-numbers are referenced by `tasks.md` and by tests.

---

## 1. New module: `choom.core.task_store`

### C1 — `done_file_for(workspace: Workspace, on: date) -> Path`

The day file for a completion date. Pure: opens nothing, creates nothing, never raises.

```text
done_file_for(ws, date(2026, 8, 2))
  == ws.root / "tasks" / "done" / "2026" / "08" / "2026-08-02-done.md"
```

### C2 — `iter_done_files(workspace: Workspace) -> list[Path]`

Every `*.md` under `tasks/done/`, newest day first, by lexical sort of the path descending. Walks
the tree on every call; there is no manifest. Returns `[]` when the root does not exist. Never
raises — an unreadable directory yields the files it could enumerate.

### C3 — `load_done_tasks(workspace) -> tuple[list[Task], list[ScanWarning]]`

Parses every file from C2 with `tasks.parse_tasks`. Each returned `Task` carries `source` set to the
file it came from and `completed` from its own field.

- An unreadable or unparseable file produces one warning naming it and does not stop the rest.
- Missing ids are backfilled in place, best-effort: a failed write yields a warning and the read
  still succeeds (research R13).
- Never raises.

### C4 — `load_task_store(workspace) -> tuple[list[Task], list[ScanWarning]]`

`load_tasks` then `load_done_tasks`, concatenated in that order, warnings merged. Never raises.

### C5 — `move_record(workspace, task_id, *, done, now=None) -> Task`

The move, both directions. Returns the record as it now stands, with `source` and `completed`
updated.

- **Locates by id across the whole store**, `tasks.md` first. Re-reads and re-parses immediately
  before writing; never trusts a cached line number.
- **No-op**: if the record's `done` already equals `done`, returns it and **writes nothing** — in
  either file, whichever file it is in. This preserves `set_task_state`'s existing no-op contract.
- **Writes the destination first, the source second** (data-model §4). Both through
  `write_text_atomic`.
- **Splices, never re-renders**: the state character and the `completed:` field are the only edits;
  the body span is copied byte-for-byte.
- A record already sitting in the "wrong" file for its state (a `[x]` in `tasks.md`, a `[ ]` in a day
  file) is **not** relocated by a no-op. Only a real transition moves anything.

**Raises**:

| Exception | When |
|---|---|
| `NotFoundError` | No record in either half of the store carries `task_id` |
| `UsageError` | More than one does. Message names every `<file>:<line>` (research R7) |
| `WorkspaceError` | Either write failed. If the **destination** failed, the source is byte-identical. If the **source** failed, the message states that the record now exists in both files and names both |

### C6 — `store_fingerprint(workspace) -> tuple[tuple[str, int, int], ...]`

`(posix_path, st_mtime_ns, st_size)` per day file, sorted. One `os.scandir` walk; opens no file.
Never raises — an unreadable entry is omitted. Held in memory by the caller only (plan.md,
Complexity Tracking).

**A matching fingerprint is not proof the store is unchanged.** Equality can occur across a real edit
when the filesystem's timestamp granularity (1 s on HFS+/ext3, 2 s on FAT/exFAT) swallows the write
and the edit is size-preserving — a `- [x]` → `- [ ]` toggle changes no byte count. A miss is
therefore **permanent**, not transient: every later tick recomputes the same tuple. Callers MUST
bound it:

> `ListScreen` skips the Done-view parse when the fingerprint matches **and** fewer than 30 s of
> displayed Done view have elapsed since the last full parse. The 30 s clock is injected, never read
> from the wall clock in a test (Principle VI).

If a measured full store parse exceeds ~100 ms, the response is to month-scope the Done view, **not**
to lengthen the interval — see plan.md's Complexity Tracking for the arithmetic.

### C7 — `tidy_completed(workspace, *, now=None) -> TidySummary` *(P3, droppable)*

Moves every parseable completed record out of `tasks.md` into the store, one at a time under C5's
ordering. Never prompts. A record it cannot read is left and counted in `left`. A failure partway
through leaves earlier moves done and is reported. Never runs implicitly.

---

## 2. Changed signatures in existing modules

| Function | Change | Compatibility |
|---|---|---|
| `tasks.load_tasks` | **None.** `tasks.md` only, same cost, same warnings | — |
| `tasks.set_task_state` | Body delegates to `move_record`. Signature, name, and no-op contract unchanged | Callers unaffected: `cli.main`, `tui.list_screen`, `mirrors._write_task_state` |
| `tasks.get_task` | Reads `load_task_store` | Additive — finds strictly more |
| `tasks.delete_task` | Locates across the store; removes from whichever file holds the record. Returns the record, whose `source` names that file | Additive |
| `tasks.render_task_line` | Optional `completed: date \| None = None`, emitted last, omitted when `None` | Keyword-only with a default |
| `tasks.parse_tasks` | `"completed"` in `_RECOGNIZED_KEYS`, validated as `created` is | A comment carrying it now classifies `task` instead of `malformed` — strictly more permissive |
| `links.resolve_id` | Task pool escalates: `tasks.md`, then the store. **`LinkTarget.path` is always `workspace.tasks_file`** for a task, whichever file holds the record (FR-024) | Signature unchanged |
| `links._iter_target_paths` | Appends the store's files | Internal |
| `links._task_field_reports`, `links._all_task_field_links` | Read `load_task_store` | Internal |
| `links.link_candidates` | **Unchanged** — `load_tasks`, open tasks only (research R4) | — |
| `mirrors._load_tasks_or_warning` | Escalates per C8 | Internal |
| `mirrors.plan_mirror_deletion` | Resolves across the store; `unreadable_tasks` scoped per C9 | Signature and outcome set unchanged |
| `tasks._format_line_numbers` | Formats `(path, line)` pairs; `mirrors.py`'s duplicate is deleted and imports this one | Internal |

### C8 — Reconcile escalation

`reconcile_on_open` and `reconcile_on_save` read `tasks.md` first. They read the done store **at most
once per call, and only when at least one mirror in the document names an id `tasks.md` does not
carry.**

- A document whose mirrors all name open tasks costs **exactly one file read** — spec 008's SC-008,
  preserved (SC-004).
- A mirror of a completed task is corrected to `[x]`, **not** reported dead. This is bug 2's fix and
  carries a named regression test.
- A mirror whose id is in neither half is still dead: left byte-identical, warned, unchanged from
  today.

### C9 — `plan_mirror_deletion` outcomes

Reads with `parse_tasks`, never `load_tasks` — the plan step still writes nothing (017 FR-014).

| Outcome | Meaning now |
|---|---|
| `self_referential` | Unchanged; decided before any file is opened |
| `deletable` | Exactly one record carries the id, **in either half of the store**. Bug 1's fix |
| `ambiguous_id` | More than one does, across files. Message names every `<file>:<line>` |
| `unreadable_tasks` | The id resolves to nothing **and** a file actually read during this resolution holds an unreadable line. Message names that `<file>:<line>` |
| `line_only` | The id resolves to nothing anywhere in the store, and every file read parsed cleanly |

Blocking reason set unchanged: `{task_unterminated_comment, task_malformed_comment}`.
`task_invalid_value` still yields a findable `Task` and still never blocks (017 FR-022).

---

## 3. What core does not do

- Does not format, colourise, paginate, or print.
- Does not construct a store path in any adapter — C1 is the only place one is built.
- Does not write any file outside `tasks.md` and the store, except the mirror splices
  `propagate_to_documents` already performs for documents the task's own `links:` field names.
- Does not persist `store_fingerprint`, `TidySummary`, or any parsed record between calls.
