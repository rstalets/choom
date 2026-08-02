# Phase 0 Research: Completed Tasks Leave the Open List

**Feature**: `019-completed-tasks-partition` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

Every decision below was taken against the installed source on `release/v0.0.4`, not from memory.
Line references are to that tree.

---

## R1 — Where the done store lives, and what creates it

**Decision**: `tasks/done/YYYY/MM/YYYY-MM-DD-done.md`, one file per day on which at least one task
was completed. The path is a pure function of the record's `completed` date. `done` is a collection
root in the same position as `meetings/`, `notes/`, and `notes/daily/`.

**Rationale**: `docs/REQUIREMENTS.md` §3.2 gives the test for adding a collection — "a real, distinct
need existing collections don't serve" plus "MUST fit the same `YYYY/MM` date partitioning as the
rest". Both hold. Inside the collection, date is the only axis, so Principle III's layout invariant
is untouched: a task's `type` (`followup`, `call`, …) stays in its metadata comment and never becomes
a directory.

**Directory creation is already free.** `atomic_write.write_text_atomic` does
`path.parent.mkdir(parents=True, exist_ok=True)` before every write
(`src/choom/core/atomic_write.py:30`). FR-003's "created on demand" needs no new code and no
`mkdir` call anywhere in this feature.

**Windows path budget**: `tasks/done/2026/08/2026-08-02-done.md` is 40 characters below the workspace
root, against §3.2's worst-case generated path of 115 and the 260-character limit. Comfortable.

**Alternatives considered**:

- **Top-level `done/`** — shorter, and matches the TUI's category name. Rejected on legibility: an
  assistant landing in a workspace reads `tasks/done/` as unambiguously about tasks, where a bare
  `done/` invites "done what?". A `tasks/` directory sitting beside `tasks.md` is legal on every
  supported filesystem and mirrors the `notes/` + `notes/daily/` shape already in the tree.
- **A single `tasks-done.md`** — no partitioning, one file. Rejected: it reintroduces the
  unbounded-growth problem this feature exists to solve, one file later.
- **A `done: true` frontmatter axis with no move at all** — i.e. leave everything in `tasks.md` and
  make the CLI smarter. Rejected: it does not shrink the file, which is the entire ask.
- **`YYYY-MM-DD.md` (the `notes/daily/` filename shape)** — rejected in favour of
  `YYYY-MM-DD-done.md` for §3.2's own stated reason: "A file that is copied, attached to an email, or
  dragged out of the vault must still say what it is."

---

## R2 — The move is two splices, never a re-render

**Decision**: moving a record copies its raw lines verbatim. Exactly two edits are applied to the
checkbox line, both byte-level splices at computed offsets:

1. the state character, at `_TASK_LINE.span("state")` — the identical one-character edit
   `set_task_state` already performs (`tasks.py:614-616`);
2. the `completed:` field, spliced into the metadata comment's inner body.

Body-span lines are copied with no edit at all.

**Rationale**: FR-008 requires the moved lines to be byte-identical apart from those two changes, and
the alternative cannot deliver that. Re-rendering through `render_task_line` would normalise field
spacing, drop any unrecognised-but-harmless whitespace the user typed, and re-emit the description
from the parsed `text` rather than the source bytes. Every write path in this codebase is already a
splice for exactly this reason — `Mirror.state_offset`, `Link.start`/`end`, `heal_text`'s
"byte-level splice" contract, and `delete_task`'s "every line outside the removed span is
byte-identical". A re-render here would be the one exception, in the one operation that touches two
files at once.

**The `completed:` splice, stated precisely.** `_split_comment` (`tasks.py:25-37`) already locates
the last `<!-- … -->` on the line and returns its inner body `B`. The insert is
`B.rstrip() + " completed:<ISO>" + <the whitespace B originally ended with, or " ">`. This appends
after `created`, matching §3.2's declared field order, preserves the user's own leading and trailing
spacing inside the comment, and touches nothing before the comment. The removal (on reopen) drops
the first `completed:…` token and the single space that precedes it.

**Unreachable-by-construction cases.** A line with no metadata comment, or with a "bare" one, parses
to `id=None` and can never match `t.id == task_id`, so the splice never runs against a line that has
no comment to splice into. A malformed or unterminated comment produces no `Task` at all
(`tasks.py:239-274`), so FR-016 holds for free rather than by a check that could be forgotten.

