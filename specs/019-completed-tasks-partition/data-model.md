# Phase 1 Data Model: Completed Tasks Leave the Open List

**Feature**: `019-completed-tasks-partition` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Nothing here is a new persistent structure. The only thing this feature adds to disk is a second
kind of file holding lines in a format that already exists.

---

## 1. The task store (on disk)

```text
<workspace>/
├── tasks.md                                    # the open list
└── tasks/
    └── done/
        └── 2026/
            └── 08/
                └── 2026-08-02-done.md          # records completed on 2 August 2026
```

| Property | Value |
|---|---|
| Collection root | `tasks/done/` |
| Partition | `YYYY/MM/`, from the record's `completed` date — date is the only axis |
| File name | `YYYY-MM-DD-done.md` |
| Frontmatter | **None.** A day file is a container, not a record; it has no id, no title, no `created` |
| Contents | Task lines in `tasks.md`'s exact format, so `parse_tasks` reads it unmodified |
| Created | On demand, by `write_text_atomic`'s existing `parent.mkdir(parents=True, exist_ok=True)` |
| Pruned | Never. An empty day file left by a reopened record is legal and is left alone |

**Where a record's file comes from.** `done_file_for(workspace, on)` is a pure function of a date:
`workspace.root / "tasks" / "done" / f"{on:%Y}" / f"{on:%m}" / f"{on:%Y-%m-%d}-done.md"`. It opens
nothing and never consults the filesystem.

**Where a record's date comes from.** Its own `completed:` field — never its path. A record found in
the file for 12 June whose field says 3 May lists as completed on 3 May, and is not relocated
(FR-005). This is the same rule that already governs a meeting note filed under the wrong month.

---

## 2. The task line

Unchanged grammar, one new field.

```markdown
- [x] call Terry about the renewal <!-- id:task_a1b2 type:followup tags:vendor links:meeting_20260728_a1b2c3d4 created:2026-07-28 completed:2026-08-02 -->
    the contract auto-renews on the 15th
```

| Field | Change |
|---|---|
| `id`, `type`, `tags`, `links`, `created` | None |
| `completed` | **New.** ISO `YYYY-MM-DD`. Last in field order, after `created` |

**Parser rules** (`tasks.py`):

- `"completed"` joins `_RECOGNIZED_KEYS`. A comment carrying it is classified `task`, not `malformed`.
- The value is validated exactly as `created` is: `_ISO_DATE` then `date.fromisoformat`. A bad value
  emits `ScanWarning(reason="task_invalid_value")` **and the record is still returned** — the
  existing pattern (`tasks.py:283-298`), not a new one.
- Presence is not tied to the checkbox. A `[ ]` record carrying `completed:` is read as open with a
  stale field; a `[x]` record with no `completed:` is read as complete with no completion date. Both
  occur in real workspaces — the first from a hand-edit, the second from every task completed before
  this feature shipped — and neither is an error.

**Renderer rules**: `render_task_line` gains an optional `completed: date | None = None`, emitted
last and omitted when `None`, matching how every other optional field already behaves. It is used for
new lines only; **a move never calls it** (see §4).

---

## 3. `Task` (in-memory)

`src/choom/core/models.py`, frozen slots dataclass. Two fields appended, both with defaults, so every
existing construction site is unaffected.

| Field | Type | Meaning |
|---|---|---|
| `id` … `body` | unchanged | unchanged |
| `completed` | `date \| None = None` | From the record's own `completed:` field. `None` for every open record and for a completed record that predates the field |
| `source` | `Path \| None = None` | The file the record was read from. Populated by every loader; `None` only for a `Task` built by a caller that never read one |

`source` exists because `line` is a line number and stopped being self-describing the moment records
could live in two files. It is what `--json`'s `file` key serialises, what the duplicate-id message
names, and what `move_record` reads to know which direction it is moving.

**New**: `TidySummary` (frozen dataclass) for the P3 sweep — `moved: int`, `left: int`,
`warnings: tuple[ScanWarning, ...]`. Lives for the length of one command; never persisted.

---

## 4. The move

The unit that moves is a **record**: one checkbox line plus its body span as `_body_span` computes it
(`tasks.py:115`), unmodified.

