# Phase 0 Research: 003-tasks

**Date**: 2026-07-28
**Feature**: [spec.md](./spec.md)

Feature 001 settled the project-wide questions — language, dependencies, packaging, argument
parsing, TUI testing, timestamps ([001 research.md](../001-meeting-notes/research.md)). None are
reopened here.

What is genuinely new in this feature is that **endpaper writes into a file the user also writes
into**. Meetings are one file per note, created with `O_EXCL` and never rewritten; `tasks.md` is one
file that both endpaper and the user edit, line by line, forever. Every decision below follows from
that.

---

## R1. What counts as a task line

**Decision**: A line is a task if it matches

```
^(?P<indent>[ \t]*)(?P<marker>[-*+])[ \t]+\[(?P<state>[ xX])\][ \t]+(?P<rest>.*)$
```

Everything else in the file — headings, paragraphs, non-checkbox list items, code fences — is
opaque text that is preserved and never interpreted.

**Rationale**: This is the CommonMark task-list-item shape as GitHub, Obsidian, and every other
markdown tool render it. Matching what renderers match is what makes acceptance criterion 3 in
REQUIREMENTS.md §3.3 ("renders as a checklist in any markdown viewer") true by construction rather
than by testing.

Indentation and the bullet marker are captured, not normalized, because the user chose them
(FR-027, FR-036). `[X]` is accepted as done on read; a toggle writes `[x]` and touches nothing else
on the line, so an uppercase marker is only ever normalized as a side effect of the user themselves
toggling that task.

**Alternatives considered**:
- **Parse with `markdown-it-py`** (already present transitively via Textual). Rejected: it gives an
  AST, not byte offsets, so writing a change back means re-rendering the document — precisely the
  operation Principle IV forbids. A line-oriented tool needs a line-oriented parser.
