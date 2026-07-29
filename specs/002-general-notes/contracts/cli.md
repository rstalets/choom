# Contract: Command-line interface (notes)

**Baseline**: [feature 001's CLI contract](../../001-meeting-notes/contracts/cli.md). Global rules,
exit codes, TTY detection, error message shape, and the JSON encoding rules are unchanged and are
not restated here.

**Stability**: Adding a subcommand or a JSON key is a minor change; renaming or removing one, or
changing an exit code, is breaking (Principle VI). This feature adds three subcommands and changes
nothing existing.

---

## Command surface added

```
endpaper note today                         # open (creating if needed) today's daily note
endpaper note new <description>             # create a typed or untyped note
      [--type <type>] [--tag <tag>]...
endpaper note list                          # list notes, daily and typed together
      [--json] [--type <type>] [--tag <tag>]... [--since <YYYY-MM-DD>]
```

`endpaper note` with no subcommand is a usage error, exit 2 — matching `endpaper meeting`.

---

## `endpaper note today`

Takes no arguments and no flags.

**stdout on success**: the note's path, one line, relative to the workspace root with forward
slashes. Exit 0.

```bash
$ endpaper note today
notes/daily/2026-07-28.md
$ endpaper note today          # same day, second call
notes/daily/2026-07-28.md      # identical output, file untouched
```

| Condition | Behaviour |
|---|---|
| No file for today | Creates `notes/daily/YYYY-MM-DD.md` with frontmatter and an empty body, prints its path, exit 0 |
| File exists | Prints its path, exit 0, **writes nothing** — not the body, not the frontmatter, not `updated`, not the mtime |
| File exists but its frontmatter is broken | Same as above. Prints the path, exit 0. Neither repaired nor reported as an error (FR-005) |
| `notes/daily/` missing | Created, then the note is written into it (FR-006) |
| Not inside a workspace | stderr message, exit 3 |

**The output is deliberately identical in the created and existing cases** (FR-007). A caller that
needs to know whether it created the note can compare the file's mtime, or check for the path before
calling — but the command does not report it, because a script that branches on "did I create it"
is a script that will eventually branch wrong on a race. The path is the useful answer in both
cases: it is what the caller pipes into `endpaper read` or an editor of their own choosing.

**Idempotence is the contract.** Calling this command *n* times on the same day produces exactly one
file and *n* identical lines of output. This is what makes it safe in a shell loop, a cron job, or
an assistant's retry.

---

## `endpaper note new`

```
endpaper note new <description> [--type <type>] [--tag <tag>]...
```

Argument rules are identical to `endpaper meeting new` — the same description handling, the same
`#tag`-inside-a-quoted-string convenience, the same `--tag` repeatability, the same token pattern
for `--type`. See the 001 contract; they are not restated here because FR-011 requires them to stay
the same and a second copy is a place for them to diverge.

**One rule notes add**:

| Argument | Rule |
|---|---|
| `--type daily` | Rejected. Exit 2, stderr: `endpaper: type 'daily' is reserved; use 'endpaper note today' for the daily note`. No file is created and `notes/` is not touched (FR-012). |

**stdout on success**: the created file's path, one line, relative to the workspace root with
forward slashes. Exit 0.

```bash
$ endpaper note new "vendor landscape" --type research --tag procurement
notes/2026-07-28-research-vendor-landscape.md

$ endpaper note new "some idea"          # untyped
notes/2026-07-28-some-idea.md

$ endpaper note new "vendor landscape" --type research   # same day, same description
notes/2026-07-28-research-vendor-landscape-2.md
```

The `#` shell hazard applies identically and is documented in `endpaper note new --help` and in
`AGENTS.md` (FR-011, and REQUIREMENTS.md's tagging rule which applies to every create command).

---

## `endpaper note list`

```
endpaper note list [--json] [--type <type>] [--tag <tag>]... [--since <YYYY-MM-DD>]
```

Returns typed notes and daily notes as one collection, sorted by `created` descending (FR-017).
Filters combine conjunctively; `--since` is inclusive and a non-ISO value is a usage error, exit 2.

**Never returns a meeting** (FR-018). `meeting list` never returns a note. The two scans do not
overlap directories.

### Human output (no `--json`)

Tab-separated, one note per line — date, type, title, comma-joined tags:

```
2026-07-28	daily	2026-07-28
2026-07-28	research	vendor landscape	procurement
2026-07-27		some idea
```

An untyped note leaves the type column empty. A daily note's title is its ISO date, so the first two
columns repeat — that is intended and is what makes a daily note greppable by date in either column.

Empty result: no output, exit 0.

### `note list --json`

stdout is exactly one JSON array with **the same seven keys** as `meeting list --json` — no key is
added for this feature, and none is renamed (FR-020):

```json
[
  {
    "id": "n_20260728_a1b2c3d4",
    "path": "notes/daily/2026-07-28.md",
    "title": "2026-07-28",
    "type": "daily",
    "tags": [],
    "created": "2026-07-28T09:14:00",
    "updated": "2026-07-28T09:14:00"
  }
]
```

The only observable differences from a meeting record are the `n_` id prefix and the `notes/` path
prefix. An assistant that already parses `meeting list --json` parses this with no change.

Empty result is `[]`, exit 0. Warnings from malformed note files go to stderr and are absent from
the array, exactly as for meetings.

### `--type daily`

Selects exactly the daily notes, and needs no special-casing — daily notes carry `type: daily` in
frontmatter and the existing exact-match filter finds them (FR-019).

```bash
endpaper note list --type daily --since 2026-07-01    # this month's daily notes
```

A daily note whose frontmatter a user broke does not appear in any listing, including this one. It
is still reachable by path, and `endpaper note today` still opens it. Listing and daily-note
resolution disagreeing on a broken file is intended: listing reports what parses, the daily note is
defined by its path.

---

## Interaction with `endpaper init`

Unchanged. `init` already creates `notes/daily/` (feature 001), so there is no migration and no new
init behaviour. A workspace created by 001 works with all three commands above immediately
(SC-010).

---

## Error messages added

```
endpaper: type 'daily' is reserved; use 'endpaper note today' for the daily note
endpaper: description must not be empty after removing #tag tokens
```

The second is feature 001's existing message, reached by `note new ""`. Both name what was wrong and
what to do instead (Principle V).
