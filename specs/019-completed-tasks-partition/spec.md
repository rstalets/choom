# Feature Specification: Completed Tasks Leave the Open List

**Feature Branch**: `019-completed-tasks-partition`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "issue #43. You are 019"

**Source**: GitHub issue #43 "[Feature]: Completed tasks should be stored outside tasks.md". Today a
completed task stays in `tasks.md` and is filtered out of the TUI. Over months of use the file fills
with lines nobody reads, and every assistant that opens it to find out what is outstanding pays for
all of them. The issue proposes that completing a task moves it to a completed-tasks file for the
day it was completed, that unmarking it moves it back, and that the "done" view scan all of those
files — acceptable because there will be far fewer of them than notes or meetings.

**Scope settled in investigation**: three shipped systems touch a task record's location, and each
one's answer is fixed here rather than left to the plan. They are, in order of how much they
constrain the design:

1. **Mirrors** (`core/mirrors.py`, spec 008) — a checklist item in a document whose link fragment
   names a task id. Moving the record changes what the link's *path* should say. §"Links and
   mirrors" settles this: `tasks.md` becomes the canonical address of the whole task collection,
   no mirror is ever rewritten because a task was completed, and no document choom did not open is
   written to.
2. **`ctrl+t` task deletion** (spec 017) — deletes a task record by id and refuses when the id
   cannot be resolved or the task list holds an unparseable line. §"Deleting a task (017)" settles
   this: 017's three refusal outcomes survive verbatim; only the corpus they are computed over
   widens.
3. **Reconcile-on-open** (`mirrors.reconcile_on_open`) — pushes task state into a document's
   mirrors when it is opened. §"Reconcile" settles this: it keeps working unchanged, because it
   already resolves by id and never consults a path.

---

## Overview

`tasks.md` is the one file in a choom workspace that only grows. Meetings and notes are partitioned
by `YYYY/MM/` so no directory accumulates forever; the task list has no such relief, and a completed
task is dead weight in it — invisible in the TUI, invisible in `choom task list`, and fully present
in every read of the file.

The cost lands hardest on the audience the CLI exists for. An assistant asked "what am I working
on?" reads `tasks.md`. After a year of daily use that read is mostly lines the answer does not
include. There is no filter it can apply before paying for them, because reading the file *is* the
filter.

This feature gives completed tasks the same treatment every other dated record in choom already
gets. Completing a task writes its record — the checkbox line and its indented body, byte for byte —
into a file for the day it was completed, and removes it from `tasks.md`. Reopening it moves it
back. `tasks.md` becomes what its name has always implied: the list of things still to do.

Three properties define the change, and every requirement below serves one of them:

1. **No line is ever lost.** A move is two writes to two files, and either one can fail. The
   destination is always written first, so the only failure state choom can land in is one where the
   line exists twice — a state that is loud, already detected, and recoverable by hand. A line that
   exists once is never the thing at risk.
2. **The move is invisible to everything that points at a task.** A task's id is permanent and
   authoritative; where its line currently sits is not addressable and never was. No document is
   rewritten, no link goes stale, and no mirror stops working.
3. **Nothing already in a user's workspace moves on its own.** A completed task sitting in
   `tasks.md` today is left exactly where the user has it, and still appears in every "done" view.
   choom does not sweep a vault it was not asked to sweep.

### Terminology

- **Open list** — `tasks.md`. Tasks not yet completed.
- **Done store** — the set of per-day files holding completed task records.
- **Task store** — the open list and the done store together. The complete set of task records,
  which is what "all tasks" has always meant.
