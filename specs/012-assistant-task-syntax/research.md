# Phase 0 Research: Linked Task Syntax for AI Assistant

**Feature**: 012-assistant-task-syntax | **Date**: 2026-08-01

Fourteen decisions. No `NEEDS CLARIFICATION` markers remain, and none were carried in from the spec.
R13 and R14 were added after implementation, each from a bug report. R13 supersedes R4's account of what
the instruction says — R4's placement reasoning still stands — and R14 bends FR-017's no-line-dropped
invariant, which it states plainly.

---

## R1: Where the reply-line logic lives

**Decision**: Two functions, both in `core`, both in modules that already exist.

- `core/editor_commands.py` gains `parse_reply_lines(text) -> tuple[ReplyLine, ...]` — pure, no
  workspace, no I/O. It classifies every line of a reply as ordinary text or an eligible task command.
- `core/mirrors.py` gains `capture_reply_tasks(workspace, text, *, source, source_id) -> ReplyCapture`
  — walks that classification, calls the existing `capture_task` per eligible line, substitutes the
  mirror line it returns, and reports what was created and what failed.

`edit_screen.py` calls one function and replaces one span of the buffer with the result.

**Rationale**: Principle I is two-way — the question is not only whether adapter concerns leak into core
but whether logic that belongs in core is being left in an adapter. Splitting a reply into lines,
deciding which are commands, and capturing tasks from them is workspace logic with no terminal in it, and
it must be testable without an event loop. The two homes are the ones the code already implies:
`parse_reply_lines` is `parse_line` applied to many lines and belongs beside it, and
`capture_reply_tasks` is `capture_task` applied to many descriptions and belongs beside that. Import
direction stays clean — `editor_commands` imports only `models`, and `mirrors` already imports far more
than it would need to add.

**Alternatives considered**:

- *A new `core/reply_tasks.py`.* Rejected: two functions with two obvious existing homes do not justify a
  third module, and splitting the grammar away from `parse_line` is exactly how the editor and the reply
  path would come to disagree about what a task line is.
- *Do the walk in `edit_screen`.* Rejected outright under Principle I. It would also make the fence rules
  untestable without a running app.

---

## R2: What makes a reply line eligible

**Decision**: A line is an eligible task command when **all** of these hold, checked in this order:

1. It is not inside a fenced code block (see below).
2. It has no leading whitespace — `line[0] == "/"`, the same first test `parse_line` already applies.
3. `parse_line` returns a `ParsedCommand` for it.
4. That command's name is `task`.

Fence tracking: a line whose first non-space run (up to three leading spaces, per CommonMark) is three or
more backticks or three or more tildes toggles fence state. The closing fence must use the same character
and be at least as long as the opener, and carry no info string. An unclosed fence means every remaining
line is inside it — the safe direction, and the one the spec's edge case names. Indented (four-space) code
blocks need no special handling: rule 2 already excludes them.

**Rationale**: Rules 2–4 are not new behaviour; they are the editor's existing rule restated, which is why
the classifier calls `parse_line` rather than re-deriving the grammar. Only rule 1 is added, and it exists
because the single least forgivable failure of this feature is creating tasks from a reply that was
explaining how to create tasks (SC-005). Tracking fence state costs one variable and one comparison per
line.

**Alternatives considered**:

- *A markdown parser.* Rejected under Principle III — a dependency, or a large amount of new code, to
  answer one question about one string.
- *Strip fences from the reply before scanning.* Rejected: the fenced text must reach the document
  unchanged (FR-010).
- *Allow indented task lines, trimming leading whitespace.* Rejected: it would make the reply path accept
  a line the editor rejects, which is the divergence FR-013 exists to prevent.

---

## R3: How the prompt learns whether capture is possible

**Decision**: `compose_prompt` gains a required keyword-only `task_capture: bool`. `EditTarget` gains a
`captures_tasks: bool` field, set `True` by `open_editor` and `False` by `open_task_editor`, and both the
prompt and the existing `/task` guard in `_capture_task` read it.

