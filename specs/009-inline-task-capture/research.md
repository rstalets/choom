# Phase 0 Research: Inline Task Capture

**Feature**: `009-inline-task-capture` | **Date**: 2026-07-31

Every decision below was taken against the code as it stands on `main` (commit `82e863f`, feature 007
merged) plus the contracts `008-document-links` publishes. Where a claim is about existing behaviour,
the file and symbol are named so it can be checked rather than believed.

---

## R1: Where the reconciliation logic lives

**Decision**: A new core module, `endpaper/core/mirrors.py`, owning everything about the relationship
between a checkbox in a document and a task in `tasks.md`: recognising a mirror, writing one, applying a
task's state into a document, and resolving which side wins. `tasks.py` gains nothing; `links.py` (from
008) gains nothing.

**Rationale**: The concern is genuinely new and genuinely one thing. It is not "tasks" — it writes
documents, which `tasks.py` has never done and should not learn to do, and giving `tasks.py` a dependency
on `links.py` would invert the layering (links resolves *into* tasks.md today). It is not "links" —
008's module is a grammar and a resolver with no notion of completion state, and 008 explicitly kept it
as one module because splitting the scanner from the healer is how a byte-preservation guarantee gets
broken. A third module keeps each of the three honest: `links` knows syntax, `tasks` knows `tasks.md`,
`mirrors` knows the edge between them.

**Import direction**: `mirrors` → {`links`, `tasks`, `editing`}. Nothing imports `mirrors` except the two
adapters. No cycle.

**Alternatives considered**:
- *Extend `tasks.py`.* Rejected: it is already the largest core module (~620 lines) and this would add
  document I/O to a module whose entire contract is one file.
- *Extend `links.py`.* Rejected: a mirror is a link, but reconciliation is not a link operation — it is a
  state operation that happens to be addressed by a link. 008's healer must stay a pure destination
  splice.
- *Put it in the TUI.* Rejected outright by Principle I, and it would leave the CLI's `task done`
  propagation with nothing to call.

---

## R2: How a mirror is recognised

**Decision**: A mirror is a line that is (a) a markdown checklist item and (b) contains a link whose
fragment is a task id. Recognition composes two things that already exist: `find_links()` from 008 for
the link (which already excludes code fences, code spans, images, and URL-scheme destinations), and a
checkbox-prefix match of the same shape `tasks.py` already uses.

`find_links` returns `start`/`end` character offsets into the text, which is what makes the rest of this
feature a splice rather than a re-render.

