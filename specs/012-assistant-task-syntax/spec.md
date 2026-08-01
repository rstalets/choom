# Feature Specification: Linked Task Syntax for AI Assistant

**Feature Branch**: `012-assistant-task-syntax`

**Created**: 2026-08-01

**Status**: Draft

**Input**: User description: "#44 - Linked task syntax for AI assistants"

**Source**: GitHub issue #44 "[Feature]: Linked task syntax for AI assistant", which asks that the
prompt choom composes for an assistant tell it that it may emit a task using the syntax the editor
already understands — `/task[.type] <description> [#tags]` alone on its own line — and that the reply's
qualifying lines be run through the existing capture path when it comes back.

---

## Overview

Today an assistant asked "what did I commit to in this meeting?" can only answer in prose. Nothing in
that answer is a real task: it has no id, it is not in `tasks.md`, and the line in the document is not a
mirror of anything. Turning the answer into tasks means retyping each one through `/task`, which is slow
enough that the user stops asking for that kind of summary at all.

The gap is not in the grammar — the grammar already exists. The editor accepts `/task <description>`
and `/task.<type> <description>` on a line of its own, lifts `#tags` out of the description, creates the
task, and leaves a working checklist item pointing at it. What is missing is that the assistant is never
told the grammar exists, and that a reply's lines are inserted as text rather than read.

This feature closes that loop. Three properties define the result:

1. **One grammar, one place it is defined.** The assistant is taught the same `/task` verb, the same
   `.type` suffix, and the same `#tag` tokens the editor and the command bar already accept. Nothing new
   is invented for the assistant, and a task it produces is indistinguishable from one the user typed —
   same format, same tag extraction, same validation, same provenance link to the document.
2. **A summary that reads normally, with real tasks inside it.** Task lines may sit anywhere in the
   reply, interleaved with ordinary prose. Each qualifying line is captured and replaced in place by the
   link to the task it created; every other line is inserted exactly as written.
3. **Nothing is captured by surprise, and nothing is lost.** Only a line whose entire content is the
   command counts — a reply that merely explains the syntax, quotes it in a code fence, or mentions it
   mid-sentence creates no tasks. If a capture fails, the words still land in the document.

A reply with no task lines behaves exactly as `/ai` does today.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask for my commitments and get real tasks (Priority: P1)

At the end of a meeting the note-taker types `/ai summarise what I committed to above, capture each one
as a followup` and presses enter. The reply arrives as a short paragraph and three commitments. Where the
assistant wrote each commitment as a task line, the document now shows a checklist item linking to a real
task in `tasks.md`. The rest of the reply is ordinary prose, as always. Nothing was retyped.

**Why this priority**: This is the feature. Everything else here bounds what gets captured or protects
what happens when a capture fails; without this, none of it exists. On its own it removes the reason this
kind of summary goes unasked for.

**Independent Test**: Open a document, run an `/ai` request whose reply contains task lines interleaved
with prose, and confirm that each task line became a checklist item linking to a task with the right
description, type, and tags, that the prose landed unchanged and in order, and that the editor did not
move.

**Acceptance Scenarios**:

1. **Given** the editor is open on a document, **When** an assistant reply contains a line whose entire
   content is `/task.followup call Terry about the renewal #procurement`, **Then** a task is created with
   description "call Terry about the renewal", type "followup", and tag "procurement".
2. **Given** the same reply, **When** it is inserted, **Then** that line appears in the document as a
   checklist item linking to the new task, not as the text the assistant wrote.
3. **Given** a reply of prose and task lines interleaved, **When** it is inserted, **Then** every
   non-task line is inserted exactly as written and the original order of all lines is preserved.
4. **Given** a reply containing several task lines, **When** it is inserted, **Then** every one of them is
   captured, in the order they appear.
5. **Given** a task line with no type suffix, such as `/task buy milk`, **When** it is captured, **Then**
   the task is created with no type, exactly as the editor's own `/task` does.