- **Task record** — one checkbox line and the indented body beneath it. The unit that moves.
- **Mirror** (spec 008's word; **task line** in issue #79) — a checklist item in a document whose
  link fragment names a task id, e.g. `- [ ] [Buy coffee](../../tasks.md#task_a1b2)`. A control
  surface onto the task, not a copy of it.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The open list stays the open list (Priority: P1)

Someone has used choom daily for a year. They complete three tasks in the TUI with the space bar.
Each one leaves `tasks.md` as they press it. At the end of the year `tasks.md` holds the twenty
things they still owe someone, and nothing else. An assistant asked what is outstanding reads one
short file and answers from all of it.

**Why this priority**: This is the issue, in the shape the issue reports it. With this alone the
feature is worth having.

**Independent Test**: Complete a task through the CLI and through the TUI. `tasks.md` no longer
carries the line; a file under the done store does, byte-identical apart from the checkbox character
and the added completion date. `choom task list` does not show it. `choom task list --done` does.

**Acceptance Scenarios**:

1. **Given** an open task in `tasks.md`, **When** `choom task done <id>` runs, **Then** the record is
   in the done store file for today, is absent from `tasks.md`, and the command exits 0.
2. **Given** the same task, **When** `choom task list` runs, **Then** it is not listed and `tasks.md`
   is the only file read.
3. **Given** a task with an indented body, **When** it is completed, **Then** the body moves with it,
   with the same lines and the same relative indentation, and `choom task show <id>` prints the same
   body it printed before.
4. **Given** a task completed on 2 August, **When** the done store is inspected, **Then** its record
   is in the file for 2 August and its metadata comment carries `completed:2026-08-02`.

---

### User Story 2 - Unticking brings it back (Priority: P1)

Someone marks a task done, then realises they marked the wrong one. They press space again. The task
is in `tasks.md` again, in the open list, with its body and its tags and its links intact — and the
day file it briefly occupied no longer mentions it.

**Why this priority**: A move that only goes one way is a trapdoor. Reopening a task is an existing,
supported operation (`task undone`, space in the TUI, unticking a mirror and saving) and it cannot
become the operation that strands a record.

**Independent Test**: Complete a task, reopen it, and diff `tasks.md` against what it held before the
completion. The record is back; its `created`, `type`, `tags`, `links`, body, and id are unchanged.

**Acceptance Scenarios**:

1. **Given** a completed task in the done store, **When** `choom task undone <id>` runs, **Then** the
   record is appended to `tasks.md`, is absent from the done store, and carries no `completed:` field.
2. **Given** a done-store day file whose last record is reopened, **When** the move completes,
   **Then** the now-empty day file is left in place, empty — partitions are created on demand and
   never pruned (`docs/REQUIREMENTS.md` §3.2).
3. **Given** a task reopened and completed again on a later day, **When** it is completed, **Then**
   it lands in the later day's file, not the earlier one.

---

### User Story 3 - A note that mirrors a completed task still works (Priority: P1)

A meeting note from June holds `- [ ] [call Terry](../../../tasks.md#task_a1b2)`. Terry is called and
the task is completed from the tasks list. The note is not open. Weeks later the note is opened: the
box reads `[x]`. Nothing in the note was rewritten when the task completed, `choom links check`
reports nothing, and the link still resolves.

**Why this priority**: This is the property the feature could most easily break, and breaking it is
worse than not shipping. A mirror that silently stops tracking its task, or a completion that
rewrites files across the vault, are both unacceptable outcomes.

**Independent Test**: Capture a task into a document, complete it from the tasks list without opening
the document, then open the document. The mirror reads `[x]`, its bytes changed only in the state
character written by reconcile, and `choom links check` reported nothing between the two steps.

**Acceptance Scenarios**:

1. **Given** a completed task and a document mirroring it, **When** the document is opened,
   **Then** the mirror is corrected to `[x]` and no dead-link warning is produced.
2. **Given** the same pair, **When** `choom links check` runs, **Then** the mirror is reported neither
   stale nor dead.
3. **Given** the same pair, **When** the user unticks the mirror and saves the document, **Then** the
   task moves back to `tasks.md` and the save writes exactly two files: the document and the store.
4. **Given** a completion, **When** it happens, **Then** no file outside the task store is written
   except the documents the task's own `links:` field names, which is the already-shipped
   `propagate_to_documents` behaviour and is unchanged by this feature.

---

### User Story 4 - Deleting a task that is already done (Priority: P2)

Someone opens a June meeting note, finds a checklist item for a task that was completed and should
never have been captured at all, puts the cursor on it and presses `ctrl+t`. The confirmation names
the task. They confirm; the line leaves the note and the record leaves the done store.

**Why this priority**: `ctrl+t` shipped tonight (spec 017) and it resolves the record in `tasks.md`.
Left alone, it would find nothing for a completed task, take 017's `line_only` path, delete the
document line and leave the record behind — a silent orphan created by a key whose entire promise is
that it removes both halves.

**Independent Test**: Complete a task that has a mirror, press `ctrl+t` on the mirror, confirm. The
line is gone from the document and the record is gone from the done store.

**Acceptance Scenarios**:

1. **Given** a mirror of a completed task, **When** `ctrl+t` is pressed on it, **Then** the
   confirmation names the task and the outcome is `deletable`, not `line_only`.
2. **Given** a mirror whose id is in neither the open list nor the done store, **When** `ctrl+t` is
   pressed, **Then** the outcome is 017's `line_only` — the document line goes, nothing else does.
3. **Given** `choom task delete <id>` for a completed task, **When** it runs, **Then** the record is
   removed from the done store and the command exits 0.

---

### User Story 5 - The workspace someone already has (Priority: P2)

Someone upgrades. Their `tasks.md` holds four hundred lines, three hundred of them completed. Nothing
happens to the file. The TUI's Done view shows those three hundred exactly as it did before, the
Todo view shows the hundred exactly as it did before, and the only change they notice is that the
next task they complete leaves the file.

**Why this priority**: The alternative — rewriting three hundred lines of a user's own file the first
time they launch a new version — is a vault-wide unprompted write, which Principle IV does not
permit and which no amount of correctness would make trustworthy.

**Independent Test**: Populate `tasks.md` with a mix of open and completed lines, run every read and
write command, and confirm no completed line moved that the user did not act on.

**Acceptance Scenarios**:

1. **Given** completed tasks in `tasks.md`, **When** choom is launched, listed, filtered, scanned for
   links, or used to open a document, **Then** none of those lines moves and `tasks.md` is not
   rewritten.
2. **Given** those tasks, **When** `choom task list --done` runs, **Then** they are listed alongside
   anything in the done store, as one list.
3. **Given** one of them, **When** it is reopened and then completed again, **Then** *that* record
   moves — a real state transition is what moves a record, and the only thing that does.

---

### User Story 6 - Tidying an old list on purpose (Priority: P3)

Someone with the four-hundred-line `tasks.md` above decides they want it cleaned up, and says so
explicitly. One command moves every completed record it can safely read into the done store, reports
what it moved and what it left, and touches nothing else.

**Why this priority**: Wanted, but strictly optional — Story 5 already leaves those users correct and
unharmed. This is the escape hatch for the user who asks, and it must never run on its own. Drop it
without affecting anything above.

**Independent Test**: Run the sweep on a mixed `tasks.md`; completed records with a readable metadata
comment move, everything else stays, and the report names both groups.

**Acceptance Scenarios**:

1. **Given** a `tasks.md` with completed and open tasks, **When** the sweep runs, **Then** only
   completed, parseable records move, and the count of each is reported.
2. **Given** a completed record with no `completed:` field, **When** the sweep moves it, **Then** its
   `created` date decides the day file it lands in, since that is the only date the record carries.
3. **Given** the sweep, **When** it is not explicitly invoked, **Then** it never runs — no launch, no
   read command, and no write command triggers it.

---

### Edge Cases

**The move itself**

- A task completed at 00:00:30 and one completed at 23:59:30 on the same day land in the same file.
  The day comes from the local wall clock at the moment of the write, the same clock `created` uses.
- Completing a task that is already complete is a no-op: no write to either file, matching
  `set_task_state`'s existing no-op-on-same-state behaviour.
- A task whose id appears twice is already an error (`UsageError`, naming the lines). It stays one,
  and the message now names files as well as lines.
- Two tasks completed in the same second both land in the same day file, appended in call order.

**Partial failure**

- The done store write fails (unwritable directory, full disk): `tasks.md` is not touched, the
  command fails, and the task is still open. Nothing moved and nothing is lost.
- The done store write succeeds and the `tasks.md` write fails: the record now exists in both files.
  This is reported, and it is the already-defined duplicate-id state — `resolve_id` warns
  `link_ambiguous`, `get_task`/`set_task_state`/`delete_task` refuse with `UsageError` naming both
  locations, and `ctrl+t` refuses with 017's `ambiguous_id`. The user deletes one copy by hand. No
  line was lost, and no operation proceeds on a record it cannot uniquely identify.
- The process is killed between the two writes: identical to the case above. Both files are written
  atomically and individually; there is no cross-file transaction and this feature does not invent
  one.

**Lines that do not move**

- A task line whose metadata comment is malformed or unterminated produces no record at all today —
  `parse_tasks` warns and skips it. It cannot be completed, so it cannot move, and it stays exactly
  where the user typed it.
- A checkbox line with no metadata comment gets an id backfilled by `load_tasks` before anything can
  act on it, exactly as today; it then moves like any other record.
- Anything in `tasks.md` that is not a task line — a heading, prose, a blank line, an ordinary
  checklist item the user wrote — is never read, never moved, and never rewritten by a move.
- A record whose `created` value is invalid still moves; the invalid value travels with it verbatim,
  and the completion day is decided by the clock, not by `created`.

**The done store**

- A user hand-edits a done-store file, adds a task line, or unticks one: the record is read like any
  other. An open (`[ ]`) record found in the done store is listed as open and is not moved back —
  choom does not relocate a record to agree with its own filing.
- A record found in the day file for 12 June whose `completed:` field says 3 May lists as completed
  on 3 May. The field is authoritative; the path is not (Principle IV, `docs/REQUIREMENTS.md` §3.2).
- A done-store file that cannot be read or parsed produces a warning naming it and does not prevent
  the rest of the store from listing.
- An empty done-store day file is legal and is left alone.

**Interaction with mirrors**

- A mirror whose task has been completed and whose document is opened has its box ticked. A mirror
  whose task has been *deleted* is dead, warned about, and left byte-identical — unchanged from today,
  but now decided after both halves of the store have been consulted, not one.
- Unticking a mirror in a document and saving moves the record back to `tasks.md`; ticking one moves
  it into the done store. The save path already routes through `set_task_state`, so it inherits the
  move without a second implementation of it.
- Two mirrors of one task disagreeing is still `mirror_ambiguous` and still writes nothing.

---

## Requirements *(mandatory)*

### Functional Requirements

**The done store and its layout**

- **FR-001**: Completed task records MUST live in per-day files under a new collection root,
  `tasks/done/YYYY/MM/YYYY-MM-DD-done.md`, where the date is the day the task was completed.
- **FR-002**: A done-store file MUST have exactly the format of `tasks.md` — task lines with trailing
  metadata comments and optional indented bodies, no frontmatter — so `parse_tasks` reads it
  unchanged and a human or an assistant opening one needs no new knowledge to read or edit it.
- **FR-003**: Done-store partitions MUST be created on demand and MUST NOT be pruned, matching every
  other partitioned collection.
- **FR-004**: The task metadata comment MUST gain one field, `completed:<YYYY-MM-DD>`, written after
  `created`. It MUST be present on every record choom moves into the done store, MUST be removed when
  a record moves back to the open list, and MUST be treated exactly as `created` is when its value is
  unparseable — a warning, with the record still returned.
- **FR-005**: A record's location MUST NOT be authoritative for anything. Its completion date comes
  from `completed:`, its state from its checkbox, its identity from its id. A record filed in the
  "wrong" day file still lists correctly and MUST NOT be moved to correct its filing.

**Completing and reopening**

- **FR-006**: Marking a task complete MUST move its record — the checkbox line and its whole body
  span — out of `tasks.md` and into the done store file for the current day, and MUST set the
  checkbox to `x` and stamp `completed:`.
- **FR-007**: Marking a task incomplete MUST move its record out of the done store and append it to
  `tasks.md`, set the checkbox to a space, and drop `completed:`.
- **FR-008**: The moved lines MUST be byte-identical to the lines removed, apart from the checkbox
  character, the `completed:` field, and the destination file's own line-ending convention. Relative
  indentation of the body MUST be preserved. No re-rendering of the task text, tags, links, or body.
- **FR-009**: Setting a task to the state it already has MUST write nothing, in either direction.
- **FR-010**: Both directions MUST go through the single existing core entry point that both
  front-ends already call for this (`tasks.set_task_state`), so the CLI, the TUI's space bar, and a
  mirror save can never diverge on where a record ends up.

**Never losing a line (Principle IV)**

- **FR-011**: A move MUST write the destination file first and the source file second, in both
  directions. The reverse ordering can lose a line to a single failed write; this ordering cannot.
- **FR-012**: If the destination write fails, the source MUST NOT be touched and the operation MUST
  fail with a `WorkspaceError` naming the file. The task stays in the state it was in.
- **FR-013**: If the destination write succeeds and the source write fails, the operation MUST report
  the failure, naming both files and stating that the record now exists in both and that one copy
  must be removed by hand. It MUST NOT retry, MUST NOT roll back by deleting what it just wrote, and
  MUST NOT exit as if the move succeeded.
- **FR-014**: A record found in both the open list and the done store MUST be treated as the existing
  duplicate-id condition: `resolve_id` warns `link_ambiguous`; `get_task`, `set_task_state`, and
  `delete_task` raise `UsageError`; `ctrl+t` returns 017's `ambiguous_id`. Every such message MUST
  name the file as well as the line.
- **FR-015**: Each of the two writes MUST be individually atomic, through the existing
  `atomic_write` primitive. No new write mechanism, no lock file, no journal.
- **FR-016**: A line that `parse_tasks` cannot turn into a record MUST NOT move, MUST NOT be
  rewritten, and MUST NOT prevent any other record from moving.

**Reading the store**

- **FR-017**: Core MUST expose the open list, the done store, and their union as three distinct
  reads, so that every call site states which one it wants and no caller's cost changes by accident.
- **FR-018**: The open-tasks view — `choom task list` with no flags, and the TUI's Todo category —
  MUST read `tasks.md` and nothing else, whatever the size of the done store.
- **FR-019**: `choom task list --done` and the TUI's Done category MUST show the union of completed
  records in the done store and completed records still in `tasks.md`, as one list, sorted by the
  existing rule.
- **FR-020**: `choom task list --all` MUST show the whole store.
- **FR-021**: `choom task show <id>`, `choom task delete <id>`, `choom task done/undone <id>`, and id
  resolution MUST find a record wherever it lives, searching `tasks.md` first and the done store
  second.
- **FR-022**: A done-store file that cannot be read or parsed MUST produce a warning naming it and
  MUST NOT prevent the remaining files, or `tasks.md`, from being read.
- **FR-023**: Id backfill (writing an id onto a checkbox line that has none) MUST continue to apply to
  `tasks.md`. It MUST also apply to a done-store file when one is read and found to carry an
  id-less checkbox line, on the same best-effort terms: if the write fails, the read still succeeds
  with a warning.

**Links and mirrors (the central decision)**

- **FR-024**: `tasks.md` MUST be the canonical address of the task collection for link purposes. A
  link to a task id MUST derive its path as the path to `tasks.md`, whichever file currently holds
  the record. Completing or reopening a task therefore changes no link's correct destination, makes
  no link stale, and requires no document to be rewritten.
- **FR-025**: No completion or reopening MUST EVER write to a document that the user did not open,
  beyond the mirror state splices `propagate_to_documents` already performs for documents named in
  the task's own `links:` field — behaviour that predates this feature and is unchanged by it.
- **FR-026**: `choom links check` MUST NOT report a mirror as stale or dead because its task is
  completed. `choom links heal` MUST NOT rewrite one.
- **FR-027**: Mirror recognition MUST remain purely by id fragment. No code path may decide whether a
  checklist item is a mirror, or which task it names, by inspecting its path.
- **FR-028**: `choom links check`, `choom links heal`, `choom links <id>`, and inbound-link scanning
  MUST cover the done store — ordinary markdown links in a completed task's text or body, and ids in
  its `links:` field, are still links and MUST NOT stop being checked because the task completed.

**Reconcile**

- **FR-029**: Reconcile-on-open MUST resolve a mirror's id against the whole store, so a mirror of a
  completed task is corrected to `[x]` rather than reported dead.
- **FR-030**: Reconcile-on-open MUST NOT read the done store when no outcome could depend on it. A
  document whose mirrors all resolve in `tasks.md` MUST cost exactly one file read, as it does today.
- **FR-031**: Reconcile-on-save MUST route a state change through the same move path, so ticking a
  mirror and saving moves the record into the done store and unticking one moves it back. The
  baseline/conflict matrix in `specs/008-document-links/contracts/mirror-format.md` is unchanged.
- **FR-032**: A save that moves a record MUST NOT stamp `updated` on any document as a side effect of
  the move. The existing non-stamping sync path is unchanged.

**Deleting a task (017)**

- **FR-033**: `plan_mirror_deletion` MUST resolve the mirror's id against the whole store. A mirror
  of a completed record MUST plan as `deletable`, not `line_only`.
- **FR-034**: 017's refusal outcomes MUST hold unchanged in substance: `self_referential`,
  `ambiguous_id`, `unreadable_tasks`, `line_only`, `deletable`. Only the corpus they are computed
  over widens from `tasks.md` to the whole store.
- **FR-035**: `unreadable_tasks` MUST fire when the id resolves to nothing **and** a file that was
  actually read during that resolution holds a line `parse_tasks` could not read. The message MUST
  name that file and line, so the refusal is actionable rather than a standing veto from an old
  day file the user has never seen.
- **FR-036**: `choom task delete <id>` and the TUI's list-view delete MUST remove a completed record
  from the done store, reporting the file it was removed from.

**Migration**

- **FR-037**: Completed tasks already in `tasks.md` MUST be left in place. No launch, read, scan,
  filter, or unrelated write may move them.
- **FR-038**: Those tasks MUST continue to appear in every "done" view, with no `completed:` field
  and therefore no completion date, sorting by the existing rule.
- **FR-039**: A completed task in `tasks.md` MUST move only when the user drives a real transition on
  it (reopen, then complete) or explicitly invokes the sweep of FR-040.
- **FR-040** *(P3, droppable)*: An explicitly-invoked, non-interactive sweep MUST be available that
  moves every parseable completed record out of `tasks.md` into the done store, reporting the number
  moved and the number left with the reason. It MUST NOT prompt, MUST NOT run implicitly, and MUST
  follow FR-011's write ordering for every record it moves.

### Interface parity (constitution Principle II)

Every command below already exists. This feature changes behaviour, not surface: it adds no command,
no flag, and no exit code, and it renames and removes no JSON key.

| Command | Changes? | What changes |
|---|---|---|
| `choom task add` | No | Always writes to `tasks.md`; a new task is never complete. |
| `choom task list` | No | Same output, same cost — one file, per FR-018. |
| `choom task list --done` | Yes | Now the union of the done store and any completed lines still in `tasks.md`. Output shape unchanged. |
| `choom task list --all` | Yes | Now reads the whole store. Output shape unchanged. |
| `choom task show <id>` | Yes | Finds a completed record wherever it lives. Output shape unchanged apart from the new keys below. |
| `choom task done <id>` | Yes | Moves the record. Exit code, propagation, and warning behaviour unchanged. |
| `choom task undone <id>` | Yes | Moves the record back. Same. |
| `choom task delete <id>` | Yes | Deletes from wherever the record lives. Same. |
| `choom links check` / `heal` | Yes | Also cover the done store (FR-028); report no new staleness (FR-026). |
| `choom links <id>` | Yes | Also scans the done store for inbound task-field links. |

**`--json` schema.** Two keys are **added** to the task record emitted by `task list --json`,
`task show --json`, and `task add --json`:

- `completed` — the ISO completion date, or `null`.
- `file` — the store file holding the record, workspace-relative POSIX (`tasks.md` or
  `tasks/done/2026/08/2026-08-02-done.md`). Required because the existing `line` key is a line number
  within a file, and without `file` it is now ambiguous.

Every existing key — `id`, `text`, `done`, `type`, `tags`, `links`, `created`, `line`, `body` — keeps
its name, its type, and its meaning. Adding a key is a minor change; nothing here is breaking. The
`task done`/`task undone` `--json` object likewise keeps `id`, `done`, `links`,
`documents_updated`, `warnings` and gains `file`.

**Exit codes** are unchanged: 0 success, 1 not found, 2 usage error, 3 workspace error. A partial
failure (FR-013) is a workspace error, code 3.

**TUI parity.** The Todo and Done categories keep their current keys, their current footer, and their
current behaviour. Space still toggles; the row leaves the Todo list and appears in the Done list, as
it already does. `ctrl+d` in the list view and `ctrl+t` in the editor keep their bindings and their
confirmations. No new key is bound and no new screen is added.

### Layering (constitution Principle I)

**`choom.core` owns**, callable with a workspace and no terminal, TTY, or event loop:

- resolving the done-store path for a date, and enumerating the store;
- reading the open list, the done store, and their union (FR-017);
- the move itself, in both directions, including the write ordering, the `completed:` stamp, the
  body span, and the duplicate-id outcome (FR-006 – FR-016);
- id resolution across the store, and the canonical-address rule for task links (FR-021, FR-024);
- the sweep of FR-040.

**The adapters own**: printing, the `--json` serialisation of the two new keys, the Done category's
row rendering, and the existing confirmations. Neither adapter may compute a done-store path, decide
where a record goes, or write a task file directly.

### Constitution notes

**Principle III — the directory-layout invariant.** `tasks/done/YYYY/MM/` encodes date, and only
date, *within* the collection. `done` is a collection root, in the same position as `meetings/`,
`notes/`, and `notes/daily/` — not an axis inside one, and not a `type`. A task's `type` is
free-form and user-invented (`followup`, `call`, …) and stays exactly where it is today, in the
metadata comment, never in a path. The harm the invariant names — "a directory per type would
fragment the vault into a long tail of one-file folders" — cannot occur here: completion is binary,
every record has exactly one value of it, and the two values map to two fixed locations that exist
regardless of what the user invents. `docs/REQUIREMENTS.md` §3.2's test for adding a collection is
met: a real, distinct need existing collections do not serve, and the same `YYYY/MM` date
partitioning as the rest, so no reindex and no migration risk. The invariant holds; this is a
deliberate collection addition, and `docs/REQUIREMENTS.md` §3.2 must list it when the work lands.

**Principle IV — never lose the user's words.** Four rules carry the weight. FR-011's ordering means
the only reachable failure state duplicates a line rather than dropping one. FR-016 means a line
choom cannot parse is never moved or rewritten. FR-037 means no vault is swept unprompted. FR-005
means location is never authoritative, so a record the user files "wrongly" still reads correctly and
is never relocated to agree with choom — the same rule that already governs a meeting note filed
under the wrong month. The one thing this feature does that IV's text speaks to directly is move a
*record* between two choom-managed files; it never moves a *file*, and it never relocates anything
the user authored outside the task store.

**Principle V.** No new binding, no new screen, no new confirmation. The one new user-visible
message is FR-013's partial-failure report, which names both files and what to do about it.

### Key Entities

- **Done store file** — one per day on which at least one task was completed. Path
  `tasks/done/YYYY/MM/YYYY-MM-DD-done.md`. Contents: task lines in `tasks.md` format. No frontmatter,
  no id of its own; it is a container, not a record.
- **Task record** — unchanged, plus one optional field: `completed`, an ISO date, present only while
  the record is complete.
- **Task store** — the pair (open list, done store). Not a new object on disk; the name for what "all
  tasks" reads.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After completing a task, `tasks.md` contains no line mentioning that task's id, and
  exactly one done-store file does.
- **SC-002**: Round-tripping a task with a body, tags, links, and a type through complete → reopen
  returns `tasks.md` to a state that differs from the original only in the record's position in the
  file.
- **SC-003**: `choom task list` opens exactly one file, asserted by counting reads, with 1,000
  completed records spread over 365 done-store files present. Counting, not timing — the house
  technique established in `tests/performance/test_reconcile_open.py`.
- **SC-004**: Opening a document whose mirrors all name open tasks costs exactly one file read,
  preserving spec 008's SC-008 unchanged.
- **SC-005**: Reading the whole store completes in under 500 ms for a done store of 1,000 day files
  holding 5,000 records, measured best-of-5 on the reference machine. This is the budget the issue's
  "relatively safe" assertion has to survive, and the Done view and every id resolution pay it.
- **SC-006**: No completion or reopening writes any file outside the task store and the documents
  named in the task's own `links:` field — asserted by watching writes across the workspace, not by
  inspection.
- **SC-007**: With the done-store write forced to fail, `tasks.md` is byte-identical afterwards and
  the task is still open. With the `tasks.md` write forced to fail after a successful done-store
  write, both copies exist, the failure is reported naming both files, and no subsequent command acts
  on the ambiguous id without refusing.
- **SC-008**: A workspace whose `tasks.md` carries 300 completed lines is byte-identical after launch,
  every read command, a document open, and a link check.
- **SC-009**: `choom links check` reports zero stale and zero dead links across a workspace where
  every task has been completed.
- **SC-010**: Every existing `--json` key for a task keeps its name and meaning; the contract tests
  that assert the schema pass unchanged, with the two added keys covered by new assertions.

**On SC-005 and the refresh tick.** The TUI's list screen re-reads every `REFRESH_SECONDS` (2.0) on
Textual's main thread, so the Done category's read is frame budget, not background CPU — the concern
`tests/performance/test_refresh_tick.py` already documents for `scan_month`. A store scan at the
SC-005 ceiling would drop a frame on each tick while the Done view is displayed. If the budget is
breached, or if the tick proves visibly janky on the target terminals, the first remedy is to scope
the Done view by month using the machinery the Meetings and Notes panes already have — which reduces
the scan to one `YYYY/MM` directory — not to add an index or a cache (Principle III). Choosing
between that and moving the tick's read to a worker is plan work, not spec work.

---

## Assumptions

- **The completion day is the local wall-clock day at the moment of the write**, from the same clock
  `created` already uses. No timezone handling is introduced, and no test may depend on a literal
  date (Principle VI).
- **`tasks/` as a directory alongside `tasks.md` is acceptable.** It groups everything about tasks
  under one name and mirrors `notes/daily/`'s shape. The alternative considered was a top-level
  `done/`; the choice affects one constant and is cheap to overturn before implementation, but is
  settled here so the plan does not reopen it.
- **`YYYY-MM-DD-done.md`, not `YYYY-MM-DD.md`**, so a file dragged out of the vault still says what
  it is — `docs/REQUIREMENTS.md` §3.2's stated reason for keeping the full date in a filename that
  already sits in a dated directory.
- **Adding `completed:` to the metadata comment is a one-way format change.** An older choom reading
  a newer workspace classifies a comment with an unrecognised key as malformed and skips that line,
  so completed records would be invisible (not lost) to a downgraded install. choom offers no
  cross-version file compatibility guarantee today and this feature does not create one; the
  alternative — deriving the completion date from the containing file's name — was rejected because
  it makes location authoritative, which Principle IV forbids.
- **The done store is small relative to the vault.** The issue's own premise: far fewer day files than
  notes or meetings. SC-005 is the assertion that turns that premise into a check.
- **Users hand-edit done-store files.** They are ordinary markdown in a format the user already
  knows, so every read path treats a hand-edit as the normal case, not as corruption.

## Out of Scope

- Scoping the Done view by month. Named above as the remedy if SC-005 is breached; not built here.
- Any index, cache, or manifest of the done store (Principle III).
- Archiving, compacting, or deleting old done-store files. Partitions are never pruned.
- A `completed` filter, sort, or date-range flag on `task list`. The union view keeps today's
  ordering.
- Purging or rewriting the `completed:` field on records the user hand-writes it onto.
- Any change to how tasks are captured, edited, tagged, linked, or displayed while open.

## Dependencies

- **Spec 003 (tasks)** — the task line format, the parser, and `set_task_state`, whose contract this
  extends.
- **Spec 007 (task content editing)** — the body span, which is the unit that moves with a record.
- **Spec 008 (document links)** — mirrors, reconcile-on-open, reconcile-on-save, and the id-first
  resolution rule this feature leans on entirely.
- **Spec 017 (editor task delete)** — `plan_mirror_deletion`'s outcomes, widened by FR-033 – FR-035.
- **`docs/REQUIREMENTS.md` §3.2 and §3.3** — the layout and link conventions. §3.2 gains the new
  collection and the `completed:` field; §3.3 gains the canonical-address rule of FR-024. Both edits
  land with the implementation, per CLAUDE.md's exemption for contributor-facing docs.
- **`AGENTS.md.tmpl`** — an assistant needs to know where completed tasks live and that `tasks.md` is
  the open list. One or two lines, inside the ~100-line budget.
