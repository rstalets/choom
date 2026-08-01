# Phase 1 Data Model: Inline Task Capture

**Feature**: `009-inline-task-capture` | **Date**: 2026-07-31

Nothing here is persisted beyond what is already on disk. The workspace's state remains exactly two kinds
of markdown file: `tasks.md`, and documents. Every structure below is either a view over bytes that are
already there, or a value that lives for the length of one call or one screen.

---

## On disk

### The task line (unchanged by this feature)

`008-document-links` gives the task metadata comment a `links` field. This feature writes into it and adds
nothing:

```
- [ ] call Terry about the renewal <!-- id:task_a1b2 type:followup tags:procurement links:meeting_20260728_9f3c1a04 created:2026-07-30 -->
```

Field order is `id`, `type`, `tags`, `links`, `created`; empty fields are omitted. A task captured outside
any document carries no `links` field and its line is identical in shape to one written today (FR-019).

### The mirror (new, but not a new syntax)

A line in a document that is both a markdown checklist item and a link to a task:

```markdown
- [ ] [call Terry about the renewal](../../../tasks.md#task_a1b2)
```

It is an ordinary CommonMark task-list item containing an ordinary CommonMark inline link. No HTML comment,
no metadata, no marker of any kind that says "endpaper wrote this" — the `#task_a1b2` fragment is the whole
identity, and it is a fragment the link primitive already defines.

**Recognition rule** — a line is a mirror when both hold:

1. Its content matches the checklist prefix: optional leading whitespace, a `-`/`*`/`+` bullet, one space,
   `[`, exactly one state character (`` ` ` ``, `x`, or `X`), `]`, one space.
2. `find_links()` reports at least one link on that line whose destination fragment is a task id.

If several links on one line carry task-id fragments, the **first** is the mirror's task; the rest are
ordinary links. This is deterministic and it is the only case where a mirror could otherwise be ambiguous.

**What is not a mirror**, and why it matters:
- A prose line containing a task link — no checkbox, so no control surface, so nothing is ever written to it.
- A checklist item with no link, or a link with no fragment — an ordinary checkbox in someone's note, which
  this feature must never touch.
- Anything inside a fenced code block or an inline code span — excluded by `find_links()` before this
  feature sees it.
- A numbered list item (`1. [ ] …`) — `tasks.md` does not produce one and task-list rendering of it is
  inconsistent across viewers.

---

## In memory

### `Mirror`

One recognised mirror in one document. Frozen; produced by scanning, never constructed by a caller.

| Field | Type | Meaning |
|---|---|---|
| `task_id` | `str` | The id in the link's fragment. The identity. |
| `done` | `bool` | The state character between the brackets, as it currently reads. |
| `line` | `int` | 1-based line number, for warnings only — never for locating the line on a later pass. |
| `state_offset` | `int` | Character offset into the document text of the single state character. This is what makes every write a one-character splice. |
| `text` | `str` | The link's text, for messages. Never compared against the task's description. |

`state_offset` is the load-bearing field: it means applying a state is `text[:o] + "x" + text[o+1:]`, so no
line is re-rendered and no byte outside that one position can change.

### `MirrorResolution`

What was decided for one task during a save-side reconcile. Frozen.

| Field | Type | Meaning |
|---|---|---|
| `task_id` | `str` | |
| `outcome` | `"unchanged" \| "task_written" \| "mirror_corrected" \| "conflict" \| "ambiguous" \| "dead"` | |
| `done` | `bool \| None` | The state that won, where one did. |
| `message` | `str` | Populated for `conflict`, `ambiguous`, and `dead`; empty otherwise. |

### `MirrorReport`

The result of any reconcile or propagate call. Frozen.

| Field | Type | Meaning |
|---|---|---|
| `text` | `str` | The document text as it now stands. **Identical object** to the input when nothing changed, so a caller can test identity to decide whether to write at all (FR-030). |
| `resolutions` | `tuple[MirrorResolution, ...]` | One per task that had a mirror in the document. |
| `warnings` | `tuple[ScanWarning, ...]` | Reuses the existing warning channel, so dead and conflicting mirrors surface through the paths both adapters already print. |

### `MirrorBaseline`

`Mapping[str, bool]` — task id to the state its mirror had when the document was opened or last reconciled.
Held by `EditScreen` for the life of that screen; passed into core, never stored by core, never written
anywhere. This is what makes "since they last agreed" answerable without a second source of truth
(research R4).

A task id absent from the baseline means "this mirror was not present at open" — a mirror the user pasted
or typed during this session. It is treated as changed-by-the-user, because it was.

### `ParsedCommand` (extended)

`core/models.py`'s existing structure gains one field so the editor can carry a dotted type suffix:

