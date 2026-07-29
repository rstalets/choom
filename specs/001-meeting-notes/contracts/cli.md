# Contract: Command-line interface

**Stability**: Everything on this page is a published contract. Adding a JSON key or a flag is a
minor change; renaming or removing one, or changing an exit code, is breaking (Principle VI).

**Audience**: AI assistants first, humans second. Every rule here exists because an assistant
cannot recover from a prompt, a pager, or an escape sequence in a pipe.

---

## Command surface

```
endpaper                                    # no args -> open the TUI
endpaper --version                          # print version, exit 0, works anywhere
endpaper --help                             # print help, exit 0, works anywhere
endpaper init                               # create a workspace here
endpaper meeting new <description>          # create a meeting
      [--type <type>] [--tag <tag>]...
endpaper meeting list                       # list meetings
      [--json] [--type <type>] [--tag <tag>]... [--since <YYYY-MM-DD>]
```

Anything not listed is out of scope for this feature and must exit 2 with a usage error.

---

## Global rules

| Rule | Requirement |
|---|---|
| Data on stdout, diagnostics on stderr, never interleaved | FR-040 |
| Never open an editor, prompt, wait for a keypress, or page | FR-038 |
| No colour or cursor control when stdout is not a TTY | FR-039 |
| No network access | FR-007 |
| Any subcommand present ⇒ never launch the TUI | FR-004 |

**TTY detection**: `sys.stdout.isatty()`. When false, output is plain text. Because the CLI never
uses Rich, the practical rule is simply that nothing writes ANSI — the check exists so future
additions cannot regress it, and a test asserts zero `\x1b` bytes in redirected output.

## Exit codes

| Code | Meaning | Raised by |
|---|---|---|
| 0 | Success | — |
| 1 | Target not found | `NotFoundError` |
| 2 | Usage error | argparse, and `UsageError` for semantic misuse (bad `--since`, bad `--type`) |
| 3 | Workspace error | `WorkspaceError` — no workspace found, or already a workspace |

An empty result is **not** an error. `meeting list` in a workspace with no meetings exits 0
(FR-006 of the spec's US3 scenario 6).

---

## `endpaper` (no arguments)

Opens the TUI (FR-003). Argument inspection happens before argparse so that a bare invocation is
never a parse error.

| Condition | Behaviour |
|---|---|
| Inside a workspace | TUI opens on the meetings list |
| Not inside a workspace | stderr message + exit 3. Does **not** open an empty TUI (US1 scenario 5) |
| stdout is not a TTY | stderr message + exit 3. A TUI in a pipe is never what the caller wanted |

---

## `endpaper init`

Creates the workspace layout in the current directory.

**stdout on success**: the absolute path of the created workspace root, one line. Exit 0.

**Failure**: if `.endpaper/` already exists here, write to stderr a message naming the existing
workspace root, exit 3, and modify nothing on disk (FR-009). Partial creation is not possible: the
marker file is written last, so an interrupted init leaves a directory that is not yet a workspace.

---

## `endpaper meeting new`

```
endpaper meeting new <description> [--type <type>] [--tag <tag>]...
```

| Argument | Rule |
|---|---|
| `<description>` | Required, positional. May contain `#tag` tokens, which are parsed out and stripped from the title (FR-022). Must be non-empty after stripping tags — otherwise exit 2. |
| `--type` | Optional. Must match `^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$`, stored lowercase. A value containing `/`, `\`, `.`, or a leading `-` is a usage error, exit 2 — this is what keeps a crafted type from writing outside `meetings/`. |
| `--tag` | Optional, repeatable. Same pattern as `--type`. Order preserved, duplicates removed. |

**stdout on success**: the created file's path, one line, relative to the workspace root with
forward slashes. Exit 0 (FR-024).

**The `#` hazard.** `#` starts a comment in bash and zsh, so an unquoted `#tag` is deleted by the
shell before endpaper runs, and the tag vanishes silently. `--tag` is the supported form. This must
be stated in `endpaper meeting new --help` and in `AGENTS.md` (FR-012). Tags inside a *quoted*
description are parsed as a convenience, not as the recommended path:

```bash
endpaper meeting new "Q3 planning" --type standup --tag platform   # supported
endpaper meeting new "Q3 planning #platform" --type standup        # also works
endpaper meeting new Q3 planning #platform                         # tag lost by the shell
```

---

## `endpaper meeting list`

```
endpaper meeting list [--json] [--type <type>] [--tag <tag>]... [--since <YYYY-MM-DD>]
```

Filters combine conjunctively (FR-028). `--since` is inclusive; a value that is not an ISO date is
a usage error, exit 2, and nothing is listed.

### Human output (no `--json`)

One meeting per line, tab-separated, sorted by `created` descending:

```
2026-07-28	standup	Q3 planning	platform
2026-07-27	vendor	Contoso renewal	procurement,legal
```

Columns are date, type, title, comma-joined tags. An untyped meeting leaves the type column empty.
Tab separation rather than aligned columns, so `cut` and `awk` work and so output does not depend
on terminal width. Empty result: no output, exit 0.

### `meeting list --json`

stdout is exactly one JSON array, no preamble or trailing text (US4 scenario 4). Each object has
exactly these seven keys:

```json
[
  {
    "id": "m_20260728_a1b2c3d4",
    "path": "meetings/2026-07-28-standup-q3-planning.md",
    "title": "Q3 planning",
    "type": "standup",
    "tags": ["platform"],
    "created": "2026-07-28T09:14:00",
    "updated": "2026-07-28T09:14:00"
  }
]
```

| Key | Type | Notes |
|---|---|---|
| `id` | string | `m_YYYYMMDD_` + 8 hex |
| `path` | string | Relative to workspace root, forward slashes on **every** platform |
| `title` | string | Never null; a meeting with no title cannot exist |
| `type` | string | `""` when untyped, never null |
| `tags` | array of string | `[]` when none, never null |
| `created` | string | `YYYY-MM-DDTHH:MM:SS`, local naive |
| `updated` | string | Same format |

Empty result is `[]`, exit 0 — not an error, and not absent output.

**Encoding**: UTF-8, `ensure_ascii=false`, so a non-ASCII title stays readable. Trailing newline
after the array.

**Warnings never contaminate stdout.** A malformed meeting file produces a warning line on stderr
and is absent from the array. An assistant piping stdout to a JSON parser is unaffected (FR-040,
FR-033).

---

## Error message shape

Errors go to stderr as a single line, no traceback, no colour:

```
endpaper: no workspace found in this directory or any parent. Run 'endpaper init' to create one.
endpaper: this directory is already an endpaper workspace: /Users/x/notes
endpaper: --since expects a date like 2026-07-28, got 'yesterday'
endpaper: --type may not contain '/', '\', '.', or start with '-'
```

Every message names what was wrong and what to do instead (Principle V). Tracebacks are suppressed
for the `EndpaperError` hierarchy; an unexpected exception still tracebacks, because silently
swallowing a bug is worse than an ugly message.
