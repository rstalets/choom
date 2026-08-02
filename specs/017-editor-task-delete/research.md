# Phase 0 Research: Delete a Task From the Line It Lives On

**Feature**: `017-editor-task-delete` | **Spec**: [spec.md](./spec.md) | **Date**: 2026-08-02

Every finding below was established by reading the installed source — `textual==8.2.8` and this
repository at `origin/release/v0.0.4` — not from memory. Line references are to that tree.

---

## R1: `ctrl+t` reaches `EditorPane` without a priority binding

**Decision**: Bind `Binding("ctrl+t", "delete_task", "Delete task", show=True)` on `EditorPane`, with
**no** `priority=True`.

**Rationale**: `EditorPane`'s existing `ctrl+o`/`ctrl+s`/`ctrl+x` bindings carry `priority=True` with a
comment explaining why — `TextArea` binds `ctrl+s` and `ctrl+x` itself, so without priority the focused
editor shadows the pane. That reason does not apply here:

- `ctrl+t` is absent from `TextArea.BINDINGS`, `Screen.BINDINGS`, and `App.BINDINGS` in 8.2.8
  (checked by iterating each class's `BINDINGS`), and appears nowhere in `src/choom/tui/`.
- `TextArea._on_key` inserts a character only when `event.is_printable or key in {"enter", "tab"}`.
  `Key("ctrl+t", "\x14").is_printable` is `False` (verified), so the key is neither consumed nor
  inserted as a control character; it bubbles to the pane.

Using the default (non-priority) binding is also the safer choice: a priority binding is checked from
the app downward regardless of focus, which would make `ctrl+t` fire while the link picker has focus.
The non-priority binding cannot, and `check_action` (R12) closes the remaining gap.

**Alternatives rejected**: `ctrl+d` — settled in refinement; it is `TextArea`'s delete-character-forward
and `ListScreen`'s shipped record-delete (`src/choom/tui/list_screen.py:169`, advertised in both
`LIST_HELP` and `TASK_LIST_HELP`). Adding `priority=True` — unnecessary, and strictly worse for the
picker case.

---

## R2: Editor undo after a confirmed deletion — the mechanism decides the behaviour

**This is the gap the spec left open. It is decided here.**

**Decision**: Remove the line with `TextArea.delete(start_location, end_location,
maintain_selection_offset=False)` — a recorded, undoable `Edit`. **Never** by assigning
`editor.text = ...`.

Consequence, stated as the intended behaviour: **the editor's undo restores the line in the buffer; the
task record stays deleted; the restored line is a dead task line, reported on the next save and on the
next open.** The undo history from earlier in the session survives the deletion.

**Rationale** — the two candidate mechanisms behave very differently, and only one is acceptable:

| Mechanism | Undo history | Undo outcome |
|---|---|---|
| `editor.delete(a, b)` → `TextArea.edit()` → `self.history.record(edit)` | **Preserved**; the deletion is one undoable step | Line comes back in the buffer; `tasks.md` untouched by the undo |
| `editor.text = new_text` → the setter is an alias of `load_text()`, whose docstring reads "This will replace the text currently in the TextArea and **clear the edit history**", and whose body opens `self.history.clear()` | **Destroyed** — the whole session's history, not just this step | Nothing to undo at all |

The second option silently throws away undo history the user accumulated before ever pressing `ctrl+t`.
That is a real loss of the user's work-in-progress control, so it is rejected even though it would make
the undo question moot.

The resulting state after an undo — a task line whose id resolves to nothing — is **not data loss and
not a new state**. It is exactly the `dead` outcome `reconcile_on_open` and `reconcile_on_save` already
produce and warn about, and which `tests/integration/test_delete_mirrors.py` already pins as the
documented consequence of deleting a task that documents mirror. Undo cannot resurrect a task record,
because the undo history belongs to one text widget and has never spanned files; pretending otherwise
would mean re-creating a task with a fresh id, which is a different task.

**Known interaction, recorded rather than fixed here**: `EditorPane._save()` already assigns
`editor.text = result.saved_text` when the frontmatter stamp changes the text
(`src/choom/tui/edit_screen.py:445-453`), which clears the history by the same mechanism. So on a
document with an `updated:` field, a save may clear undo history regardless of this feature. That is
pre-existing behaviour introduced by 004/014, is not made worse here, and is out of scope — but it does
mean the undo-restores-the-line behaviour is reliably observable only where the save does not rewrite
the buffer (a task body, or a second save inside the same clock second). The decision above is about
what *this feature* does with the undo stack: it does not clear it.

