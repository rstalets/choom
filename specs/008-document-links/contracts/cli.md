# Contract: `endpaper links`

**Feature**: `008-document-links`

The CLI is an assistant's only interface (Principle II), so everything here is non-interactive: no
prompt, no confirmation, no pager, no colour on a non-TTY. Data goes to stdout, diagnostics to
stderr, and the two are never interleaved.

---

## Commands

```
endpaper links <id>            [--json] [--direction out|in|both]
endpaper links check [<path>…] [--json]
endpaper links heal  [<path>…] [--json] [--dry-run]
```

`check` and `heal` are reserved words in the `<id>` position. This is unambiguous rather than
heuristic: every id carries a collection prefix (`meeting_`, `note_`, `task_`), so no real id can
collide with either word. The id prefix change (research R6) is what makes the reservation safe.

### `endpaper links <id>`

What a record points at, and what points at it.

| Flag | Default | Meaning |
|---|---|---|
| `--direction out\|in\|both` | `both` | Restrict to outbound or inbound |
| `--json` | off | Emit the stable schema below |

`--direction in` is the backlink question and costs a workspace scan; `out` reads one file.

### `endpaper links check [<path>…]`

Reports broken links in two classes, because they need different responses:

- **stale** — the id resolves but the path is wrong or absent. Mechanically fixable.
- **dead** — the id resolves to nothing. Needs a decision: relink, remove, or recreate the target.

With no paths, the whole workspace. With paths, only those files (FR-036). Writes nothing, ever.

### `endpaper links heal [<path>…]`

Rewrites every stale link. Touches no dead one (FR-035).

| Flag | Meaning |
|---|---|
| `--dry-run` | Report exactly what `heal` would change and write nothing (FR-037) |
| `--json` | Emit the stable schema below |

**A file with nothing stale in it is not written**, so its `updated` does not move and a colleague's
sync client sees no modification (link-format.md → Repair). This is the difference between a
deliberate repair pass and the repair-on-scan behaviour that was rejected.

---

## JSON schema

Fixed by FR-039. One object per link reported; `links check` and `links heal` emit an array of them.

```json
[
  {
    "file": "notes/2026/07/2026-07-30-research-vendor.md",
    "line": 12,
    "text": "Q3 planning",
    "target_id": "meeting_20260728_a1b2c3d4",
    "old_path": "../../meetings/2026/06/2026-06-28-q3-planning.md",
    "new_path": "../../meetings/2026/07/2026-07-28-q3-planning.md",
    "status": "stale"
  },
  {
    "file": "tasks.md",
    "line": 4,
    "text": "call Terry about the renewal",
    "target_id": "meeting_20260101_deadbeef",
    "old_path": null,
    "new_path": null,
    "status": "dead"
  }
]
```

| Key | Type | Notes |
|---|---|---|
| `file` | string | Workspace-relative, forward slashes |
| `line` | integer | 1-indexed |
| `text` | string | Link text; for a task's `links:` field, the task text |
| `target_id` | string \| null | `null` only for a path-only link that has not yet gained a fragment |
| `old_path` | string \| null | `null` when the link was written with no path |
| `new_path` | string \| null | `null` for a dead link — it never gets one |
| `status` | string | `resolved` \| `stale` \| `dead` |

`endpaper links <id> --json` emits the same object shape, so one parser handles all three commands.
`--direction both` groups them:

```json
{ "id": "meeting_20260728_a1b2c3d4", "out": [ … ], "in": [ … ] }
```

With `--direction out` or `in`, the top level is the bare array.

**Stability**: adding a key is a minor change; renaming or removing one is breaking (Principle II).
Recorded in the changelog per FR-054.

---

## Human-readable output

Tab-separated, one row per link, no header — matching `task list` and `meeting list`, so `cut -f`
works:

```
notes/2026/07/2026-07-30-research-vendor.md:12	stale	meeting_20260728_a1b2c3d4	Q3 planning
tasks.md:4	dead	meeting_20260101_deadbeef	call Terry about the renewal
```

Never colourised when stdout is not a TTY.

---

## Exit codes

Per the constitution: `0` success, `1` not found, `2` usage error, `3` workspace error. An unresolved
link is a target not found, which is why both stale and dead map to `1`.

| Command | `0` | `1` | `2` | `3` |
|---|---|---|---|---|
| `links <id>` | Resolved, including when it has no links at all (US3 AC4) | The id itself resolves to nothing | Bad `--direction` value | No workspace |
| `links check` | Nothing stale and nothing dead | Anything stale or dead | Bad flag | No workspace |
| `links heal` | Nothing stale remains and nothing was dead | Any dead link remains | Bad flag | Cannot write |
| `links heal --dry-run` | Same as `check` | Same as `check` | Bad flag | No workspace |

An empty result is success, not "not found" — a record nothing points at is a normal record.

---

## Guarantees an assistant can rely on

- **Never blocks.** No prompt, no confirmation, no pager — including `heal`, which is destructive in
  the sense that it rewrites files and therefore takes `--dry-run` rather than asking (Principle II).
- **`--dry-run` and the real run report the same set.** Verified as a contract test, not assumed:
  this is what makes it safe to run `heal` without reading a diff first.
- **A dead link is never touched.** Not rewritten, not removed, not "fixed" by guessing. Reported
  with everything needed to choose: file, line, text, and the unresolvable id (FR-034).
- **One malformed file never poisons a run.** An unparseable file is skipped with a diagnostic on
  stderr; every other file still reports (Principle IV).
- **stdout stays parseable.** Warnings — dead links, ambiguous ids, unreadable files — go to stderr.
  Piping stdout to a JSON parser never receives a diagnostic as data.