**Rationale**: The condition is real — a task's own body has no document identity to link a capture from,
which is why `_capture_task` already refuses there. Today that refusal reads `stamps_frontmatter`, a field
about frontmatter that happens to correlate. Two behaviours now depend on the distinction, so it gets its
own name and stops being inferred from an unrelated one. Making the parameter required rather than
defaulted puts the decision at every call site, including the three in tests, where a silent default
would be the easiest thing in this feature to get wrong without a test noticing.

**Alternatives considered**:

- *Default `task_capture=True`.* Rejected: a caller that forgets instructs an assistant to emit lines that
  will land as literal text.
- *Default `task_capture=False`.* Safer, but it makes the feature's absence the silent outcome — the
  failure a test is least likely to catch.
- *Keep reading `stamps_frontmatter`.* Rejected: it is a coincidence, not a reason, and the comment in
  `_capture_task` already has to explain that.

---

## R4: The instruction's wording and where it sits

**Decision**: A separate constant, appended to `_INSTRUCTIONS` only when `task_capture` is true, as the
final bullet — immediately after "Do not edit any file" — and explicitly reconciling itself with it:
emitting the line is not editing a file, because choom does the writing.

Content, in about six lines: the two forms (`/task <description>` and `/task.<type> <description>`), that
`#tags` inside the description are lifted out, that the line must be the whole line and unindented and
outside any code fence, that choom replaces it with a link to the task it creates, and that it is
optional.

> **Superseded in part by R13.** "Optional" is exactly the word that made a real assistant answer a
> request for action items with a markdown list. The clause is now directive for content that is a thing
> to be done, bounded to what the request asked for, and requires fenced examples. The placement decision
> above — last, after "Do not edit any file", reconciling itself with it — is unchanged.

**Rationale**: Placement matters more than it looks. "Do not edit any file" is the last and most absolute
instruction in the block, and a permission to create tasks that arrives before it reads as contradicted by
it; arriving after it, and naming the contradiction, is what makes both instructions followable. The
"replaced by a link" clause is not decoration either — it is what lets the assistant write a summary whose
surrounding prose still reads correctly after the substitution has happened.

Keeping it a separate constant is what makes FR-006 checkable: one string, appended or not, cannot drift
between assistants.

**Alternatives considered**:

- *One constant with the task clause always present, plus a "not available here" line.* Rejected: it
  spends prompt on telling an assistant about a thing it cannot do.
- *Per-assistant wording.* Rejected by FR-006, and by #69's lesson — instruction wording is where the two
  assistants diverge, so the response to divergence is fewer per-assistant strings, not more.

---

## R5: When the capture runs

**Decision**: On the UI thread, inside `_finish_request`, after the superseded check and only when
`reply.ok`. Not in the `@work(thread=True)` worker.

**Rationale**: The worker is the tempting home — it already blocks, and file I/O there would keep the UI
free. It is wrong because the worker cannot know whether its reply will be used. `_finish_request`
discards a reply whose request has been superseded, and `AssistantRequest.wait()` reports cancellation;
capturing before those checks creates tasks for a reply the user never sees, which FR-019 forbids and
which no cleanup path could undo. Doing it after the checks costs one atomic write per captured task on
the UI thread — the same cost as the user typing `/task` that many times, and bounded by a reply the
assistant has already spent seconds producing.

**Alternatives considered**:

- *Capture in the worker, delete the tasks if the reply is discarded.* Rejected: a delete-to-repair path
  for a case that a single `if` prevents.
- *Capture in the worker, pass the created ids through and discard silently.* Same defect: the tasks exist.

---

## R6: Undo granularity

**Decision**: The whole reply, with mirror lines already substituted, is inserted by the single
`editor.replace()` call that exists today. Nothing about the edit shape changes.

**Rationale**: Captures complete before the buffer is touched, so there is exactly one edit to undo,
exactly as a reply with no task lines produces today (FR-011). Undo therefore restores the `⋯` placeholder
span in one step and leaves the created tasks alone, which is the behaviour 009 already established for a
typed capture (FR-024) — inherited rather than implemented.

---

## R7: Per-line capture rather than a batch write

**Decision**: Call `capture_task` once per eligible line, accepting one `tasks.md` write each.

