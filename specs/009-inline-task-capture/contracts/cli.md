# Contract: command-line surface

**Feature**: `009-inline-task-capture`

The CLI is an assistant's only interface (Principle II). Everything below is non-interactive: no prompt, no
confirmation, no pager, no editor. Data goes to stdout, diagnostics to stderr. Exit codes are 0 success,
1 not found, 2 usage error, 3 workspace error.

---

## `endpaper task add` — gains `--link`

```
endpaper task add "<description>" [--type <type>] [--tag <tag>]... [--link <id>]... [--json]
```

| Option | Behaviour |
|---|---|
| `--link <id>` | Records `id` in the task's `links` field. Repeatable (`action="append"`), matching `--tag`. |

**Validation order**: every `--link` id is resolved *before* anything is written. An id that resolves to
nothing exits **1** with `no record with id 'meeting_20260728_deadbeef'` on stderr, and no task is created
(FR-036).

Exit 1 rather than 2 because the argument was well-formed and names a thing that is not there — research
[R10](../research.md#r10---link-validation-and-its-exit-code). An assistant distinguishing "I mistyped the
flag" from "that meeting does not exist" needs these to differ.

**Unchanged**: an invocation with no `--link` writes a task line identical in shape to today's (FR-019).

### Output

Plain: the new task's id on stdout, as today.

`--json`:

```json
{
  "id": "task_a1b2",
  "text": "call Terry about the renewal",
  "done": false,
  "type": "followup",
  "tags": ["procurement"],
  "links": ["meeting_20260728_9f3c1a04"],
  "created": "2026-07-31"
}
```

`links` is added by `008-document-links` to every task-shaped JSON object; this feature populates it. Adding
a key is a minor change under Principle II.

---

## `endpaper task done` / `endpaper task undone` — propagate to mirrors

```
endpaper task done <id> [--json]
endpaper task undone <id> [--json]
```

`tasks.md` is written first, exactly as today. Then every document the task links to has its mirrors
spliced to the new state, without stamping `updated` (FR-029, FR-037).

### Exit codes

| Situation | Exit | Why |
|---|---|---|
| Task updated, every mirror written | 0 | |
| Task updated, some document missing/unreadable/unwritable | **0**, warnings on stderr | The operation asked for succeeded. Exiting non-zero would make an assistant believe the completion did not happen and retry it — research [R11](../research.md#r11-propagation-warnings-never-fail-the-operation). |
| Task updated, a link resolves to nothing | **0**, warning on stderr | A dead link is a reported state, not a failure (FR-018). |
| No task with that id | 1 | unchanged |
| Id ambiguous in `tasks.md` | 2 | unchanged |
| No workspace | 3 | unchanged |

### Output

Plain: silent on success, as today. Warnings on stderr, one per line, each naming the document:

```
could not write meetings/2026/07/2026-07-28-q3-planning.md: Permission denied
```

`--json`:

```json
{
  "id": "task_a1b2",
  "done": true,
  "links": ["meeting_20260728_9f3c1a04"],
  "documents_updated": ["meetings/2026/07/2026-07-28-q3-planning.md"],
  "warnings": []
}
```

| Key | Type | Meaning |
|---|---|---|
| `id` | string | the task |
| `done` | bool | the state it now holds |
| `links` | array of string | the task's link ids, in file order |
| `documents_updated` | array of string | workspace-relative paths whose mirrors were spliced; empty when none needed it |
| `warnings` | array of string | one message per document or link that could not be handled |

`documents_updated` lists only documents actually written — a document whose mirror already read correctly
does not appear, because it was not opened for writing (FR-030).

Paths are workspace-relative with forward slashes on every platform, matching every other path this CLI
emits.

---

## Stream separation and TTY behaviour

- Warnings, always to stderr, in both plain and `--json` modes. A `--json` consumer parsing stdout never
  has to strip a warning out of the document it is parsing.
- No colour or decoration when stdout is not a TTY, unchanged.
- Nothing blocks. A propagation touching ten documents is ten reads and up to ten writes; there is no
  prompt at any point, including when a document cannot be written.

---

## What is not added

No `endpaper task sync` or equivalent bulk reconcile command. Reconcile-on-open is a consequence of opening
a document, and the CLI has no command that opens or reads a document body — verified across the full
subcommand surface (research [R6](../research.md#r6-where-reconcile-on-open-hooks-in-and-what-the-clis-counterpart-is)).
Adding a command with no user need would be inventing surface to satisfy a symmetry that Principle II does
not actually require here; `task done`/`undone` propagation is the parity obligation and it is met.

If a document-reading command is added later, it calls `reconcile_on_open` like the TUI does and inherits
the behaviour with no new contract.