6. **Given** a reply that contains no task lines, **When** it is inserted, **Then** the result is
   identical to what `/ai` produces today — no capture, no message about tasks, no change in behaviour.
7. **Given** any reply, **When** it is inserted, **Then** the editor keeps focus and no screen or
   collection change occurs.
8. **Given** a reply that captured one or more tasks, **When** insertion completes, **Then** the user is
   told how many tasks were captured.

---

### User Story 2 - The assistant is told the grammar, on the same terms every time (Priority: P2)

The user has `claude` configured today and switches to `copilot` tomorrow. Both are told the same thing
about task lines, in the same words, because the instruction lives with the prompt rather than with
either assistant.

**Why this priority**: The capture path is worthless if the assistant never emits a task line, and a
grammar that only one assistant knows is a feature the user cannot rely on. It is separable from Story 1
— the instruction can be verified in the composed prompt without invoking anything.

**Independent Test**: Compose a prompt for each configured assistant and confirm both carry the same task
syntax instruction, stating the form, that the line must be the whole line, and what happens to it.

**Acceptance Scenarios**:

1. **Given** any configured assistant, **When** a prompt is composed for an `/ai` request from a
   document, **Then** it states that the assistant may emit a task as `/task <description>` or
   `/task.<type> <description>` alone on its own line, that `#tags` in the description are lifted out, and
   that such a line becomes a link to the task choom creates.
2. **Given** two different configured assistants, **When** prompts are composed for the same request,
   **Then** the task syntax instruction is identical in both.
3. **Given** the composed prompt, **When** it is read, **Then** it presents task lines as available, not
   required — a reply with none is a normal reply.
4. **Given** an `/ai` request made while editing a task's own body rather than a document, **When** the
   prompt is composed, **Then** it does not offer the task syntax, because there is no document identity
   to capture from.

---

### User Story 3 - Nothing is captured by surprise (Priority: P3)

The user asks "how do I capture a task from in here?" The assistant answers by explaining the syntax and
showing an example in a code fence. No task is created. The explanation lands in the document as an
explanation.

**Why this priority**: A tool that creates records from text that was only describing them is a tool the
user stops trusting with the editor. The boundary has to be as reliable as the capture itself, and it is
testable independently of whether any capture ever succeeds.

**Independent Test**: Drive a reply containing the command inside a code fence, indented under a bullet,
and mid-sentence, and confirm no task is created and the text is inserted exactly as written.

**Acceptance Scenarios**:

1. **Given** a reply line reading `You can type /task call Terry to capture that.`, **When** the reply is
   inserted, **Then** no task is created and the line is inserted as written.
2. **Given** a reply containing `/task call Terry` inside a fenced code block, **When** the reply is
   inserted, **Then** no task is created and the fence is inserted as written.
3. **Given** a reply line that is indented — `  /task call Terry`, or the same line nested under a bullet
   — **When** the reply is inserted, **Then** no task is created and the line is inserted as written,
   matching the editor's own rule that the command must be the entire line.
4. **Given** a reply line reading `/task` or `/task.followup` with no description, **When** the reply is
   inserted, **Then** no task is created, the line is inserted as written, and the user is told a
   description was missing.
5. **Given** a reply line that is `/ai ...`, `/link ...`, or any other command, **When** the reply is
   inserted, **Then** it is inserted as written — `task` is the only verb a reply can act on, and a reply
   can never trigger a further assistant request or link insertion.
6. **Given** an `/ai` request made while editing a task's own body, **When** the reply contains a task
   line, **Then** no task is created and the line is inserted as written.

---

### User Story 4 - The captured tasks behave like every other task (Priority: P4)

A week later the user opens one of the captured tasks. It names the meeting it came from, and one
keystroke opens that meeting. Ticking it off in the tasks list ticks the checkbox in the meeting note,
and ticking the note's checkbox completes the task.

**Why this priority**: This is what makes the capture worth having rather than a formatted list, and it
should cost nothing to build — it is the behaviour 009 already defined for the checklist items the editor
inserts. It is listed separately because it is what a reviewer must actually verify rather than assume.