**Rationale**: `capture_task` is where description parsing, `#tag` extraction, token validation, id
generation, line rendering, and the source link all happen — FR-021's "indistinguishable" is true only
because there is one path. A batch writer would have to reproduce that or refactor it, and both are ways
for a reply-captured task to acquire a shape that a typed one does not have.

**Alternatives considered**:

- *Collect descriptions and write once.* Rejected on the above; the write cost it saves is not a cost this
  feature has evidence of paying. If it ever is, the fix belongs inside `add_task`, benefiting every caller.

---

## R8: What the user is told

**Decision**: One status line composed from the capture result:

- All captures succeeded, at least one: `3 tasks captured` (singular `1 task captured`), rendered
  **without** the `⚠` prefix.
- Some failed: `2 tasks captured; 1 could not be: <first reason>`, with `⚠`.
- All failed, or the only task lines were unusable: the reason alone, with `⚠`.
- No task lines at all: exactly today's behaviour — the plain `EDIT_HELP` footer, no message (FR-011).

This needs a neutral note path in `EditScreen`: `_render_status` prefixes `⚠` unconditionally today, so it
gains a `warn: bool = True` keyword rather than a second method.

**Rationale**: A successful capture is news, not a warning, and rendering "3 tasks captured" behind a
warning sign teaches the user to read `⚠` as noise — the same reflex Principle V's confirmation rule
exists to protect. Naming only the first reason keeps the line inside a narrow terminal; the count carries
the rest.

---

## R9: Not mistaking a fresh mirror for a user toggle

**Decision**: Seed `_mirror_baseline[task.id] = False` for every task the reply captures, at the same
point `_capture_task` does it for a typed one.

**Rationale**: The baseline is "what each mirror read when the buffer and `tasks.md` last agreed". A
mirror that appears in the buffer without a baseline entry is indistinguishable at the next save from one
the user just ticked, which would write a spurious state change back to `tasks.md` (FR-023). This is the
single most likely silent bug in the feature and it costs one line.

---

## R10: Partial-failure semantics

**Decision**: `capture_reply_tasks` catches `UsageError` and `WorkspaceError` per line — the two
`capture_task` documents — and on either one leaves that line's text exactly as the assistant wrote it,
records a `ScanWarning`, and continues to the next line. A new `ScanWarningReason` literal,
`"reply_capture_failed"`, is added for it.

Ordering is top to bottom, so tasks appear in `tasks.md` in the order the assistant listed them, and a
failure part-way through leaves the tasks before it created.

**Rationale**: FR-016 and FR-017 make this the feature's Principle IV surface: the reply is the user's
words for this purpose, and no failure may cost any of it. Catching exactly the two documented exceptions
rather than `Exception` keeps a genuine bug loud. `UsageError` covers the empty-description case (FR-015),
so `/task` with nothing after it needs no separate branch — it fails the same way and lands as text.

Adding a `ScanWarningReason` value is additive; under Principle II adding a key or value is a minor
change, and no existing reader enumerates the literal exhaustively.

---

## R11: Test layering

**Decision**: Risk-based, per Principle VI, weighted to `unit/` because that is where this feature's edge
cases actually live.

- `tests/unit/test_reply_lines.py` (new) — the classifier: backtick and tilde fences, an unclosed fence, a
  fence opened with a longer run, indented lines, inline mentions, `/task` bare, `/task.followup` bare,
  `/ai` and `/link` lines, CRLF input, and a line that is only tags.
- `tests/unit/test_capture_reply_tasks.py` (new) — substitution and ordering, tags and type suffix
  reaching the task, a reply with no task lines returning its input unchanged, one failure among several,
  and every failure at once.
- `tests/unit/test_compose_prompt.py` (existing) — the instruction present when `task_capture=True`,
  absent when `False`, and identical for every profile in `PROFILES`.
- `tests/integration/test_ai_command_tui.py` (existing) — one end-to-end path per story: a reply of prose
  and task lines producing real tasks and mirrors (US1), a reply explaining the syntax producing none
  (US3), and an unwritable `tasks.md` still landing the whole reply (US5).