**Alternatives considered**: `delete_task` + `add_task`. Rejected — `add_task` mints a *new* id and
re-renders the line, so it would change the record's identity and break every mirror pointing at it.

---

## R3 — Write ordering, and the only failure state that is reachable

**Decision**: destination first, source second, in both directions. Two independent
`write_text_atomic` calls. No lock file, no journal, no cross-file transaction.

**Rationale**: there are only two orderings and one of them can lose a line.

| Ordering | Failure between the writes | Outcome |
|---|---|---|
| source first, destination second | destination write fails | **the record is gone from both files** |
| destination first, source second | source write fails | the record exists in **both** files |

The second failure is loud, already detected, and recoverable by hand; the first is silent data loss.
Principle IV does not treat that as a close call.

**The duplicate state is not new machinery.** A task id carried by two records is already a defined,
handled condition throughout the tree: `get_task`, `set_task_state`, `delete_task`, and
`set_task_body` all raise `UsageError` naming the conflicting lines (`tasks.py:545-550`, `598-603`,
`636-640`, `691-696`); `resolve_id` emits `link_ambiguous` naming every path
(`links.py:653-661`); `plan_mirror_deletion` returns `ambiguous_id` (`mirrors.py:424-437`); and
`delete_by_id` re-raises the ambiguity as a `UsageError` (`deletion.py:53-55`). A partial move lands
in that state and every subsequent operation refuses rather than acting on a record it cannot
uniquely identify. This feature adds no new recovery path — it adds file names to the existing
messages (R7) and stops.

**Not addressed, deliberately**: the read-then-write window. `delete_task`, `set_task_state`, and
`set_task_body` all re-read and re-parse immediately before writing but cannot prevent a concurrent
external edit landing between the read and the `os.replace`. The move inherits that window and does
not widen it — it is one more `write_text_atomic` on a second file, not a longer hold on the first.
Closing it would mean file locking, which is out of scope and would be a new source of truth in a
OneDrive-synced directory.

---

## R4 — Which loader each call site gets

**Decision**: three explicit core reads, and every existing call site reassigned by hand rather than
inheriting a silent change of meaning.

| Function | Reads | Notes |
|---|---|---|
| `load_tasks(workspace)` | `tasks.md` only | **Unchanged in meaning and cost.** Every property its callers rely on today survives. |
| `load_done_tasks(workspace)` | the done store | New. Returns records plus warnings, one warning per unreadable file. |
| `load_task_store(workspace)` | both, `tasks.md` first | New. The union. |

**Call-site audit** (every current caller of `load_tasks`, from `grep`):

| Call site | Gets | Why |
|---|---|---|
| `cli.main._cmd_task_list`, no flags | `load_tasks` | FR-018 — the open view must stay one file read. |
| `cli.main._cmd_task_list --done` / `--all` | `load_task_store` | FR-019, FR-020. |
| `tui.app.visible_tasks`, Todo category | `load_tasks` | FR-018, and it runs on the 2-second tick (R10). |
| `tui.app.visible_tasks`, Done category | `load_task_store` | FR-019. |
| `tasks.get_task` | `load_task_store` | FR-021. |
| `tasks.set_task_state` | both, escalating | The record may be in either file; it must find it to move it. |
| `tasks.delete_task` | both, escalating | FR-036. |
| `links.resolve_id` (`task` pool) | both, escalating | FR-021. `tasks.md` first; the store only on a miss. |
| `links._task_field_reports`, `_all_task_field_links` | `load_task_store` | FR-028 — a completed task's `links:` field is still a link. |
| `links._iter_target_paths` | + the store's files | FR-028 — markdown links in a completed task's body are still links. |
| `links.link_candidates` | `load_tasks` | **Deliberately unchanged.** The `/link` picker offers open tasks. Adding every completed task would grow the candidate list without bound and offer, as the common case, links to work that is finished. Behaviour is identical to today. |
| `mirrors._load_tasks_or_warning` | escalating (R5) | FR-029, FR-030. |

**Rationale for three functions rather than a flag**: `load_tasks(workspace, include_done=True)`
would leave every existing call site silently changed in cost and meaning by a default, which is
precisely how FR-018 gets lost in a later refactor. Three names make each call site state its intent,
and make the audit above mechanically checkable.