- **Accept any checkbox anywhere, including inside fenced code blocks.** Deferred, not rejected: a
  `- [ ]` inside a code fence in `tasks.md` is a pathological case in a file whose entire purpose is
  tasks. Noted as a known limitation in [data-model.md](./data-model.md#known-limitations).

---

## R2. The metadata comment, and what "malformed" means

**Decision**: Metadata rides in the **last** `<!-- ... -->` on the line, as space-separated
`key:value` pairs drawn from `id`, `type`, `tags`, `created`. `tags` is comma-separated. Values
never contain spaces.

```
- [ ] send the vendor comparison <!-- id:t_a1b2 type:followup tags:procurement,q3 created:2026-07-28 -->
```

Classification of a task line, in order:

| The line's trailing text | Classification | Behaviour |
|---|---|---|
| No `<!--` at all | **bare task** | Listed. Identifier backfilled (R5). |
| `<!--` with no `-->` on the line | **malformed** | Skipped, warned, left byte-identical. |
| A closed comment with **no** recognized key | **bare task** | The comment is the user's own prose. Listed; backfill appends a new metadata comment after it. |
| A closed comment with recognized keys, all tokens well-formed | **task** | Listed. |
| A closed comment with a recognized key **and** a token that is not `key:value` or whose key is unknown | **malformed** | Skipped, warned, left byte-identical. |
| Well-formed structure, but `created` is not an ISO date | **task** | Listed with `created = None`, warned. Not skipped. |

**Rationale**: The requirement's own example of malformed input is `- [ ] thing <!-- id:` — an
unterminated comment, where the parser genuinely cannot tell where the user's text ends and metadata
begins. Skipping is right there, because guessing would rewrite something the user typed.

The "no recognized key" row is what keeps `- [ ] fix the <!-- hack --> path` from being classified as
broken metadata. Taking the **last** comment on the line means a user comment and endpaper's metadata
can coexist, and round-trip.

The last row is a deliberate narrowing. Skipping a whole task because someone typed
`created:yesterday` makes the task vanish from every list while still sitting in the file — the
user's most useful information (the text) is lost to the interface over the least useful field. So
value-level damage that does not threaten identity degrades the field, not the task. Structural
damage, where the extent of the metadata is unknown, skips the line. Both warn.

**Alternatives considered**:
- **First comment on the line instead of the last** — breaks any line where the user wrote their own
  comment before endpaper appended metadata.
- **A stricter grammar with quoting, so values could contain spaces** — rejected under Principle III.
  Types and tags are already constrained to `[A-Za-z0-9][A-Za-z0-9_-]*` by `_validate_token` in
  `core/meetings.py`; nothing that goes in the comment can contain a space.

---

## R3. Task identifier format

**Decision**: `t_` + 4 lowercase hex digits, generated with `secrets.token_hex(2)` and retried
against the identifiers already parsed from the file. On read, any `[A-Za-z0-9_-]+` is accepted as
an identifier.

**Rationale**: REQUIREMENTS.md §3.3 shows `t_a1b2`, and this is the one identifier a user types by
hand — `endpaper task done t_a1b2` — so length is a usability cost, not a cosmetic one. Meetings use
8 hex digits with no collision check because there is no cheap way to enumerate every id in a
workspace; tasks live in a single file that has *already been fully parsed* by the time an id is
generated, so the check costs a set lookup. 4 hex digits with a check beats 8 without one here.

Accepting a looser pattern on read means a user who hand-writes `<!-- id:groceries -->` gets a task
that works, rather than a warning.

**Alternatives considered**: reusing `new_meeting_id`'s `m_YYYYMMDD_xxxxxxxx` shape — rejected as
21 characters of line noise per task in a file the user reads raw, for uniqueness guarantees that a
single-file scan does not need.

---

## R4. Parsing is a pure text-to-data function

**Decision**: `core.tasks` splits into a pure layer and a thin I/O layer.

```python
parse_tasks(text: str)            -> ParsedTasks          # pure; no Path, no open()
render_task_line(...)             -> str                  # pure
load_tasks(workspace)             -> (list[Task], list[ScanWarning])   # reads, backfills
add_task(workspace, description)  -> Task                 # appends
set_task_state(workspace, id, done: bool) -> Task         # toggles
```

**Rationale**: Principle I says core must be testable without a terminal; this goes one step
further and makes the *interesting* half testable without a filesystem. Every classification rule in
R2, every preservation rule in R6, and every edge case in the spec is a string-in, data-out
assertion — no `tmp_path`, no fixtures, no cleanup. The file layer that remains is three functions
long and has almost no branching to get wrong.

`ParsedTasks` carries the original lines alongside the records, so a writer can rebuild the file by
replacing exactly one line and re-joining, and a test can assert the rebuild is byte-identical when
nothing changed.

**Alternatives considered**: a `TaskFile` class holding a path and mutating methods. Rejected under
Principle VI ("prefer a plain function to a class") and because it invites caching a parse across
writes, which is exactly the staleness R7 exists to prevent.

---

## R5. Who writes the backfilled identifiers, and when

**Decision**: `parse_tasks` is pure and writes nothing; it reports which lines need an id.
`load_tasks(workspace)` — the single entry point both adapters call — parses, and if any line needs
an id, writes the repaired text back before returning records that carry the new ids. If the write
fails, it returns the records anyway, with `id=None` on the un-backfilled ones and a warning.

**Rationale**: REQUIREMENTS.md §3.3 is explicit that a bare checkbox is "picked up on the next scan
and given an id, in place" — so a read genuinely is a writer, and pretending otherwise would just
move the surprise somewhere less obvious. Making `load_tasks` the only place that happens keeps it to
one auditable function, and keeps `parse_tasks` honest for tests.

Degrading instead of failing (FR-038) matters because the read-only case is real: a file open in
another program on Windows, a synced folder mid-write, a vault on read-only media. A user asking
"what do I have to do" should get an answer.

Backfill writes **only** `id`. It does not invent `created` — see R8.

---

## R6. Writing without losing anything

**Decision**: Every write is: read the whole file with newline translation **off**, rebuild the line
list in memory, write to a temporary file in the same directory, `os.replace` it over the original.

- Read with `open(..., newline="")` so `\r\n` survives as `\r\n` in the string.
- Split with `str.splitlines(keepends=True)` so each line carries its own terminator, and lines that
  are not touched are re-joined exactly as they arrived — mixed line endings included.
- A new appended line uses the terminator of the file's last line; for a new or empty file, `\n`,
  matching `create_meeting`.
- `os.replace` is atomic on POSIX and on Windows, so a crash or a full disk leaves the original
  intact (FR-032).
- `PermissionError` / `OSError` on the write becomes `WorkspaceError` (exit 3).

**Rationale**: This is the whole of Principle IV expressed as a write strategy. Reading with
universal newlines and writing with `\n` would silently convert a Windows user's entire file to LF
on the first toggle — a one-character edit producing a whole-file diff in OneDrive, which is exactly
the kind of thing that makes a plain-files tool untrustworthy.

**The one place a byte changes that FR-037 does not anticipate**: appending to a file whose last
line has no terminator. The terminator must be added, or the new task lands on the end of the user's
last line. `add_task` therefore terminates the previously-final line and ends the new line with a
terminator. `set_task_state` and backfill preserve a missing final newline exactly. Recorded as a
refinement in [plan.md](./plan.md#follow-ups-outside-this-plan).

**Alternatives considered**:
- **Open the file `"w"` and rewrite in place** — a crash mid-write truncates the user's task list.
  Rejected outright.
- **Seek to the line offset and patch the single checkbox byte** — the smallest possible write, and
  tempting. Rejected: it needs byte offsets tracked through decoding, breaks the moment a multi-byte
  character sits earlier in the file, and buys nothing at this file size.
- **File locking** — out of scope per REQUIREMENTS.md §5, which names OneDrive's conflict-copy
  behaviour as the answer for simultaneous edits.

---

## R7. Locate by identifier at write time, never by cached line number

**Decision**: `set_task_state` re-reads and re-parses the file, finds the task by id, and writes.
The `line` field on a `Task` is display and diagnostic data only; no writer consumes it.

**Rationale**: Between the TUI's startup scan and a `space` keypress ten minutes later, the user may
have edited `tasks.md` in another window — that is the premise of the whole feature. A cached line
number is a stale pointer, and following one writes a checkbox onto the wrong task. The re-read
costs a millisecond on a file of this size.

This also gives duplicate-id detection (FR-030) for free: locating by id already enumerates matches,
so finding two is a natural outcome rather than an extra pass.

---

## R8. A hand-written task has no creation date, and endpaper does not invent one

**Decision**: Backfill writes `id` only. `created` stays absent, `Task.created` is `None`, the JSON
field is `null`, and undated tasks sort after dated ones, keeping file order among themselves.

**Rationale**: The date endpaper could write is the date it first *noticed* the line, which is not
when the user wrote it. Writing that down converts "unknown" into a plausible-looking wrong answer
that no later reader can distinguish from a real one. Absence is honest and costs one nullable field.

Sorting undated tasks last rather than first keeps a freshly hand-added line at the bottom of the
list, where the user just typed it.

---

## R9. The task surface in the TUI

**Revised 2026-07-28**, after feature 002 merged. The original decision — a dedicated
`TaskListScreen` — was made when the TUI had exactly one screen and one content type, and tasks had
nowhere to live. 002 shipped a persistent collection menu pane (`#collection-menu`, `COLLECTIONS =
("meetings", "notes")`, `h`/`l` between panes, `switch_collection()`), which is a first-class answer
to "a second content type" that did not exist when this was written. The superseded decision is kept
below.

**Decision**: **Tasks are a third collection** in the existing menu — `COLLECTIONS = ("meetings",
"notes", "tasks")` — inside the one `ListScreen`. No new screen. `space` toggles, `a` shows completed
as well, `j`/`k` and the arrows move, `h`/`l` cross panes, `/` opens the shared bar. New verbs `task`
and `tasks` join `VERBS`; `tasks` posts `CollectionRequested("tasks")` exactly as `notes` does, and
`task` posts `CreateRequested("task", …)`.

**The preview pane stays visible and empty on the tasks collection** (requirements owner's decision).
A task is one line and has nothing to preview today, but the pane is reserved for a future feature
rather than collapsed. Keeping it also means the three-pane layout does not reflow when the user
crosses collections, which is worth more than the reclaimed width.

Verified against Textual's documentation and the merged code: `ListView` binds only `enter`, `up`,
and `down`, so `space` and `a` are unclaimed, and Textual resolves an unmatched key by walking from
the focused widget up the DOM — the same mechanism `ListScreen` already relies on for `j`/`k`, `h`,
`l`, and `/`. No `priority=True`, nothing rebound.

**Two guards the branching needs**:

1. `space` and `a` are screen-level actions that **no-op unless `app.active == "tasks"`**. They are
   bound once, not conditionally registered, because a binding that exists but does nothing is
   simpler than a binding set that changes shape under the user.
2. The status bar text is per-collection, so the footer advertises `space toggle` and `a all` only
   where they do something. Principle V requires every *active* binding to be visible; it equally
   requires the footer not to promise a key that will not fire.

**Rationale on Principle V**: this now satisfies the principle literally rather than by argument.
The TUI stays one screen with a filterable list and a preview pane; tasks are a third thing that
list can show; every transition is still one keystroke. The Complexity Tracking entry the original
decision required is deleted, not re-justified — the better design made the deviation unnecessary.

**Cost of the revision**: `app` state stops being uniform. `documents` and `warnings` are dicts keyed
by collection, but a `Task` is not a `Document` — different fields, different store, no path. So the
app carries `tasks: list[Task]`, `visible_tasks: list[Task]`, `show_done: bool`, and
`warnings["tasks"]`, and `ListScreen.refresh_rows` branches once on `app.active` to choose its row
type. That is one conditional in one method, against a whole screen class avoided.

**Alternatives considered**:
- **A dedicated `TaskListScreen`** *(the superseded decision)* — a second screen reusing `CommandBar`
  and `StatusBar`, with no preview pane. It was the right call against a single-collection TUI and
  the wrong one against a multi-collection TUI: it would have introduced a second navigation model
  (`/tasks` switching *screens*) alongside the menu that switches *collections*, for the same user
  intent.
- **Hiding the preview pane on tasks** — rejected by the requirements owner; the pane is reserved
  for a future feature, and a layout that reflows on every collection change is worse than an empty
  pane.
- **Tasks in the preview pane of the meetings list** — rejected; it makes tasks a detail of meetings,
  which REQUIREMENTS.md §3.3 explicitly says they are not in v0.0.1.

---

## R10. `--all` means "include completed", and nothing else

**Decision**: On `endpaper task list`, `--all` includes completed tasks. Cross-workspace scope is not
implemented in this feature and, when it arrives, must not claim this flag on this command.

**Rationale**: REQUIREMENTS.md uses `--all` for both meanings — §3.3 for completed tasks, §3.4 for
widening to every workspace. On `task list` they would collide, and the §3.3 meaning is the one
specified with acceptance criteria. Flagged to the requirements owner in
[plan.md](./plan.md#follow-ups-outside-this-plan) rather than resolved unilaterally for §3.4.

The rest of the CLI shape follows feature 001 exactly: `--tag` repeatable, `--type` single, `--json`
on the read command, `argparse` subparsers, data on stdout, warnings on stderr.

---

## R11. Dependencies and performance

**Decision**: No new runtime dependency. `re`, `secrets`, `os`, and `pathlib` from the standard
library. No new configuration.

A 1,000-task file is roughly 80 KB: one read, one regex per line, one dictionary per match. That is
comfortably inside SC-007's one second — the same order as the 001 scan, but on a single file
instead of a thousand, and with no YAML parser in the path.

No performance work is planned beyond a fixture that generates a 1,000-task file and asserts the
bound, mirroring the existing `tests/performance/` pattern.