- No `contract/` change: this feature adds no CLI surface. No `performance/` change: no budget.

New `stub_assistant` modes are needed for the integration paths — `reply_with_tasks`, `reply_explaining`,
and one mixing both — added beside the existing `reply` and `reply_with_slash` modes in `tests/conftest.py`.

**Rationale**: The failure modes are string classification and partial failure, both of which are cheapest
and clearest to pin at the unit layer; the integration tests exist to prove the wiring, not to re-verify
the rules. `test_reply_containing_a_slash_ai_line_is_inserted_as_literal_text` already covers FR-014 and
needs no change — a useful signal that the boundary was drawn where the code already stood.

No test reads the wall clock: `capture_task` takes `now`, and none of these assert on a date.

---

## R12: Documentation surface

**Decision**: README only — two bullets, both existing: the `/ai` bullet gains what the assistant may now
emit and what happens to it, and the inline task capture bullet gains a clause that the same syntax is
available to the assistant. `AGENTS.md.tmpl` is **not** changed.

**Rationale**: `AGENTS.md` is runtime guidance for an assistant working in a workspace directly, and it
already documents the `/task` line for that reader. This feature's instruction travels inside the composed
prompt, which is self-contained by construction — an assistant invoked by `/ai` is told the grammar
whether or not it ever reads `AGENTS.md`. Adding it to both would duplicate the one string FR-006 exists to
keep single, and would spend the file's ~100-line budget on something its reader does not need.

---

## R13: The instruction has to be directive, and bounded, and fence its examples

**Added after implementation**, from a bug report: asked for a list of tasks from a meeting note, the
assistant returned a markdown list and used the syntax not at all.

**Decision**: three properties, all measured against the real Claude Code CLI rather than reasoned about.

1. **Directive, not permissive.** R4's wording explained the syntax, said "you may write", and closed
   with "this is optional -- most replies need none". Read together with the earlier instruction to
   "write markdown that belongs in working notes: prose, a list, a table", an assistant asked for action
   items produced a list every time. The clause now says content that is a thing to be done is written as
   a task line "not as a bullet in a markdown list", and that this "overrides the guidance above".
2. **Bounded to the request.** Directive wording alone over-corrected: a plain "summarise the discussion
   in two sentences" began appending three captured tasks, because the note contained commitments. The
   clause now says to answer only what was asked, and names the cost — real records the user has to go
   and delete.
3. **Examples fenced.** With the syntax now prominent, "how do I capture a task from in here?" produced a
   *bare* example line, which the classifier would have captured as a real task. The classifier's fence
   rule (R2) is only half the protection; the assistant has to fence. The clause now says so, and names
   why: a bare example is indistinguishable from a real one.

**Rationale**: this is the part of the feature no stub can test — quickstart's US2 says as much, and T037
called out that only a real assistant can prove the line gets emitted. The failure was not in the
mechanism, which worked from the first commit, but in the assumption that stating a capability makes an
assistant use it. Prompt wording is behaviour here, so each of the three is a requirement (FR-005,
FR-005a, FR-005b) with a test naming the failure it prevents, not a phrasing that a later edit can
casually undo.

**Measurement**: four prompts against the same fixture note -- "list the action items I committed to",
"summarise in two sentences then list what I owe", "summarise in two sentences", and "how do I capture a
task? show me an example" -- scored by running the real classifier over each reply rather than by eye.
Before: 0 captured on the first, which is the bug. After: 2, 2, 0, 0 -- all four as intended.

**Alternatives considered**:

- *Leave the wording and let users prompt around it* ("...and use the task syntax"). Rejected: it makes
  the feature something the user has to know a password for, and #44's whole complaint is that capturing
  by hand is what stops them asking.
- *Drop "a list" from the general instruction block.* Rejected: it is right for every reply that is not a
  set of commitments, and this feature does not get to degrade the ordinary case.
- *Post-process a markdown list into task lines.* Rejected outright: choom would be inventing tasks from
  text the assistant did not mark as tasks, which is the opposite of the explicit grammar this feature
  exists to establish.

---