**Two splices, applied to the checkbox line only. Body lines are copied byte-for-byte.**

| Splice | Where | Rule |
|---|---|---|
| State | `_TASK_LINE.span("state")` | One character: `" "` ↔ `"x"`. The identical edit `set_task_state` performs today (`tasks.py:614`) |
| `completed:` | Inside the last `<!-- … -->` on the line | **Insert**: inner body `B` becomes `B.rstrip() + " completed:<ISO>" + <B's original trailing whitespace, or " ">`. **Remove**: drop the first `completed:…` token and the single space before it |

Everything else about the line — the indent, the marker, the description, the other fields, their
spacing, the line's own terminator — is carried through untouched. Nothing is re-rendered
(research R2), so a hand-edited comment survives a completion.

**Unreachable by construction**: a line with no comment, or a bare/malformed one, yields `id=None` or
no `Task` at all, so it can never be matched by id and the splice can never run against a line with
nothing to splice into.

### Write sequence

```text
complete:                                   reopen:
  1. read + parse tasks.md                    1. read + parse the store; locate by id
  2. locate by id; compute the moved block    2. compute the moved block
  3. WRITE tasks/done/…-done.md   ← first     3. WRITE tasks.md (append)      ← first
  4. WRITE tasks.md (block removed)           4. WRITE the day file (block removed)
```

Both writes go through `write_text_atomic`. There is no transaction spanning them, by design.

### Failure states

| Failure | Result | Detected by |
|---|---|---|
| Step 3 fails | Source byte-identical; record still in its original state | `WorkspaceError`, exit 3 |
| Step 4 fails | **Record exists in both files.** No line lost | The existing duplicate-id path: `resolve_id` → `link_ambiguous`; `get_task`/`set_task_state`/`delete_task` → `UsageError`; `plan_mirror_deletion` → `ambiguous_id` |
| Killed between 3 and 4 | Identical to the row above | Same |

Recovery is by hand, and the message says so, naming both files. That is the whole recovery story
(research R3) — no rollback, no retry, no repair pass.

---

## 5. State transitions

```text
                    task done / space / tick a mirror + save
   ┌──────────────┐ ─────────────────────────────────────────▶ ┌───────────────────┐
   │  tasks.md    │                                            │  tasks/done/…     │
   │  - [ ] …     │ ◀───────────────────────────────────────── │  - [x] … completed│
   └──────────────┘   task undone / space / untick + save      └───────────────────┘
          │                                                              │
          │ task delete / ctrl+d / ctrl+t                                │
          ▼                                                              ▼
                                   (gone)
```

Two states that exist and are **not** transitions choom performs:

- `- [x]` **in `tasks.md`** — every task completed before this feature, and any the user ticks by
  hand in the file. Lists in every done view; never moved except by a real reopen→complete cycle or
  the explicit sweep (FR-037, FR-039).
- `- [ ]` **in a day file** — a hand-edit. Lists as open; never moved back (FR-005). choom does not
  relocate a record to agree with its own filing.

---

## 6. Reads

| Function | Scope | Cost |
|---|---|---|
| `load_tasks(workspace)` | `tasks.md` | One file. **Unchanged** |
| `load_done_tasks(workspace)` | the store | One `scandir` walk + one parse per day file |
| `load_task_store(workspace)` | both, `tasks.md` first | The sum |

Ordering within a result: `tasks.md`'s records first in file order, then the store's files in
reverse chronological order (newest day first), records in file order within each. `filter_tasks`
then applies its existing sort, so no caller sees a change in ordering rules.

An unreadable or unparseable day file yields one `ScanWarning` naming it and does not stop the rest
(FR-022). Id backfill applies inside the store on the same best-effort terms it uses for `tasks.md`
(research R13).

---

## 7. What is *not* stored

- No index, manifest, or list-of-files. `iter_done_files` walks the tree every time it is asked.
- No back-reference from a record to the documents mirroring it beyond the `links:` field that
  already exists.
- No cache of parsed records between calls. The one thing held between refresh ticks is
  `store_fingerprint`'s tuple of `(path, mtime_ns, size)` — no task data, no content, never written
  to disk, discarded with the screen (plan.md, Complexity Tracking).
