# Contract: CLI delete commands

**Feature**: `011-ui-refinements` | **Covers**: FR-015–FR-020, US3

Three peer subcommands, one per record type. All three are thin wrappers over
`core.deletion.delete_by_id`; they differ only in the `expect` kind they pass.

---

## Synopsis

```text
choom meeting delete <id> --force
choom note delete <id> --force
choom task delete <id> --force
```

| Argument | Required | Notes |
|---|---|---|
| `<id>` | yes | The record id, as it appears in the matching `list --json` output |
| `--force` | yes | Explicit acknowledgement. Without it the command deletes nothing |

There is no `--json` flag. `--json` is required on *read* commands (Principle II); `delete` returns no
data, and adding an empty JSON object would imply a schema that could later be depended on.

---

## Streams

| Stream | Content |
|---|---|
| stdout | **Empty on success.** Never written to on failure either |
| stderr | One line naming the failure, on any non-zero exit |

No colour, no decoration, on either stream, on any platform, TTY or not — these commands print no styled
output at all, so the non-TTY rule is satisfied by construction rather than by a check.

---

## Exit codes

Existing registry (`docs/REQUIREMENTS.md` §4.1); nothing added, nothing renamed.

| Code | When | stderr |
|---|---|---|
| `0` | The record was deleted | — |
| `1` | No record carries `<id>` | `no meeting with id 'meeting_abc'` |
| `1` | `<id>` resolves to a record of a different kind | `no meeting with id 'note_abc'` |
| `2` | `--force` was not given | `refusing to delete without --force` |
| `2` | `<id>` is carried by more than one record | `id 'task_abc' is carried by more than one record: <path>, <path>` |
| `2` | Missing or extra positional arguments | argparse's own usage message |
| `3` | The file or `tasks.md` could not be written | the underlying workspace error |

---

## Non-blocking guarantee

The commands never prompt, never page, and never read stdin. This is structural, not conventional:
`--force` is a *required* argument, so there is no "ask when the flag is absent" branch to fall into.

Verifiable as: run with stdin closed and stdout redirected to a file; the command completes without
waiting and the file contains no prompt text and no escape sequences.

---

## Behaviour

Each command:

1. Resolves the workspace the same way every other command does.
2. Calls `delete_by_id(workspace, id, expect=<kind>)`.
3. Returns 0, or lets the raised `ChoomError` propagate to `main()`, which prints it to stderr and
   returns its `exit_code`.

Deleting a task removes its line and body span from `tasks.md` and writes no other file, so mirrors of
that task in documents are left exactly as the user wrote them; they resolve as dead links afterwards.

---

## Examples

```console
$ choom task delete task_k3n9 --force
$ echo $?
0

$ choom task delete task_k3n9 --force
no task with id 'task_k3n9'
$ echo $?
1

$ choom note delete note_p2x1
refusing to delete without --force
$ echo $?
2

$ choom meeting delete note_p2x1 --force
no meeting with id 'note_p2x1'
$ echo $?
1
```

---

## Compatibility

Additive. No existing command, flag, `--json` schema, or exit code changes. An assistant that never calls
`delete` sees no difference.