---

## R5 — Reconcile-on-open: the escalation rule

**Decision**: `reconcile_on_open` reads `tasks.md` first, exactly as today. It reads the done store
**at most once**, and only when at least one mirror in the document names an id that `tasks.md` does
not carry.

**Rationale**: this is the fix for bug 2. Today `_load_tasks_or_warning` calls `load_tasks` and
`reconcile_on_open` treats any unresolved id as **dead** (`mirrors.py:587-591`) — leaves the box
byte-identical and warns. Once completed records live elsewhere, every mirror of a completed task
would take that branch: the box would stay `[ ]` forever and the user would collect a dead-link
warning per completed task, per open. That is a regression this feature introduces, and it is
strictly worse than today's behaviour.

The escalation rule is the cheapest correct one. A mirror whose id *is* in `tasks.md` needs nothing
further. A mirror whose id is not could be either completed (tick it) or genuinely deleted (warn),
and those two outcomes are indistinguishable without reading the store — so an outcome does depend on
the read, and FR-030's condition is met. A document whose mirrors all name open tasks reads one file
and nothing else, which is spec 008's SC-008 preserved verbatim (SC-004).

**Considered and rejected**: skipping the store read when every unresolved mirror already reads
`[x]`, on the grounds that the text cannot change either way. It is true of the *text* and false of
the *warnings* — it would emit "does not resolve" for every completed mirror, which is the bug in a
quieter register. A correctness rule is not worth trading for one avoided read.

**Reconcile-on-save** needs no separate rule. It already routes state changes through
`set_task_state` (`mirrors.py:730`), so it inherits the move, and it uses the same
`_load_tasks_or_warning` helper, so it inherits the escalation.

---

## R6 — `plan_mirror_deletion` and 017's refusal rules

**Decision**: `plan_mirror_deletion` resolves against the whole store. `unreadable_tasks` is scoped
to files that were actually read during that resolution.

**The bug, precisely.** `plan_mirror_deletion` opens `workspace.tasks_file` directly
(`mirrors.py:397-421`) and matches `t.id == mirror.task_id` against `parse_tasks(raw)`. For a
completed task the id is not there, `parsed.warnings` is clean, and the function falls through to
`line_only` (`mirrors.py:466-473`) — "no record exists". The TUI then deletes the document line and
`commit_mirror_deletion` returns without touching anything (`mirrors.py:498-499`). Net result: the
line the user pointed at is gone and the record survives, unreferenced, in the done store. That is
silent data divergence produced by a key whose stated promise (017 spec, §Overview) is that it
removes both halves.

**The fix**: the same read, widened. `tasks.md` first — unchanged, including the deliberate use of
`parse_tasks` rather than `load_tasks` so the plan step never writes (017 FR-014) — then the done
store on a miss, read the same way, with the same no-write discipline. All five outcomes keep their
meaning:

| Outcome | Change |
|---|---|
| `self_referential` | None. Decided before any file is opened. |
| `deletable` | Now also reached for a record in the done store. **This is the bug fix.** |
| `ambiguous_id` | Now also fires across files — the same id in `tasks.md` and in a day file, which is exactly the R3 partial-failure state. Correct and wanted. |
| `unreadable_tasks` | Scoped: see below. |
| `line_only` | Now means "in neither half of the store", which is what it always claimed. |

**Scoping `unreadable_tasks`.** 017's rule is: refuse when the id resolves to nothing *and* the task
list holds a line `parse_tasks` could not read, because choom cannot tell "already deleted" from
"unreadable". Applied naively across a store of hundreds of day files, one broken line in a file from
last March becomes a permanent veto on every `ctrl+t` in the workspace — a refusal the user cannot
act on because they have no idea it exists. The rule therefore fires on the unreadable set of the
files actually read during this resolution, and the message names the file and line
(`tasks/done/2026/03/2026-03-14-done.md:7`), not just `tasks.md`. The blocking reason set is
unchanged: `{task_unterminated_comment, task_malformed_comment}`, with `task_invalid_value` still
excluded because it still yields a findable `Task` (017 FR-022, `mirrors.py:286`).

---

## R7 — Duplicate-id messages must name files

**Decision**: `_format_line_numbers` grows into a formatter over `(path, line)` pairs, rendering
`tasks.md:12 and tasks/done/2026/08/2026-08-02-done.md:3`.