**Rationale**: Reusing `find_links` is what buys FR-013 and the code-fence edge case for free, and it is
what guarantees `/task` inside a fenced block is inert without this feature knowing what a fence is.
Requiring the checkbox prefix is what keeps an ordinary prose link to a task — "as agreed in
[call Terry](../../tasks.md#task_a1b2)" — from being silently turned into a control surface.

**The prefix rule**: optional leading whitespace, a `-`, `*`, or `+` bullet, a space, `[`, exactly one
state character (space or `x`/`X`), `]`, a space. This is the same shape `_TASK_LINE` in `tasks.py`
matches, minus that regex's anchoring to a bare `- [ ] ` at column zero. A numbered list item
(`1. [ ] …`) is out: `tasks.md` does not produce one and CommonMark task-list extensions are inconsistent
about it.

**Alternatives considered**:
- *Match on the task's text.* Rejected by FR-015, and the spec's own scenario 4.3 — the user is expected
  to reword the line.
- *Match by line number recorded somewhere.* Rejected: that is stored derived state, which is Principle
  III, and the user is expected to move the line.

---

## R3: Which documents a toggle writes to

**Decision**: The documents named by the task's own `links:` ids, resolved with `resolve_id()`. Not an
inbound scan.

**Rationale**: FR-021 says "every document the task links to", and that is both cheaper and more
defensible than the alternative. A task has zero, one, or a handful of links, so a toggle costs that many
resolutions — where a resolution is a substring probe over file bytes with an early exit (008 R5), not a
parse. The copy-pasted-mirror case that an inbound scan would also catch is covered by reconcile-on-open
(FR-026, US6 scenario 2), which is where the spec puts it.

**Rejected**: `inbound_links(workspace, task_id)` on every toggle. It is correct and it is 155 ms per
toggle on a 6,000-document workspace (008's measurement), for a case the design already handles for free.
It would also make the space key's cost proportional to workspace size, which is exactly the property
this project keeps refusing to accept.

**Consequence worth stating**: a mirror in a document the task does not link to is not updated at the
moment of the toggle. It is updated the next time that document is opened. This is the design, not a gap.

---

## R4: Detecting "both sides changed" without storing anything

**Decision**: The editing session holds a baseline — a mapping from task id to the state each mirror had
when the document was opened or last reconciled. It lives in the `EditScreen` instance for the life of
that screen and is never written to disk. Core stays stateless: the reconcile function takes the baseline
as an argument.

**Rationale**: This is the only reading of FR-024 that does not require a second source of truth. With
the baseline, all four cases are decidable from three booleans — baseline, current mirror, current task:

| baseline | mirror now | task now | meaning | resolution |
|---|---|---|---|---|
| b | b | b | nothing changed | no write (FR-030) |
| b | ¬b | b | user ticked it here | mirror wins → write `tasks.md` (FR-022) |
| b | b | ¬b | changed elsewhere | task wins → correct mirror (FR-023) |
| b | ¬b | ¬b | both changed | save wins → write `tasks.md`, warn (FR-024) |

The fourth row is only distinguishable from the second because of the baseline; without it, both look
like "mirror disagrees with task" and the warning FR-024 requires could not be raised.

**Alternatives considered**:
- *Persist a last-agreed marker in the file or a sidecar.* Rejected by Principle III, and it would be
  wrong the moment someone hand-edits either file.
- *Compare file mtimes.* Rejected: mtime on a cloud-synced folder is not a reliable ordering, and it
  cannot attribute a change to a specific task.
- *Always let the save win, and never warn.* Rejected: FR-024 asks for the divergence to be reported, and
  a silent overwrite of someone else's completion is exactly the failure this design exists to prevent.

---

## R5: The two write paths, and why `save_buffer` is not overloaded

**Decision**: Two distinct paths, because they differ on `updated`:

1. **User save** — the person edited the document. `updated` is stamped. Reconciliation runs on the buffer
   text *before* `save_buffer()` is called; `save_buffer` keeps the job it has (heal links, stamp, write).
2. **Sync write** — nobody edited the document; a task's state is being pushed into it, from a toggle in
   the tasks list or from reconcile-on-open. `updated` is **not** stamped (FR-029). This needs its own
   writer: `save_buffer` always stamps and cannot serve here.

**Rationale**: 008 already threads `workspace` into `save_buffer` for link healing, and it is tempting to
thread a mirror baseline through as well. That would put a stateful, session-scoped argument into a
function whose contract is "write these bytes safely", and it would still not serve the sync path, which
has no buffer and no session. Keeping reconciliation as its own call in `mirrors.py` leaves one function
per job and leaves 008's seam untouched.

**The sync writer** reuses the same atomic technique already used twice in the codebase (`editing.save_buffer`
and `tasks._atomic_write`): same-directory temp file, `os.replace`, line-ending and trailing-newline
policy restored from what was read. It does not go through `stamp_updated`.

**Alternatives considered**:
- *Add `mirror_baseline=` to `save_buffer`.* Rejected as above.
- *Let the sync path stamp `updated` too.* Rejected by FR-029 and by the spec's stated reason: it would
  reorder every recency-sorted list because someone ticked a box in a different collection.

---

## R6: Where reconcile-on-open hooks in, and what the CLI's counterpart is

**Decision**: Three call sites in the TUI — `open_editor()`, `open_task_editor()`, and `PreviewScreen`'s
mount/resume. Core exposes one function they all call. There is no CLI counterpart, because the CLI has no
command that opens or reads a document.

**Verified**: the CLI's full subcommand surface is `init`, `meeting create|list`, `note create|today|list`,
`task add|list|show|done|undone`, `config`. Nothing reads a document's body. There is therefore no CLI
behaviour that reconcile-on-open is missing from — the parity obligation under Principle II attaches to
`task done`/`undone` propagation (FR-037), which is specified and delivered.

**Rationale**: `PreviewScreen` is included deliberately. FR-026 and US6 scenario 6 require that what is
displayed is never a stale checkbox, and the preview is the most common way a document is looked at.
Excluding it would mean the read-only path shows something the editing path would immediately correct.

**Cost control (FR-031, SC-007)**: the function returns without reading `tasks.md` at all when the
document contains no mirror. The mirror test is `find_links()` over text already in memory — the document
was just read to be displayed — so a document with no links costs one scan of a string that is already
there, and no additional file read.

---

## R7: Registering `/task` and the dotted type suffix

**Decision**: Register `EditorCommand(name="task", …)` in `EDITOR_COMMANDS`, and teach `parse_line()` to
split a dotted suffix off the verb exactly as `command_bar.py` already does.

**Verified**: `command_bar.py:114` does `stem, _, type_part = first_token.partition(".")` then
`resolve_verb(stem.lower())`. `core/editor_commands.py:parse_line` currently does
`word, _, argument = rest.partition(" ")` and looks up the whole word, so `/task.followup` does not match
today. One `partition(".")` on the word before the table lookup fixes it, and `ParsedCommand` gains the
suffix.

**Rationale**: This is the smallest change that satisfies FR-002, and it is the same three lines the
command bar already runs — which is the point. It also means `/ai.something` becomes parseable; the
dispatcher rejects a suffix on a command that does not take one, so `/ai.foo bar` reports rather than
silently ignoring the suffix.

**Note for 008's `/link`**: `parse_line` is shared. Adding the suffix split affects `/link` only insofar as
`/link.foo` now reports an error instead of failing to parse — a strictly better message either way.

**Alternatives considered**:
- *A separate parser for `/task`.* Rejected by FR-002 and by 006's whole premise that in-editor commands
  share one framework.
- *Accept `/task followup call Terry` with a positional type.* Rejected: it diverges from the command bar,
  and it makes a one-word description ambiguous.

---

## R8: The capture sequence, and what happens when a step fails

**Decision**: Strict ordering, with the typed line untouched until everything that can fail has succeeded:

1. Reject an empty description before anything else — no save, no write (FR-007).
2. Save the document in its pre-command state (FR-005). Abort on failure; the line stays as typed.
3. `add_task(..., links=(source_id,))`. Abort on failure; the line stays as typed.
4. Build the mirror line: `relative_destination(source, tasks_file)` plus the task's id and text.
5. Replace the typed line with the mirror; move the cursor to its end; keep focus.

**Rationale**: Step 2 before step 3 is FR-005 and it is also what makes step 4 possible — the link's path
is derived from a file that exists. Step 3 before step 5 is what makes FR-009 true: there is no window in
which the user's words are gone and the task does not exist. The mirror is inserted as an ordinary buffer
edit and is therefore undoable (FR-014), which falls out of using the same `TextArea.replace` call `/ai`
uses (`edit_screen.py:_finish_request`).

**A document that has never been saved** cannot occur through the TUI — `open_editor` is always given a
path that exists — but the guard is cheap and the spec names the case.

---

## R9: Two mirrors of one task in one document

**Decision**: If two mirrors for the same task disagree with each other at save time, `tasks.md` is left
unchanged for that task and a warning names it (FR-025). If they agree, they are treated as one.

**Rationale**: There is no principled winner between two of the user's own edits, and picking one
arbitrarily would silently discard the other. Reporting is the behaviour Principle IV asks for everywhere
else in this codebase.

**On open** the question does not arise: the task's state is authoritative and both mirrors are corrected
to it.

---

## R10: `--link` validation and its exit code

**Decision**: `endpaper task add --link <id>` resolves each id with `resolve_id()` before creating
anything. An id that resolves to nothing exits **1** (not found) with a message naming it on stderr, and
no task is written.

**Rationale**: The constitution's exit-code contract is 0 success, 1 not found, 2 usage error, 3 workspace
error. An unresolvable id is a thing that is not there, not a malformed command line — `--link` was spelled
correctly and given a well-formed argument. `2` would be wrong and would be indistinguishable from a
genuine argument error to an assistant deciding what to retry.

**Repeatable**: `action="append"`, matching the existing `--tag`, which is the precedent an assistant will
already have learned.

**Deliberate asymmetry with the editor**: the editor writes a link to a document it just saved, so
resolution cannot fail there; the CLI takes an id from an untrusted argument, so it must check.

---

## R11: Propagation warnings never fail the operation

**Decision**: `task done`/`undone` exit 0 when `tasks.md` was written, even if a linked document could not
be. Warnings go to stderr (FR-032, FR-039).

**Rationale**: The operation the caller asked for — complete this task — succeeded. Exiting non-zero would
make an assistant believe the completion did not happen and retry it, which is worse than a stale mirror
that reconcile-on-open will fix. This differs from `links check`, which exits non-zero because reporting
unresolved links *is* its operation.

---

## R12: Performance, and what gets a test

**Decision**: One performance test, on reconcile-on-open, against SC-008's 50 ms budget. Nothing else here
gets one.

**Rationale**: Constitution VI: performance tests cover only scenarios with a real budget to protect.
Capture (SC-012, 200 ms) is one `tasks.md` parse plus one append — the same work `add_task` already does
and which `tests/performance/test_task_scan.py` already bounds. Toggle propagation is a handful of
`resolve_id` probes. Reconcile-on-open is the only new thing on a hot path, because it runs every time any
document is opened, and it is the one that has to prove it costs nothing when there is nothing to do.

**The measurement that matters** is the no-mirror case: a document with no mirrors must not read `tasks.md`
at all. That is asserted as behaviour (no file read), not only as a duration, because a duration assertion
on a fast machine would pass even if the read happened.

---

## Resolved unknowns

| Unknown | Resolution |
|---|---|
| Module for reconciliation logic | New `core/mirrors.py` (R1) |
| Mirror recognition rule | Checklist prefix + `find_links` fragment match (R2) |
| Documents touched by a toggle | The task's own `links:` ids, resolved (R3) |
| "Since they last agreed" | Session baseline held in `EditScreen`, passed into core (R4) |
| Whether `save_buffer` grows again | No — separate reconcile call, separate non-stamping writer (R5) |
| Reconcile-on-open call sites | `open_editor`, `open_task_editor`, `PreviewScreen`; no CLI counterpart exists (R6) |
| `/task.followup` parsing | `partition(".")` in `parse_line`, mirroring `command_bar.py:114` (R7) |
| Failure ordering during capture | Validate → save → add → build → replace (R8) |
| Two disagreeing mirrors | No write, warn (R9) |
| `--link` failure exit code | 1, not found (R10) |
| Propagation failure exit code | 0 with stderr warnings (R11) |
| Performance coverage | One test, reconcile-on-open, plus a no-read assertion (R12) |

No `NEEDS CLARIFICATION` items remain.
