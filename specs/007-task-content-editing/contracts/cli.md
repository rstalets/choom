# Contract: CLI surface

The CLI is an AI assistant's only interface (Principle II). Everything here is non-interactive: no
editor, no prompt, no pager, data on stdout, errors on stderr.

## `endpaper task show <id> [--json]`

Prints one task and its body, selected by id.

**Human form** — the same columns `task list` prints for that task, then the body verbatim after a
blank line. A task with no body prints the summary line alone.

```console
$ endpaper task show t_a1b2
t_a1b2  open  2026-07-30  followup  call the vendor  procurement

Need the Q3 comparison before the renewal meeting.

- 07-28 called, left voicemail
```

**JSON form** — one object, identical in shape to an entry of `task list --json`:

```json
{
  "id": "t_a1b2",
  "text": "call the vendor",
  "done": false,
  "type": "followup",
  "tags": ["procurement"],
  "created": "2026-07-30",
  "line": 12,
  "body": "Need the Q3 comparison before the renewal meeting.\n\n- 07-28 called, left voicemail"
}
```

**Exit codes**

| Code | Condition |
|------|-----------|
| 0 | The task was found. A task with no body still exits 0, with `"body": ""`. |
| 1 | No task has that id. |
| 2 | The id is ambiguous — more than one task carries it. The message names the conflicting line numbers. |
| 3 | `tasks.md` cannot be read, or no workspace is selected. |

## `endpaper task list --json` (changed)

Every entry gains `"body"`: the dedented body text, `""` when the task has none. Every key the
command emits today keeps its name and meaning. Adding a key is a minor change under Principle VI;
this one is a changelog entry.

The human-readable `task list` table is **unchanged** — it stays one line per task, because a
multi-line body would break the column layout that makes the table scannable. `task show` is how a
body is read in human form.

## Unchanged

`task add`, `task done`, and `task undone` gain no flags and change no output. `task done` and
`task undone` preserve a task's body, which follows from their only touching one character of the
checkbox line.

## AGENTS.md

The generated workspace guidance file documents the task line format and the commands an assistant
reaches for. It gains the body shape and `task show`, staying within its ~60-line budget.