## R14: A loose list of task lines is tightened here, not in the prompt

**Added after implementation**, from a bug report: a captured list arrived in the note with a blank line
between every checklist item.

**Decision**: `capture_reply_tasks` drops a run of blank lines lying between two *captured* lines
(`_tighten_captured_runs`). Blank lines before the block, after it, between a capture and ordinary prose,
or beside a line whose capture failed are all kept.

**Rationale**: both shapes are ordinary markdown. An assistant may write its task lines tight or as a
loose list, and nothing about the request determines which. Substituting each line for its mirror
faithfully preserves whichever arrived, so the user's note gets a gappy checklist roughly whenever the
model felt like it — the same list, formatted two different ways on two different days.

The alternative is a prompt instruction, and R13 is the reason not to reach for one again: three rounds of
wording produced an assistant that complies *usually*. Sampling the real Claude Code CLI for this
behaviour gave tight lists in every one of five attempts across two fixture notes, including two at six
tasks — the reported gappy output never reproduced on demand. A property that cannot be reproduced cannot
be pinned by a test, and a prompt cannot make it deterministic. Moving the rule into the walk makes the
outcome the same on every run regardless of which shape the model chose, and it is testable.

**On the invariant this bends**: FR-017 said no part of a reply may be dropped. It now says no line
*carrying a character* may be dropped, with this one bounded exception (FR-010a). That is a real
weakening and worth stating plainly rather than burying: the guarantee exists so an assistant's words
always reach the document, and a blank line between two checklist items is not words. The exception is
narrow by construction — it requires a captured line on both sides, so no rule about prose, failures, or
block separation changes.

**Alternatives considered**:

- *Instruct the assistant to keep task lines consecutive.* Rejected per above: probabilistic where this is
  deterministic. It remains available as a belt-and-braces addition if the loose shape proves common.
- *Normalise blank lines across the whole reply.* Rejected: it would reformat the assistant's prose, which
  is exactly what FR-010 exists to prevent.
- *Tighten in the TUI before inserting.* Rejected under Principle I — it is a rule about reply content, and
  the unit tests for it should not need an event loop.

---

## R15: Description length is a prompt constraint, grounded in the column width

**Added after implementation**, from a bug report: every captured task truncated in the tasks list.

**Decision**: the clause asks for three to five words, around thirty characters, and names the tasks
list's 34-character truncation point as the reason. It also asks for lower case unless a word is a proper
noun and no trailing full stop, which is the house style every hand-typed task already follows.

**Rationale**: nothing in the original clause said anything about length, and an assistant summarising a
meeting writes a *sentence* — it has no reason to know a list column exists. Measured against a
six-commitment fixture note, descriptions came back at a mean of 75 characters and a maximum of 105, and
**12 of 12 truncated**. The title column is 34 characters wide at the 80-column layout target that
Principle V and 011 both design against, so every captured task lost its tail exactly where the user reads
it.

Giving the reason rather than only the number matters: the first attempt said "about 34 characters, treat
40 as the ceiling" and landed at a mean of 34 with 5 of 12 still over. Anchoring on a word count as well —
models follow "three to five words" more reliably than a character budget — brought it to a mean of 30, a
maximum of 36, and 2 of 11 grazing the limit by a character or two.

| Wording | Mean | Max | Over 34 |
|---------|------|-----|---------|
| No length guidance | 75 | 105 | 12 of 12 |
| Character budget only | 34 | 49 | 5 of 12 |
| Word count + budget + reason | 30 | 36 | 2 of 11 |

Stopping there is deliberate: squeezing the last two costs meaning, and a description a couple of
characters over is legible where an 80-character one is not.

**Alternatives considered**:

- *Truncate or summarise the description in `capture_task`.* Rejected outright — choom would be editing
  the words the assistant chose, and Principle IV's whole premise is that it does not.
- *Widen the title column.* Rejected: it is not the column that is wrong, and the space would come out of
  the tags column, which 011 sized deliberately.
- *Let the description run long and rely on the preview pane.* Rejected: the list is where a user scans
  for a task, and a list of identical prefixes is not scannable.
