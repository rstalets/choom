# Contract: task commands on the command line

Extends [001's CLI contract](../../001-meeting-notes/contracts/cli.md). Everything it fixes still
holds: no editor, no prompt, no pager, no ANSI on a non-TTY, data on stdout, diagnostics on stderr,
`EndpaperError.exit_code` mapped straight to the process exit code.

---

## Command surface

```
endpaper task add <description> [--type <type>] [--tag <tag>]...
endpaper task list [--json] [--all] [--type <type>] [--tag <tag>]...
endpaper task done <id>
endpaper task undone <id>
```

`--tag` is repeatable on both `add` and `list`. As with meetings, the help text for `task add` must
state that an unquoted `#tag` is eaten by the shell before endpaper sees it, and that a `#tag` inside
a *quoted* description is parsed out as a convenience.

`--all` means **include completed tasks**. It does not mean "every workspace" — see
[research.md R10](../research.md#r10---all-means-include-completed-and-nothing-else).

---

## `task add`

Prints the new task's **identifier**, one line, nothing else:

```console
$ endpaper task add "send the vendor comparison" --type followup --tag procurement
t_a1b2
```

The identifier is what the next command needs; the path is fixed and already known. Exit 0.

| Situation | Behaviour |
|---|---|
| `tasks.md` missing | Created, then appended |
| Description empty after tag removal | Exit 2, message on stderr, no file written |
| Type or tag is not a valid token | Exit 2, same message shape as `meeting new` |
| File not writable | Exit 3 |

---

## `task list`

Default output is tab-separated, one task per line, open tasks only, oldest first:

```
<id>\t<state>\t<created|->\t<type>\t<text>\t<tags comma-joined>
```

`<state>` is `open` or `done`. Absent `created` renders as `-`; absent type and tags render as empty
fields. Tab-separated with a fixed field count so `cut -f` works, matching `meeting list`.

`--json` emits a single JSON array on one line, exactly seven keys per object
([data-model.md](../data-model.md#entity-task-list-record-the-wire-projection)):

```json
[{"id":"t_a1b2","text":"send the vendor comparison","done":false,"type":"followup","tags":["procurement"],"created":"2026-07-28","line":3}]
```

- `id` and `created` may be `null`. `type` is `""` and `tags` is `[]` when absent — never null.
- Key order is stable. Adding a key is a minor change; renaming or removing one is breaking.
- Empty result is `[]`, exit 0 — including when `tasks.md` does not exist.

Warnings about malformed lines go to **stderr**, one per line, prefixed `endpaper: `, and do not
change the exit code. Piping stdout must never deliver a warning as data.

---

## `task done` / `task undone`

```console
$ endpaper task done t_a1b2
$ echo $?
0
```

Silent on success — nothing on stdout. The file change is the output.

| Situation | Exit | stderr |
|---|---|---|
| Toggled | 0 | — |
| Already in that state | 0 | — (no write attempted) |
| Id matches nothing | 1 | `endpaper: no task with id 't_zzzz'` |
| Id matches more than one line | 2 | `endpaper: id 't_a1b2' appears on lines 4 and 9; edit tasks.md to give one of them a different id` |
| `tasks.md` not writable | 3 | `endpaper: could not write <path>: <reason>` |
| No workspace | 3 | existing "no workspace found" message |

Matching is exact — no prefix or fuzzy resolution ([FR-031](../spec.md)).

---

## Exit codes

Unchanged from 001, applied to the new commands:

`0` success · `1` id not found · `2` usage error · `3` workspace error.

---

## Contract tests

Added to the existing files in `tests/contract/`:

1. `task list --json` output parses, and `set(keys) == {id,text,done,type,tags,created,line}` for
   every object.
2. Redirected (non-TTY) output of every task command contains no `\x1b` byte.
3. Every task command completes without reading stdin — run with stdin closed, assert no hang.
4. Warnings appear on stderr and never on stdout, verified by piping a workspace whose `tasks.md`
   has a broken comment.
5. Each row of the exit-code table above is exercised.
