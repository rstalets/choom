# Research: Task Content Editing

Phase 0 output for [plan.md](./plan.md). Each item states the decision, why it was chosen, and what
was rejected.

## R1 — Where a body starts and ends

**Decision.** A task's body span begins on the line after its checkbox line and runs to the end of
the last indented, non-blank line before a terminator. A line terminates the span when it is either
(a) a checkbox line at any indent, or (b) non-blank with no leading whitespace. Blank lines neither
extend nor terminate a span; they are included when more indented content follows, and excluded
when they trail.

```text
- [ ] call the vendor <!-- id:t_a1b2 -->   <- task line
                                           <- span starts here (blank, included)
  Need the Q3 comparison.                  <- body
                                           <- blank, included (content follows)
  - 07-28 called, left voicemail           <- body; a bullet, not a checkbox
                                           <- blank, excluded (trails)
- [x] send invoice <!-- id:t_c3d4 -->      <- terminator
```

**Rationale.** The rule is decidable one line at a time, in the loop `parse_tasks` already runs, and
it never has to look backwards. Excluding trailing blank lines matters on write: it means the blank
line separating two tasks belongs to neither, so replacing one body cannot swallow or duplicate the
separator.

**Alternatives considered.** *Indent-depth matching* (a body line must be indented at least as far
as the list item's content column) is what CommonMark actually specifies, but it rejects
hand-written bodies indented by one space, which is exactly the input Principle IV says to tolerate.
*Scanning to the next blank line* would end a body at its first paragraph break.

## R2 — Indentation: dedent on read, re-indent on write

**Decision.** The body text handed to the editor and to the CLI is dedented by the longest common
leading-whitespace prefix across the span's non-blank lines. That prefix is remembered and re-applied
when the body is written back; a body written where none existed uses two spaces. Blank lines are
written as genuinely empty lines, never as whitespace-only ones. When the common prefix is empty
because the span mixes tabs and spaces at column zero, no dedent happens and two spaces are used for
the write — the content survives verbatim, only its depth changes, and only if the user actually
edits it.

**Two spaces is the CommonMark-correct default**: `- ` puts the list item's content column at 2, so a
two-space indent is a continuation of the item and not an indented code block, which would need six.

**Rationale.** Re-applying the observed prefix is what makes a four-space or tab-indented body
survive an edit without being silently reformatted.

**Alternatives considered.** *Always normalise to two spaces* is simpler but rewrites every
hand-indented body the first time it is touched. *Never dedent* leaks the file's indentation into
the editor, so the user edits a buffer that starts every line with whitespace they did not type.

## R3 — Byte-identical no-op saves

**Decision.** `set_task_body` compares the requested body against the one already parsed and returns
without writing when they match — the same short-circuit `set_task_state` already uses when a task
is toggled to the state it is in.

**Rationale.** This is what makes SC-003 hold unconditionally, independent of any indent
reconstruction: opening the editor and saving without typing cannot alter the file because it does
not write to it. It also keeps a file on a synced folder from generating churn.

## R4 — A blank line between the task line and its body

**Decision.** When writing a body, emit one blank line between the task line and the first body
line. When reading, leading blank lines are dropped from the body text, so the round-trip is stable.

**Rationale.** Without the blank line, CommonMark reads the first body line as a lazy continuation of
the task's own paragraph — `- [ ] call the vendor` and `Need the Q3 comparison.` render as one run-on
paragraph. The blank line makes the body its own block, which is what SC-008 requires. The cost is
that the list becomes "loose" and renderers wrap every item in a paragraph; that is cosmetic and
affects only files that have bodies.

## R5 — Editing a slice of a file

**Decision.** Generalise `EditScreen` from "a file" to "an edit target": the buffer text, a `save`
callable returning a `SaveResult`, a display path, a line offset used when composing an `/ai` prompt
so the assistant is pointed at the right line of `tasks.md`, and a flag for whether the target has
frontmatter to stamp. The existing file-backed path becomes one target and behaves exactly as it
does today; a task body becomes the second.

**Rationale.** `_save` is entangled with the `/ai` flow — `_start_ai_request` calls `_save()` before
invoking the assistant — so the save path has to stay single. A target object keeps one save path
with two implementations behind it.

The frontmatter flag is load-bearing: `save_buffer` stamps `updated:` and reports "frontmatter's
updated: field could not be found" when it cannot. A task body has no frontmatter and never will, so
without the flag every task-body save would show a spurious warning.

**Alternatives considered.** *Subclassing `EditScreen`* would require the subclass to track changes
to `_save` and the `/ai` interaction. *A second editor screen* duplicates the discard dialog,
bindings, and status handling — three copies of Principle V's rules to keep aligned.

## R6 — Where the tests go

Risk-based, per Principle VI. The risk in this feature is concentrated in the file format, so that
is where the tests concentrate.

| Layer | Covers | Why here |
|-------|--------|----------|
| `unit/` | Span boundaries (nested checkbox, non-indented line, tabs, trailing blanks, EOF, malformed comment line); dedent/re-indent; the splice writer (add, replace, remove, no-op, CRLF, missing trailing newline, non-ASCII, not-found, ambiguous id) | Pure functions over strings. Every failure mode is reachable without a terminal, and these are the cases that lose user data if wrong. |
| `contract/` | `task show` exit codes (0/1/2), stream separation, non-blocking; `body` present in `task list --json` and `task show --json`; existing keys unchanged | The AI-facing surface. Extends the existing contract files rather than adding new ones. |
| `integration/` | One end-to-end path per user story, parametrized across adapters where both have one: hand-edited body renders in the preview; `e` → type → save lands in the file and the pane; `task show` prints it | Proves the wiring, once per story. |
| `performance/` | Nothing new | No budget in this feature is at risk: the body is parsed in the pass that already reads the file, and the preview reads from memory. |

Existing files to extend rather than duplicate: `test_task_handedit.py` and `test_task_no_loss.py`
gain body-bearing fixtures; `test_json_schema.py`, `test_exit_codes.py`, `test_streams.py`, and
`test_non_blocking.py` gain `task show`.

## R7 — Keeping the in-memory task list fresh

**Decision.** After a body save, reload the task list with `load_tasks(workspace)` and let the list
screen's existing resume path re-select by id.

**Rationale.** `ListScreen.on_screen_resume` already rebuilds rows and restores the highlighted item
by id, because a create or an edit could have changed anything while the screen was away. A body
save is one more instance of that, so it needs no new mechanism. A full reload of one file is
cheaper than the bookkeeping to patch a single task in place, and `parse_tasks` is the only code
that knows how to recompute the spans that a write just shifted.

## R8 — Rejected: a sidecar file per task

Storing bodies in `tasks/<id>.md` was considered and rejected by the requester. It would let the
editor open a whole file and keep `tasks.md` scannable, but it adds a directory to a collection set
`REQUIREMENTS.md` states is fixed, creates a second file that can drift from the first when a task
line is hand-deleted, and splits "the user's task" across two places in a tool whose premise is that
the file is the product.

## R9 — Rejected: treating nested checkboxes as body content

Reading an indented `- [ ] …` as body text rather than as a task would allow checklists inside a
body. It was rejected because it silently reclassifies data in vaults that already exist: a user who
today has indented checkboxes sees those tasks disappear from the list on upgrade. Principle IV
treats the user's existing file as the fixed point, so the parse rule for what is a task does not
change.

The consequence is documented in the spec: a checkbox line inside a body ends the body there and
appears in the list as its own task. Nothing is lost — the line is still in the file and still
visible, just in the list rather than the pane.