**Alternatives rejected**: making the deletion non-undoable on purpose (e.g. `history.clear()` after
it) — that is the destructive option dressed as a safety feature; suppressing the resulting dead line
by scanning and rewriting on undo — would mean watching the buffer for undos and writing `tasks.md`
behind the user's back, far past what the confirmation authorised.

---

## R3: The logic lands in `core/mirrors.py`, split into a plan step and a commit step

**Decision**: No new core module. Two new public functions and one new frozen result type in
`src/choom/core/mirrors.py`, whose module docstring already claims exactly this domain: *"This module
owns everything about that edge: recognising a mirror, writing one at capture time, pushing a task's
state into a document, and resolving which side wins when a mirror and its task disagree."* Removing
the edge is the same domain as creating it.

The split is forced by the confirmation sitting in the middle of the operation:

- `plan_mirror_deletion(...) -> MirrorDeletion | None` — decides what would happen. Reads `tasks.md`,
  **writes nothing**. Returns `None` when the line is not a task line, which is FR-008's no-op.
- `commit_mirror_deletion(...) -> MirrorDeletion` — performs the `tasks.md` write for a plan that
  called for one. Never touches the document; the caller owns the buffer.

`plan_mirror_deletion` computing the resulting document text *before* the dialog is raised is also the
mechanism for FR-013 ("captured at the moment the confirmation is raised"): what gets applied on
confirm was decided from the buffer as it stood when the question was asked. This mirrors
`ListScreen.action_delete`'s shipped discipline of capturing `record_id` before pushing the dialog
(`src/choom/tui/list_screen.py:665-668`).

**Alternatives rejected**: a new `core/mirror_deletion.py` — a module for two functions in a domain that
already has a home, and `mirrors.py`'s own plan explicitly warns that splitting this grammar across
files is "how a byte-preservation guarantee gets quietly broken". Putting it in `core/deletion.py` —
that module is the by-id record-delete entry point for both front-ends and knows nothing about document
text. A single do-everything function — leaves the adapter deciding whether to ask first, which is the
decision Principle V cares most about.

---

## R4: Removal is a character-offset splice, and the widget conversion is a library call

**Decision**: `MirrorDeletion` carries `span: tuple[int, int]` — character offsets into the document
text — and `text`, which is by construction `original[:start] + original[end:]`. The adapter converts
the offsets to widget coordinates with `TextArea.document.get_location_from_index(index)` and calls
`delete()`.

**Rationale**: Character offsets are already this module's idiom for exactly this reason. `Mirror`'s own
docstring: *"`state_offset` is the load-bearing field: it is the character offset of the single state
character in the document text, so applying a state is always `text[:o] + char + text[o+1:]` — no line
is ever re-rendered."* `Link.start`/`Link.end` are the same idea for the healer. Using offsets here
keeps FR-018 ("a splice at a recorded position, never a re-render, never located by text match") true
by construction rather than by discipline.

`get_location_from_index` exists on `textual.document._document.Document` in 8.2.8 (verified), so the
offset → `(row, column)` conversion is a library call, not adapter logic. This matters for the
Principle I gate: the adapter computes nothing about *what* to remove.

It also gives the design a single bridging assertion a test can make:

```
after the widget edit:  editor.text == plan.text
```

If the adapter ever diverged from core's decision, that equality breaks. One rule, one definition, one
check — rather than core and the TUI each knowing how to remove a line.

**Span definition** (contract-level, so both consumers agree): the span starts at the first character
of the task line and ends **after its line terminator**. When the task line is the last line of the
buffer and carries no terminator, the span instead starts at the end of the previous line's content —
i.e. it absorbs the *preceding* terminator — so removing the last line does not leave a stray blank
line behind. When the task line is the only line, the span is the whole buffer.

**Alternatives rejected**: core returning a line index and the adapter doing `(row,0)`→`(row+1,0)` with
its own last-line special case — that special case is a rule about what removal means, and it belongs in
core. Core returning only the new text and the adapter assigning `editor.text` — clears undo history
(R2).

---

## R5: Line endings and the trailing newline need no new code

**Decision**: The core text transform operates on LF-only text and knows nothing about CRLF. FR-019 is
satisfied by the existing save path.