| Field | Type | Meaning |
|---|---|---|
| `command` | `EditorCommand` | unchanged |
| `argument` | `str` | unchanged |
| `suffix` | `str` | New. The text after the first `.` in the verb — `"followup"` for `/task.followup`. Empty when there is no suffix. |

---

## State transitions

### A task's completion state

There is exactly one state, on the task line in `tasks.md`. Every mirror is a view of it. The transitions
and their triggers:

```
                     space in the tasks list / `task done` / `task undone`
              ┌──────────────────────────────────────────────────────────┐
              │                                                          ▼
        ┌──────────┐                                              ┌──────────┐
        │  open    │                                              │   done   │
        └──────────┘                                              └──────────┘
              ▲                                                          │
              └──────────────────────────────────────────────────────────┘
                     a mirror ticked in a document, at that document's save
```

Both triggers write the same one character on the same line, located by id. Nothing else can change a
task's state.

### Reconcile-on-open (tasks.md → document)

The user has not acted on this document, so the task is authoritative.

| Mirror reads | Task reads | Action |
|---|---|---|
| open | open | none |
| done | done | none |
| open | done | splice `x` into the mirror |
| done | open | splice ` ` into the mirror |
| any | *no such task* | leave byte-identical, warn `link_dead` |

The document is written only if at least one splice happened, and the write does not stamp `updated`.

### Reconcile-on-save (document → tasks.md, with corrections coming back)

The user has just acted on this document, so their edit is authoritative — but only for mirrors they
actually touched. Read `b` as the baseline state at open.

| Baseline | Mirror now | Task now | Outcome | Effect |
|---|---|---|---|---|
| `b` | `b` | `b` | `unchanged` | nothing written |
| `b` | `¬b` | `b` | `task_written` | write `tasks.md` (FR-022) |
| `b` | `b` | `¬b` | `mirror_corrected` | splice the mirror to match the task (FR-023) |
| `b` | `¬b` | `¬b` | `conflict` | write `tasks.md` from the mirror, warn (FR-024) |
| *absent* | any | any | `task_written` | a mirror that appeared this session is the user's edit |
| — | two mirrors, disagreeing | any | `ambiguous` | `tasks.md` untouched for that task, warn (FR-025) |
| — | any | *no such task* | `dead` | left byte-identical, warn (FR-028) |

Note the fourth row writes the same value the second row would; what differs is the warning. That is the
whole reason the baseline exists — without it, rows two and four are indistinguishable.

**Idempotence (FR-027)**: `tasks.md` is written from the mirror in one pass, and the corrected document
text is returned from the same pass. There is no second traversal and no callback, so a write to `tasks.md`
cannot re-trigger a write to the document that produced it.

### Propagation (tasks list → documents)

Triggered by `space`, `task done`, or `task undone`. For each id in the task's `links` field:

1. `resolve_id()` it. Unresolvable → warn, continue.
2. Read the document. Unreadable → warn, continue (FR-032).
3. Recognise mirrors for this task. None → nothing to do, no write.
4. Splice each to the task's new state. Already matching → no write.
5. Write without stamping `updated`, unless the document is open with unsaved changes — in which case
   nothing is written and the correction is applied through reconcile-on-save when the user saves (FR-033).

`tasks.md` is written **first**, in every case. No document failure can block, reverse, or delay it.

---

## Relationships

```
Task ──links:──▶ Document          (id only, in the metadata comment; written at capture)
Document ──mirror──▶ Task          (markdown link with an #id fragment; the checkbox)
```

The two are reciprocal by convention, not by enforcement. Either can exist without the other, and both
cases are ordinary:

- **A task with a link but no mirror** — the user deleted the checkbox from their note. The task keeps its
  link, because it is still true that it was captured there. Toggling it writes nothing to that document.
- **A mirror with no matching link on the task** — a checkbox pasted into a second note, or written by
  hand. It is a valid control surface: reconcile-on-open corrects it, and ticking it at save writes through
  to the task. It is simply not visited when the task is toggled from the list, because the task does not
  name that document.

Neither case is repaired, because neither is broken.

---

## Validation rules

| Rule | Source | Where enforced |
|---|---|---|
| A description is required; a `.type` suffix is not one | FR-007 | dispatch, before anything is saved |
| Type and tag tokens validate exactly as elsewhere | FR-004 | `add_task`, unchanged |
| A `--link` id must resolve before a task is created | FR-036 | CLI, via `resolve_id` |
| A mirror is located by id, never by line or text | FR-015 | recognition returns offsets from a fresh scan every time |
| A dead mirror is never rewritten or removed | FR-028 | resolution outcome `dead`, no splice |
| Sync writes never stamp `updated` | FR-029 | the sync writer does not call `stamp_updated` |
| A document is written only when something changed | FR-030 | `MirrorReport.text` is the same object when untouched |
| Reconciliation reads at most the document and `tasks.md` | FR-031 | no scan, no third file, ever |