**Independent Test**: Capture tasks from a reply inside a meeting, then confirm the task names the
meeting, that the meeting's inbound links list the task, and that completing it from either end updates
the other.

**Acceptance Scenarios**:

1. **Given** a task captured from a reply, **When** its line in the tasks file is inspected, **Then** it
   carries a link to the source document's id in the same field an editor-typed capture uses — no field
   specific to this feature.
2. **Given** a task captured from a reply and one captured by typing `/task` with the same words,
   **When** both lines are compared, **Then** they differ only in id and timestamp.
3. **Given** a checklist item inserted from a reply, **When** the task is completed from the tasks list,
   **Then** the item is ticked on the same terms as any other mirror.
4. **Given** a checklist item inserted from a reply, **When** the user ticks it and saves, **Then** the
   task is completed on the same terms as any other mirror.
5. **Given** a checklist item just inserted from a reply, **When** the document is next saved, **Then**
   the new item is not mistaken for a box the user ticked or unticked.

---

### User Story 5 - A failed capture never costs the reply (Priority: P5)

The tasks file is momentarily unwritable — it is open elsewhere, or the workspace is on a synced drive
mid-conflict. The assistant's reply still lands in the document, in full. The lines that could not be
captured are inserted as the assistant wrote them, and the user is told which ones failed.

**Why this priority**: Losing the answer to a request that took thirty seconds to run is far worse than
not capturing the tasks in it. It is the last story because it only matters when something else has
already gone wrong.

**Independent Test**: Make the tasks file unwritable, run a request whose reply contains task lines, and
confirm the whole reply reaches the document, the failing lines are present as text, and a message names
the failure.

**Acceptance Scenarios**:

1. **Given** a reply with task lines and the tasks file cannot be written, **When** the reply is inserted,
   **Then** every line of the reply reaches the document and no text is dropped or truncated.
2. **Given** the same, **When** insertion completes, **Then** a message names the failure rather than
   failing silently.
3. **Given** a reply with several task lines where one capture fails, **When** the reply is inserted,
   **Then** the remaining lines are still captured and only the failing one is inserted as written.
4. **Given** a request the user cancels, or one the assistant fails, **When** it ends, **Then** the
   `/ai` line is restored exactly as today and no task is created.
5. **Given** a reply whose captures partly succeeded, **When** the user undoes in the editor, **Then**
   only the document text is affected — the tasks that were created remain, exactly as an editor-typed
   capture behaves today.

---

### Edge Cases

- **A reply that is nothing but task lines.** Every line is captured and the document receives only
  checklist items. This is a valid reply, not an error.
- **Two identical task lines in one reply.** Both are captured as separate tasks, exactly as typing the
  same `/task` line twice would. Deduplication is not this feature's job.
- **A task line whose description is only tags** (`/task #procurement`). Handled by the existing
  description validation — the same message the editor gives today.
- **A very long reply with many task lines.** Every qualifying line is captured; there is no cap, and no
  partial insertion — the document receives the whole reply.
- **The source document is deleted or renamed between the request being sent and the reply arriving.**
  The capture reports the failure per Story 5 and the reply text still lands.
- **A reply arriving after the editor has moved on** (the request was superseded). Unchanged from today:
  the reply is discarded and no task is created.
- **A task captured from a reply is later deleted.** Unchanged from 011: the checklist item left in the
  document keeps the user's words rather than disappearing. This feature adds no deletion behaviour.
- **A task line inside a fenced block that is never closed.** Treated as inside the fence — the reply is
  inserted as written and nothing is captured, which is the safe direction.
- **A reply containing `/task` inside an inline code span.** The line is not entirely the command, so it
  is ordinary text and nothing is captured.

## Requirements *(mandatory)*

### Functional Requirements

**Teaching the assistant**

- **FR-001**: The prompt composed for an assistant MUST state that the assistant may emit a task by
  writing `/task <description>` or `/task.<type> <description>` alone on its own line.