**Rationale**: `load_for_edit` (`src/choom/core/editing.py:37-55`) reads with `newline=""`, records the
file's convention in `EditableFile.newline` and its `trailing_newline` state, and hands back text with
`\r\n` already collapsed to `\n`. Every write goes back out through `_apply_line_ending_policy`
(`editing.py:58-66`), which restores both. The editor buffer is therefore always LF-only, in both hosts
and for both `EditTarget` implementations.

So a CRLF document survives this feature for the same reason it survives `/task`, `/link`, and every
existing save — and adding CRLF handling to the new code would be a second, competing implementation of
a policy that already has one. Tests still cover it end-to-end (a CRLF fixture through the whole
gesture), but no new source handles it.

---

## R6: "The task list is unreadable" has an exact definition — and planning must not write

**Decision**: The task list counts as unreadable, for FR-021's purposes, when
`parse_tasks(raw_text).warnings` contains a warning whose `reason` is `task_unterminated_comment` or
`task_malformed_comment`. No other reason qualifies. The plan step reads the file with
**`parse_tasks`, not `load_tasks`**.

**Rationale**: Those two reasons are exactly the cases where `parse_tasks` skips a line *without*
producing a `Task` — `src/choom/core/tasks.py:239-274`, both branches `continue` before `_append_task`.
A line skipped that way is invisible to an id lookup, which is precisely why choom cannot tell "this
task was deleted" from "this task is sitting right there under a broken comment".

The third task-shaped reason, `task_invalid_value`, does **not** qualify: an invalid `created` date
records a warning and then falls through to `_append_task` (`tasks.py:290-310`), so the task is still
found by id. Treating it as blocking would refuse a deletion choom is perfectly able to perform, which
FR-022 forbids.

`needs_id` lines (a checkbox with no metadata comment at all) also do not qualify. They have never had
an id, so no task line in any document can point at one; they cannot be the record being looked for.

**Why `parse_tasks` and not `load_tasks`**: `load_tasks` backfills missing ids and **writes the file**
(`tasks.py:436`). The plan step runs before the user has confirmed anything, and FR-014 requires that
cancelling write nothing at all. Calling `load_tasks` there would write to `tasks.md` merely because the
user pressed a key — a side effect from a gesture they may be about to cancel. `parse_tasks` is pure.

**Alternatives rejected**: treating any warning as blocking (over-refuses, breaks FR-022); ignoring
unreadable lines entirely and removing the document line (the unrecoverable guess FR-021 exists to
prevent); attempting to repair the malformed comment (Principle IV says malformed input is skipped and
logged, not rewritten, and repairing it here would be a write nobody asked for).

---

## R7: Detecting extra text on the line — extend `Mirror` with the link's span

**Decision**: Add `link_start: int` and `link_end: int` to the `Mirror` dataclass, populated in
`find_mirrors` from the `Link` it already selects.

**Rationale**: FR-011 needs to know whether the line carries anything besides the checkbox prefix and
the task's own link. That is decidable exactly when the mirror's link span is known: take the line's
content, remove the `_MIRROR_PREFIX` match and the characters between `link_start` and `link_end`, and
test whether anything non-whitespace remains.

`find_mirrors` already has this information and discards it — it sorts the line's task links by
`link.start` and keeps only `(task_id, text)` (`src/choom/core/mirrors.py:91-92`). Threading the span
through is additive and cheap.

The alternative — having the new plan function call `find_links` again and re-apply "first by document
order wins" — would restate FR-007's rule in a second place, which is the one thing FR-005 explicitly
forbids.