**Rationale**: the existing message — "id 'task_a1b2' appears on lines 12 and 3; edit tasks.md to
give one of them a different id" — is actively wrong once records live in two files. It names one
file, and both line numbers are relative to files the user is not told about. Since the R3 partial
failure produces exactly this state, the message is the user's only instruction for recovering from
it, and Principle V requires an error to name "the directory or command the user should have used".

There are two `_format_line_numbers`, one in `tasks.py:575` and one in `mirrors.py:291`, already
duplicated. This feature collapses them into one helper in `tasks.py` that `mirrors.py` imports,
rather than duplicating the new file-aware version a second time.

---

## R8 — `completed:` in the metadata comment, not derived from the filename

**Decision**: add one field, `completed:<YYYY-MM-DD>`, to the task metadata comment, after `created`.
Add `"completed"` to `_RECOGNIZED_KEYS` and validate it exactly as `created` is validated — an
unparseable value warns (`task_invalid_value`) and the record is still returned.

**Rationale**: the cheaper option is to derive the completion date from the containing file's name,
which needs no format change at all. It was rejected because it makes **location authoritative**, and
that is the one coupling this whole design avoids. Principle IV states it directly: "A file the user
has filed under the wrong month still lists — its date comes from frontmatter, never from its path."
A record carrying its own `completed` date can be hand-moved, hand-copied, or dragged into the wrong
day file and still read correctly, and choom is never tempted to relocate it to make the path true
(FR-005). Deriving from the path also silently loses the date the moment a user merges two day files.

**The forward-compatibility cost, stated.** `_classify_body` returns `"malformed"` for a comment
carrying any token it does not recognise (`tasks.py:50-58`). An **older** choom reading a newer
workspace therefore skips completed lines and warns, so those records would be invisible — not lost,
and only on a downgrade. choom publishes no cross-version file-compatibility guarantee today and this
does not create one. The alternative (a token an old parser tolerates) does not exist within the
current grammar, and inventing one is a larger change than the risk warrants.

**Not chosen**: a `completed` *timestamp* rather than a date. The day is what the file partition
needs and the day is all the done view shows; a time would be precision nothing reads.

---

## R9 — No memo, no cache on `resolve_id`

**Decision**: `resolve_id` gains the escalation and nothing else. No cache, no snapshot parameter,
no module-level state.

**Rationale**: the tempting optimization is a per-operation snapshot, because `heal_text` resolves
every link in a document one at a time. But `resolve_id` **already** does a full `scan_meetings` or
`scan_notes` per call for every `meeting_`/`note_` id (`links.py:604-632`) — a whole-collection walk,
per link. Adding a done-store scan per unresolved task id is the same order of cost as what ships
today, in a path that is not on any budget. Introducing a cache here would be new state to invalidate
in exchange for improving a path nobody has measured, which is the trade Principle III names
explicitly.

The two paths that *are* budgeted build their own snapshot locally, without a shared abstraction:
`reconcile_on_open` already assembles `tasks_by_id` in one pass (`mirrors.py:554`) and simply
assembles it from two reads instead of one (R5); the Done view calls `load_task_store` once per
refresh (R10). Neither needs `resolve_id` to change shape.

---

## R10 — The TUI refresh tick is the real performance risk, and the mitigation

**The risk, measured against the shipped code.** `ListScreen` runs `_refresh_tick` every
`REFRESH_SECONDS = 2.0` (`list_screen.py:58, 225`), and `_refresh_tick_read` calls
`app.visible_tasks()` **on Textual's main thread** (`list_screen.py:478-498`). Its own docstring
flags this: "what a worker thread would eventually hand back". `tests/performance/test_refresh_tick.py`
already documents the consequence — cost here is frame budget, not background CPU, and the crossover
into "can drop a frame" is around 15 ms. A whole-store parse at the SC-005 ceiling (500 ms) would
drop frames every two seconds for as long as the Done view is displayed. That degrades the whole UI,
not only the Done list.

**Decision**: the Done view's tick gets a **stat fingerprint precheck**. Before parsing, walk the
store with `os.scandir` and build `(path, st_mtime_ns, st_size)` for each day file. If the tuple
matches the previous tick's, skip the read entirely and return the previous key. A directory walk
over 1,000 small files costs single-digit milliseconds and opens nothing.