- **FR-002**: The instruction MUST state that `#tags` written in the description are lifted out of it and
  attached to the task, so the assistant does not have to encode tags separately.
- **FR-003**: The instruction MUST state what happens to such a line — choom creates the task and
  replaces the line with a link to it — so the assistant can write a reply that reads correctly once the
  substitution has happened.
- **FR-004**: The instruction MUST state that the command must be the line's entire content, unindented,
  and outside any code fence, and that a line failing those conditions is left as ordinary text.
- **FR-005**: The instruction MUST present task lines as available rather than required; a reply with none
  is a normal reply.
- **FR-006**: The instruction MUST be identical for every configured assistant. No assistant-specific
  wording, and no assistant may receive a different grammar.
- **FR-007**: The instruction MUST be omitted when the request originates somewhere with no document
  identity to capture from — editing a task's own body — and any task line in such a reply MUST be
  inserted as written.

**Acting on the reply**

- **FR-008**: On a successful reply, the system MUST identify every line whose entire content is a task
  command and capture each one through the same path an editor-typed `/task` uses — same parser, same tag
  extraction, same type suffix handling, same validation.
- **FR-009**: Each captured line MUST be replaced, in the text inserted into the document, by the
  checklist item linking to the task it created.
- **FR-010**: Every line of the reply that is not a captured task line MUST be inserted exactly as
  written, with the reply's original line order preserved.
- **FR-011**: A reply containing no task lines MUST behave exactly as it does today — no capture attempt,
  no additional message, no change to how the reply is inserted.
- **FR-012**: A line inside a fenced code block MUST NOT be captured.
- **FR-013**: A line with leading whitespace MUST NOT be captured, matching the editor's existing rule
  that the command is the entire line.
- **FR-014**: `task` MUST be the only command a reply can act on. A reply line naming any other command,
  registered or not, MUST be inserted as written — a reply can never trigger a further assistant request,
  a link insertion, or any other command.
- **FR-015**: A task line with no description MUST NOT create a task; the line MUST be inserted as
  written and the user told a description was required.
- **FR-016**: A capture that fails MUST NOT prevent the rest of the reply from being inserted or the
  remaining task lines from being captured. The failing line MUST be inserted as written.
- **FR-017**: No part of a reply may be dropped or truncated by this feature, under any failure.
- **FR-018**: When a reply captures one or more tasks, the user MUST be told how many were captured;
  when any capture failed, the user MUST be told that, naming the reason.
- **FR-019**: A cancelled or failed request MUST behave exactly as today — the `/ai` line is restored and
  no task is created.
- **FR-020**: Inserting a reply MUST NOT move the user off the editor, change the collection, or push a
  screen; the editor keeps focus, as it does today.

**What the captured task is**

- **FR-021**: A task captured from a reply MUST be indistinguishable from one captured by typing the same
  `/task` line in the editor, apart from its id and timestamp — including the link recording the source
  document.
- **FR-022**: A checklist item inserted from a reply MUST participate in mirror reconciliation in both
  directions on the same terms as one inserted by typing the command.
- **FR-023**: A checklist item just inserted from a reply MUST NOT be read at the next save as a state
  change the user made.
- **FR-024**: Undo in the editor MUST affect only the document buffer. Tasks created by the reply are not
  removed by undo, exactly as an editor-typed capture behaves today.

### Key Entities

- **Composed prompt**: The text handed to the assistant for an `/ai` request. Gains the task syntax
  instruction; otherwise unchanged.
- **Assistant reply**: The text the assistant returns. Now read line by line before insertion rather than
  inserted whole.
- **Task line**: A line of a reply whose entire content is `/task[.<type>] <description>`, unindented and
  outside a code fence. The unit this feature acts on.
- **Task**: Unchanged. A task captured from a reply is an ordinary task carrying a link to the document
  the request came from.