**Blast radius**: `Mirror` is constructed in exactly one place in the entire tree (`mirrors.py:95`,
confirmed by grep across `src/` and `tests/`), consistent with its docstring ("produced by scanning,
never constructed by a caller"). Adding two required fields breaks no call site.

---

## R8: Write order, and what each failure leaves behind

**Decision**: On confirm — (1) `tasks.md` write, (2) widget splice, (3) document save. Any failure at
step 1 stops the whole gesture.

**Rationale**: The spec argues the order (FR-015) and the coordinator endorsed it; this records what each
outcome actually looks like, so the tests have something to assert:

| Failure point | `tasks.md` | Document on disk | Buffer | Reported |
|---|---|---|---|---|
| Plan refuses (unreadable / ambiguous / self-referential) | untouched | untouched | untouched | status, naming cause and next step |
| User cancels the dialog | untouched | untouched | untouched, still dirty if it was | nothing |
| Step 1 raises (`WorkspaceError`, `NotFoundError`, `UsageError`) | untouched | untouched | untouched | status, the core message |
| Step 3 save fails | **task deleted** | untouched | line removed, marked unsaved | status, the save message |
| All succeed | task deleted | line removed + `updated` stamped | clean | status names the deleted task |

The step-3 row is the only partial state, and it loses nothing: every word the user wrote is still on
disk, and the buffer holds the change so `ctrl+o` retries it. Its residue if abandoned — a document
still carrying a line for a deleted task — is the already-handled dead-mirror state (R2).

Reversing the order would put the document write first, so its failure mode would be an orphan task
record while the user's document line was already gone. Both are recoverable, but only one of them
touches the file holding the user's words *before* the cheaper, id-located, already-tested write has
succeeded.

**Free behaviour worth naming**: FR-025 (a second task line for the same task elsewhere in the document)
needs no new code. After step 2 the buffer still contains that second line; step 3's `reconcile_on_save`
looks its id up, finds no task, and emits `_dead_mirror_warning` — which `_save()` already surfaces
through `mirror_report.warnings`. The report FR-025 asks for falls out of the existing save path.

---

## R9: The self-referential case needs the editor to know which task it is editing

**Decision**: Add `body_task_id: str | None = None` to `EditTarget`. `open_task_editor` sets it;
`open_editor` leaves it `None`. `plan_mirror_deletion` takes it and returns the `self_referential`
outcome when it equals the target line's task id.

**Rationale**: FR-024 refuses to delete the task record whose body is the buffer being edited. Nothing in
today's `EditTarget` can answer "which task is this?" — `open_task_editor` closes over `task_id` in its
`_save` function and the value is otherwise unreachable (`src/choom/tui/edit_screen.py:151-191`).
`captures_tasks=False` distinguishes a task body from a document, but not *which* task.

Without the guard the sequence is: `delete_task(A)` removes A's checkbox line and body span, then
`set_task_body(A, ...)` re-reads, fails to find A, and returns `SaveResult(ok=False)`. Nothing is
corrupted — `set_task_body` re-reads and locates by id, so it cannot write into a stale offset — but the
user is left in an editor whose text has nowhere to go, with a message about a task that no longer
exists. Refusing up front is the same outcome with an explanation, one step earlier.

`EditTarget` is constructed in exactly two places, both in `edit_screen.py` (grep over `src/` and
`tests/`), so a defaulted field is a two-line change.

**Note on the non-self-referential body case**, which stays allowed: deleting task B from inside task A's
body editor writes `tasks.md` twice — `delete_task(B)`, then `set_task_body(A, ...)` on save. This is
safe because both re-read and re-parse the file and locate by id rather than by a cached line number, a
discipline both docstrings state explicitly. B's removal shifts A's line number; neither call cares.

---

## R10: Confirmation wording, including the unsaved-edits clause

**Decision**: Three wordings, one dialog class (the existing `ConfirmDialog`), no new dialog. The saving
side effect is named in the question itself.

| Case | Question |
|---|---|
| Task exists | `Delete "{description}"? It goes from this document and from your task list, and the document is saved. This cannot be undone.` |
| Task already absent (FR-012) | `Delete "{description}"? It is no longer in your task list, so only this line goes. The document is saved. This cannot be undone.` |
| Extra text on the line (FR-011) | the applicable question above, plus ` This line has other text on it, which goes too.` |

**Rationale for the "and the document is saved" clause** — this is the coordinator's honesty check.
`ctrl+t` commits any unrelated unsaved edits sitting in the buffer (FR-028/FR-030). A dialog that said
only "delete this task" would be accurate about the deletion and silent about the save, which is
misleading precisely for the user most at risk: someone with a half-written paragraph further down the
buffer. Six words fix it inside the existing question, so no second dialog is needed and FR-009 holds.

Cancelling remains a complete no-op (FR-014), which is what makes the clause safe to state: the user who
reads "the document is saved" and is not ready for that presses Esc and nothing at all has happened.

Precedent for the shape: `ListScreen.action_delete` already asks `Delete "{title}"? This cannot be
undone.` with `cancel_label="Keep It"` / `confirm_label="Delete"` (`list_screen.py:674-678`). The same
labels are reused, so the two deletions in the product read the same way.

**Alternatives rejected**: a second dialog or a two-stage confirmation when the buffer is dirty —
forbidden by FR-009 and by Principle V's warning about dialogs that teach dismissal; saying nothing about
the save — the misleading option; refusing when dirty — rejected in the spec, and inconsistent with
`/task`, `/link`, and `/ai`, all of which call `self._save()` before touching `tasks.md`.

---

## R11: Footer text

**Decision**: `EDIT_HELP` becomes
`"ctrl+o save   ctrl+x save & back   ctrl+t delete task   esc discard   ctrl+q quit"` — 81 characters,
up from 60.

**Rationale**: Principle V requires every active binding in the footer, and
`tests/unit/test_footer_bindings.py::test_footer_advertises_every_shown_binding` enforces it mechanically
for `EditorPane` against `EDIT_HELP`, so a `show=True` binding that is not spelled out fails the suite.

81 characters is comfortably inside precedent: `LIST_HELP` is 115 and `TASK_LIST_HELP` is 117 today. The
`<= 80` assertion in that same test file is parametrized over `PREVIEW_HELP` and `LINKS_SECTION_HELP`
only, deliberately — the list footers have always exceeded it. `StatusBar.update` already handles a
string wider than the bar by falling back to `f"{text}   {version}"` instead of right-padding, and
`tests/integration/test_narrow_terminal_tui.py` boots the app at 20 and 10 columns without asserting the
footer fits, so nothing regresses.

"delete task" rather than "delete": the list view's `ctrl+d delete` removes whichever record is
highlighted, which in the tasks collection is also a task. Spelling this one "delete task" says what the
key does on a line rather than on a row, and the two footers are never on screen at the same time.

`LINK_PICKER_HELP` is unchanged: `ctrl+t` is inert while the picker is open (R12), and an inert key does
not belong in the footer.

---

## R12: Gating the binding while the editor is busy

**Decision**: Extend `EditorPane.check_action` — return `False` for `"delete_task"` when
`self._link_picker_line is not None` or `self._request is not None`.

**Rationale**: FR-004. The pane already has this exact mechanism
(`src/choom/tui/edit_screen.py:384-400`): it disables `save`/`save_and_close`/`close`/`cancel_request`
while a `/link` choice is pending, and gates `cancel_request` on there being a request. Adding one term
reuses a shipped pattern rather than inventing a state machine.

Both conditions matter for different reasons. During an `/ai` request the buffer is `read_only` and the
target line has been replaced by the `⋯` placeholder, so a deletion would be planned against text that is
about to be overwritten when the reply lands. While the picker is open, focus is on the picker and the
line the user is looking at is not the line the cursor is on.

`TextArea.read_only` alone is not sufficient as the test: it blocks `TextArea`'s own key handling, but
`ctrl+t` is a pane binding and would still fire.

---

## R13: Test placement

**Decision**: Risk-based, per Principle VI — not one test per acceptance scenario.

- **`tests/unit/test_mirror_deletion.py`** (new): everything about *what* gets removed, against strings.
  The span rules (mid-file, last line with and without a trailing newline, only line), blank lines above
  and below preserved, indented continuation preserved, the task line's own indentation, extra-text
  detection, the outcome matrix (deletable / line-only / unreadable / ambiguous / self-referential), and
  that `plan.text == original[:s] + original[e:]`. This is where the Principle IV guarantees are actually
  proved, and none of it needs a terminal.
- **`tests/unit/test_mirror_recognition.py`** (modify): `link_start`/`link_end` are populated correctly,
  including the multiple-links-on-one-line case.
- **`tests/unit/test_footer_bindings.py`** (no change needed): its existing parametrized test covers the
  new binding automatically. Named here so the tasks phase does not add a redundant one.
- **`tests/integration/test_editor_task_delete_tui.py`** (new): the gesture end to end — confirm deletes
  both, cancel writes nothing, no dialog on a non-task line, the undo behaviour decided in R2, the
  second-mirror warning, refusal paths, a CRLF fixture, and the `editor.text == plan.text` bridge
  assertion from R4. Parametrized across the inline and full-screen hosts where the host could plausibly
  matter, rather than duplicated.
- **No `tests/contract/` change**: this feature adds no CLI surface, no `--json` key, and no exit code.
  `tests/contract/test_cli_delete.py` already covers `task delete` and is untouched.
- **No `tests/performance/` change**: no budget to protect; the plan step parses one `tasks.md` and one
  buffer already in memory, which is the same cost `/task` pays today.

No test reads the wall clock. Fixtures needing a date derive it the way the existing task fixtures do.