**Why this is not a cache or a second source of truth (Principle III).** It stores no task data and
answers no question about content. It decides only *whether to re-read*, is never written to disk,
and dies with the screen. It is also the pattern the tick already uses one level up:
`_refresh_tick_apply` compares a `key` against `_last_render_key` and skips the re-render when they
match (`list_screen.py:499-514`). This adds the same idea one layer earlier, where the cost now is.

**The failure mode is a missed change that persists — corrected.** An earlier draft claimed a miss
costs "a stale list for two seconds, the same failure mode the tick already has". That was wrong. A
missed change is missed again by every subsequent tick, because the fingerprint recomputes to the
same value; the list stays stale until something else moves that file's `(mtime_ns, size)`. The
tick's existing failure mode recovers on the next tick. This one does not.

A miss requires the new `mtime_ns` to be **exactly equal** to the sampled one and the size unchanged
— the comparison is tuple inequality, not "is newer", so a backwards-skewed synced timestamp is still
detected. Two things make equality reachable: **filesystem timestamp granularity** (1 s on HFS+ and
ext3, 2 s on FAT/exFAT, 100 ns on NTFS — two writes inside one quantum are indistinguishable), and
**size-preserving edits**, of which toggling `- [x]` to `- [ ]` is the most likely external edit a
done file will ever see. The OneDrive-shared-workspace assumption widens who the writer might be.

**Resolution: bound the staleness** rather than accept an open-ended window. A full re-parse is
forced when more than 30 s of *displayed* Done view has elapsed since the last one. Wall-clock, not
tick-count, because the tick is paused while filtering, editing, or suspended, so a tick-count bound
would stretch arbitrarily in wall time. The clock is injected (Principle VI).

**Arithmetic**, since the forced parse is exactly the cost the fingerprint exists to avoid: this
file's sibling `test_refresh_tick.py` records ~0.14 ms/document, so the Meetings and Notes ticks
already spend ~7–28 ms of main-thread time **every 2.0 s** — 3.6–14 ms/s amortised, shipping today. A
100 ms store parse every 30 s is 3.3 ms/s, *below* that. At the SC-005 ceiling of 500 ms it is
16.7 ms/s — comparable on average, but a 500 ms single-frame stall is not acceptable, and that is the
real limit. **The bound is therefore paired with an escalation trigger**: a measured full parse above
~100 ms means month-scope the Done view, never lengthen the interval — a longer interval makes the
stall rarer instead of smaller and widens the very window the bound exists to close.

**Residual, accepted**: up to 30 s of staleness after a missed external edit. Tolerable because the
Done view is a record of finished work rather than a live surface, because any completion, filter,
collection switch, or restart refreshes it immediately, and because the window is now bounded and
testable rather than open-ended.