- **Mirror (checklist item)**: Unchanged. The link left in the document in place of a captured task line,
  and a control surface onto the task's state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from "summarise what I committed to above" to real, linked tasks in one
  keystroke, retyping no descriptions — the same single action whether the reply captures zero tasks or
  ten.
- **SC-002**: 100% of a reply's text reaches the document, including when every capture in it fails.
- **SC-003**: A task captured from a reply and one captured by typing the same command differ only in id
  and timestamp when their lines in the tasks file are compared.
- **SC-004**: A reply containing no task lines produces exactly the document text it produces today.
- **SC-005**: Zero tasks are created by replies that merely describe the syntax — in a code fence,
  indented, or mid-sentence.
- **SC-006**: Every configured assistant receives the identical task syntax instruction, verifiable
  without invoking either one.
- **SC-007**: A user who captures tasks this way can complete them from the tasks list or from the note
  and see the other side agree, with no additional step.

## Assumptions

- **The grammar is not new and is not extended.** `/task` with an optional `.type` suffix and inline
  `#tags` is what the editor and command bar already accept; this feature teaches it and applies it to
  reply lines rather than defining anything.
- **Only `/task` is acted on from a reply.** The issue names only task capture, and letting a reply
  trigger `/ai` or `/link` would let one request spawn another. Other commands stay text (FR-014).
- **Code fences are excluded.** A reply that explains the syntax with an example is a normal reply, and
  creating tasks from it would be the least forgivable failure mode. Fence tracking applies to the reply
  text only.
- **The instruction is unconditional for document targets.** It is included in every composed prompt from
  a document, not gated on a setting — a setting that could be a sensible default must be a sensible
  default (Constitution III), and the assistant is told the lines are optional.
- **The reply's captures write to the tasks file; the reply's text stays an unsaved buffer edit.** The
  document is already saved before the request is sent, so nothing typed before it can be lost; the
  inserted reply is the user's to keep or discard, exactly as today.
- **Task ordering follows the reply.** Lines are captured top to bottom, so tasks appear in the order the
  assistant listed them.
- **No cap on captures per reply.** A summary of a long meeting may legitimately produce many followups.
- **Scope is the TUI editor's `/ai` path.** The CLI has no assistant invocation to change.

## Dependencies and Relationships

- **Builds on 006 (assistant invocation, issue #19).** The composed prompt, the in-flight and
  cancellation behaviour, and the reply insertion path all come from that feature; this changes what the
  prompt says and what happens to the reply text on the way in.
- **Reads the reply after it has been reduced to the assistant's answer (issue #69).** Each assistant's
  reply is already narrowed to its final answer — tool-call narration and status chatter stripped —
  before anything inserts it. This feature reads that answer, so what counts as a line here is a line the
  user would have seen in the document, and no line of an assistant's transport format can create a task.
  That reduction stays per-assistant; the task syntax instruction (FR-006) does not.
- **Builds on 009 (inline task capture, issue #21).** The capture path, the mirror checklist item, the
  provenance link, and reconciliation in both directions are reused unchanged. This feature adds no task
  behaviour of its own.
- **Reuses the existing command parser and tag extraction.** The line grammar, the `.type` suffix split,
  and lifting `#tags` out of a description are shared with the editor and the command bar, so the three
  can never disagree about what a task line means.
- **Related to issue #37** (`/config assistant` dropping skill files). Both address "the assistant needs
  to be told how choom works" — #37 at the install and discovery layer, this at the reply layer. Neither
  blocks the other, and the workspace's `AGENTS.md` already documents the `/task` line for assistants
  reading the workspace directly.

## Out of Scope

- Any new command, verb, suffix, or tag syntax.
- Acting on `/link`, `/ai`, or any other command emitted by an assistant.
- Having the assistant write `tasks.md` directly. Placement, id, and the mirror stay choom's
  responsibility, which is what the format conventions exist for.
- Assistant invocation from the CLI.
- Deduplicating or merging tasks a reply captures against tasks that already exist.
- Capturing into a document other than the one the request was made from.
- Any change to how a task is completed, listed, or rendered.