**The named first remedy if SC-005 is still breached**: month-scope the Done view using the
`month_scope` / `scope_selection` machinery the Meetings and Notes panes already have
(`app.py`), reducing the scan to one `YYYY/MM` directory. Tasks have no month scope today
(`app.set_filter`'s "Tasks has no month scope to restore"), so this is real work and is out of scope
here — but it is the answer, and **an index or an on-disk cache is not**, absent a Complexity
Tracking justification this feature does not have.

---

## R11 — The optional sweep is CLI-only

**Decision**: `choom task tidy` — non-interactive, explicit, reports counts. No TUI equivalent. P3,
droppable.

**Rationale for CLI-only under Principle II**: `choom links check` and `choom links heal` are already
CLI-only maintenance commands with no TUI surface (`cli/main.py:585, 596`; no reference anywhere in
`src/choom/tui/`). A one-shot vault maintenance operation is inherently non-interactive in the sense
Principle II carves out: there is nothing to select, nothing to preview, and no per-record decision
to make. `tidy` follows that precedent exactly rather than inventing a new class of exception.

It takes no confirmation and no prompt (Principle II forbids both); it is destructive only in the
sense that `task done` is, and it moves records under FR-011's ordering one at a time, so a failure
partway through leaves the records it has already moved moved and the rest untouched, with a count of
each.

---

## R12 — Test layering, and the existing tests this changes

**Decision**: risk-based, per Principle VI. Weight goes to `unit/` because every Principle IV
guarantee here is decidable against strings and a `tmp_path`.

- **`tests/unit/`** — new `test_task_store.py`: path derivation for a date; the two splices and their
  byte guarantees; `completed:` insert and removal, including a comment with unusual internal
  spacing; the body span travelling intact; a malformed line never moving; an open record found in a
  done file listing as open and not being relocated; the three loaders' scopes.
- **`tests/unit/`** — new `test_task_move_failure.py`: both partial-failure orderings, with the
  destination and then the source made unwritable, asserting byte-identity of the untouched file and
  the duplicate-not-drop outcome.
- **`tests/integration/`** — new `test_completed_task_partition.py`: complete → reopen → complete
  round trip across CLI and TUI; the `ctrl+t`-on-a-completed-mirror regression (R6); the
  reconcile-on-open regression (R5).
- **`tests/contract/`** — `test_json_schema.py::EXPECTED_TASK_KEYS` is an **exact-set** assertion
  (`tests/contract/test_json_schema.py:9`), so the two added keys require editing that constant. That
  is the right shape: adding a key is a minor change, and a reviewed one-line edit to a pinned set is
  how it should show up in a diff. `test_task_done_json.py::EXPECTED_KEYS` needs the same for `file`.
- **`tests/performance/`** — two additions, both carrying `@pytest.mark.performance`, since
  `tests/performance/` now runs as its own CI job selected by that marker (issue #84): the counted
  one-file-read assertion for the default `task list` (SC-003) and the 500 ms whole-store budget
  (SC-005). The count-based one is the load-bearing test — a count cannot flake.

**Existing tests that will need updating**, from `grep`:
`tests/integration/test_task_cli.py`, `test_task_handedit.py`, `test_task_no_loss.py`,
`test_task_category_tui.py`, `tests/unit/test_task_filter_only_done.py`,
`tests/unit/test_mirror_reconcile.py`, `tests/integration/test_mirror_reconcile_open.py`,
`test_mirror_reconcile_save.py`, `test_mirror_propagation.py`, `tests/unit/test_mirror_deletion.py`,
and `tests/performance/test_reconcile_open.py` (which counts `load_tasks` calls and must now account
for the escalation). Each asserts something that is still true in substance; what changes is which
file the completed line is expected in.

**No test may read the wall clock** (Principle VI). The completion date comes from `datetime.now()`
by default, and every core write path in this feature takes an injectable `now: datetime | None`
parameter for the same reason `add_task` already does (`tasks.py:461`).

---

## R13 — Id backfill inside the done store

**Decision**: `load_done_tasks` backfills a missing id onto a checkbox line in a done-store file, on
the same best-effort terms `load_tasks` uses for `tasks.md` (`tasks.py:423-451`): if the write fails,
the read still succeeds and a warning is recorded.

**Rationale**: Principle IV's "missing metadata is repaired in place". A user who hand-writes
`- [x] paid the invoice` into a day file has written a task; the rule that gives it an id in
`tasks.md` has no reason to stop at a directory boundary, and without it that record can never be
reopened, shown, or deleted by id.

**Cost check**: this is a write during a read, which is why `plan_mirror_deletion` avoids
`load_tasks`. The escalating readers in R4 that must not write (`plan_mirror_deletion`) use
`parse_tasks` on the store files directly, exactly as they do for `tasks.md` today. The distinction
is preserved, not blurred.

---

## R14 — Documentation that lands with the code

- **`docs/REQUIREMENTS.md` §3.2** — the layout block gains `tasks/done/YYYY/MM/YYYY-MM-DD-done.md`;
  the task-line bullet gains `completed` in the field order. §3.2's collection rule is satisfied, not
  amended.
- **`docs/REQUIREMENTS.md` §3.3** — gains the canonical-address rule (FR-024): a task link's derived
  path is the path to `tasks.md`, whichever file currently holds the record.
- **`AGENTS.md.tmpl`** — currently 77 lines against the ~100-line backstop
  (`tests/contract/test_guidance_docs.py` asserts `<= 100`). Two lines: where completed tasks live,
  and that `tasks.md` is the open list. Comfortably inside the budget, and squarely the kind of
  non-obvious layout fact §4.2 says the file exists to carry.
- **`README.md` — untouched.** Per `CLAUDE.md`, the feature list describes the released version; this
  is unreleased and belongs to the release, not to this PR.
