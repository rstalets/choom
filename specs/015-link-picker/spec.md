# Feature Specification: A Picker for Ambiguous `/link`

**Feature Branch**: `015-link-picker`

**Created**: 2026-08-01

**Status**: Draft

**Input**: User description: "issue #46. You are 015"

**Source**: GitHub issue #46 "[Feature]: /link offers a picker when several records match", which asks
that `/link <terms>` stop failing closed when the search matches more than one record, and instead
raise a selection list from the status bar so the writer chooses from what was found without leaving
the document.

---

## Overview

`/link <terms>` inserts a markdown link to another record, but only when the search matches exactly
one. Every other outcome ends the same way: the typed line is left alone and the status bar reports
either "no match" or the names of the candidates. That was a deliberate choice — a picker looked like
it would contradict *never take the user out of the document*.

In use, the rule is too strict and the rejection is the common case, not the exception. One word is
usually ambiguous: `/link research` matches every research note, `/link meeting` matches most of the
collection. And being told the answer is not the same as getting it — a status bar that names three
candidates hands the writer a puzzle (guess which word narrows it, retype the query) at exactly the
moment they were mid-sentence.

The reasoning also does not survive contact with what is being proposed. "Never take the user out of
the document" rules out a modal picker *screen*. A short list rising from the status-bar region is an
inline affordance, closer to autocomplete than to a dialog: the document stays on screen, the cursor
does not move, no screen transition occurs, and `esc` returns to exactly where the writer was. It is a
widget in the same sense the in-flight `/ai` status is a widget — not a fourth state in the
list → preview → edit model.

Three properties define the feature:

1. **Ambiguity becomes a choice, never a rejection.** More than one match raises the list. The writer
   picks with the keys already on the home row of this interface — `↑`/`↓`, `enter`, `esc`.
2. **The fast paths are untouched.** Exactly one match still inserts directly, with no list and no
   extra keystroke. Zero matches still reports, because there is nothing to choose from.
3. **The document does not move.** No screen change, no cursor movement, no scroll. Dismissing leaves
   the line exactly as it was typed.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose from the records that matched (Priority: P1)

Someone writing a meeting note types `/link research` on its own line and submits it. Four research
notes match. Instead of a status line naming them and stopping, a short list rises from the bottom of
the editor with those four records in it, the first one highlighted. They press `↓` once, press
`enter`, and the line becomes a markdown link to the record they chose. They keep typing.

If they decide they picked the wrong search terms, `esc` closes the list and leaves the line reading
`/link research`, ready to be edited and submitted again.

**Why this priority**: This is the feature. Every other story refines a list that this one has to make
exist first. On its own it converts the most common `/link` outcome from a dead end into a completed
link, which is the entire value the issue asks for.

**Independent Test**: In a workspace with several records sharing a word, open a document in the
editor, submit `/link <that word>`, and confirm a list appears, that `↑`/`↓` move the highlight, that
`enter` replaces the line with a working link to the highlighted record, and that `esc` leaves the
line byte-identical to what was typed.

**Acceptance Scenarios**:

1. **Given** a workspace where three records match the search terms, **When** the writer submits
   `/link <terms>` in the editor, **Then** a selection list appears in the status-bar region showing
   all three, with the first row highlighted, and the document remains visible above it.
2. **Given** the selection list is open, **When** the writer presses `↓` and then `enter`, **Then**
   the `/link` line is replaced by a markdown link to the second record in the list and the list
   closes.
3. **Given** the selection list is open, **When** the writer presses `esc`, **Then** the list closes,
   the line still reads exactly what was typed, and the cursor is where it was before the list opened.
4. **Given** the selection list is open and the highlight is on the first row, **When** the writer
   presses `↑`, **Then** the highlight moves to the last row (and pressing `↓` from the last row moves
   it to the first).
5. **Given** a record is chosen from the list, **When** the inserted link is followed, **Then** it
   resolves to that record — the path is correct relative to the file being edited, exactly as it
   would be for a single-match insertion.
6. **Given** the selection list is open, **When** it is displayed, **Then** the footer states the keys
   that act on it (`↑`/`↓` to move, `enter` to insert, `esc` to cancel).

---

### User Story 2 - Tell the candidates apart at a glance (Priority: P2)

Two records are both called "Q3 planning" — one a meeting from last week, one a note from March. A
list of bare titles cannot be chosen from; the writer would have to leave the document to work out
which is which, which is the thing this feature exists to avoid.

Each row therefore carries the record's title, which collection it belongs to, and its date. And the
list is ordered newest first, because the record someone wants to link is overwhelmingly the one they
just wrote — the same assumption `meeting list` already makes.

**Why this priority**: A picker that cannot be chosen from correctly is a slower version of the
problem. It is P2 rather than P1 only because the list has to exist before its rows can be judged.

**Independent Test**: Create two records with the same title in different collections and on different
dates, submit a `/link` search matching both, and confirm each row shows title, collection, and date,
and that the newer record is listed first.

**Acceptance Scenarios**:

1. **Given** two matching records share a title, **When** the list is shown, **Then** each row shows
   the record's title, its collection, and its date, so the two rows are distinguishable.
2. **Given** matching records were created on different dates, **When** the list is shown, **Then**
   rows appear newest first.
3. **Given** two matching records share a date, **When** the list is shown, **Then** their relative
   order is by title, so the same search always produces the same order.
4. **Given** a matching record has no date recorded, **When** the list is shown, **Then** that row
   still appears, sorts after every dated row, and shows a placeholder in place of a date rather than
   being omitted or blank-sorted to the top.
5. **Given** a matching record's title is longer than the width available, **When** the list is shown,
   **Then** the title is truncated rather than wrapped or pushing the collection and date off the row.

---

### User Story 3 - The document is never disturbed (Priority: P3)

The list is an affordance over the document, not a departure from it. Whatever happens — a choice, a
dismissal, a search that finds one record, a search that finds none — the writer ends up in the same
place in the same document, and the interface never gains a state they have to get back out of.

**Why this priority**: This is the constraint the original decision was protecting, and the one the
feature has to demonstrate it respects. It is P3 because it is verified against a list that stories 1
and 2 build, but a failure here would invalidate the whole approach.

**Independent Test**: With a long document scrolled to the middle, submit an ambiguous `/link`, and
confirm through both outcomes (insert and cancel) that the visible portion of the document, the cursor
position, and the screen itself are unchanged apart from the edited line.

**Acceptance Scenarios**:

1. **Given** a long document scrolled so the `/link` line is mid-screen, **When** the list opens,
   **Then** the document stays on screen and its scroll position does not change.
2. **Given** the list is open, **When** any key other than the keys the footer names is pressed,
   **Then** the document is not modified by it.
3. **Given** exactly one record matches, **When** `/link <terms>` is submitted, **Then** the link is
   inserted directly with no list shown and no additional keystroke required.
4. **Given** no record matches, **When** `/link <terms>` is submitted, **Then** the existing status-bar
   message is shown, no list appears, and the typed line is left as-is.
5. **Given** the list is open, **When** the writer inserts or cancels, **Then** the editor is left in
   the editing state it was in — not a preview, not a list screen — with the cursor available for
   typing immediately.

---

### Edge Cases

- **More matches than fit on screen.** A one-word search in a large workspace can match dozens of
  records. The list occupies a bounded number of rows and scrolls within itself as the highlight moves
  past either end; it never grows to swallow the document.
- **A very short terminal.** When there is not enough room to show a usable list, the interface must
  still do something honest — the existing report-and-stop behaviour is the correct fallback rather
  than a one-row list or a broken layout.
- **The record disappears between listing and choosing.** The workspace is a folder of files that
  another program can change. If the chosen record can no longer be resolved when `enter` is pressed,
  the writer is told so and the line is left as typed, rather than a link to nothing being written.
- **A task among the candidates.** Tasks are link targets alongside meetings and notes; a task row has
  to be as identifiable as a document row even though a task's "title" is its text.
- **Duplicate everything.** Two records with the same title, collection, and date still produce two
  distinct rows, and choosing either links to that one specifically.
- **Cancelling leaves the command text behind.** After `esc` the line still reads `/link <terms>`,
  which is what lets the writer narrow the search and resubmit — matching what already happens when a
  search finds nothing.
- **Submitting `/link` with no terms.** Unchanged: the existing "needs search terms" message, no list.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When `/link <terms>` matches more than one record, the system MUST present a selection
  list of the matching records instead of reporting the candidates and stopping.
- **FR-002**: The selection list MUST be presented within the editor's status-bar region, with the
  document remaining visible; it MUST NOT be a separate screen and MUST NOT introduce a new state in
  the list → preview → edit model.
- **FR-003**: The system MUST NOT move the cursor or change the document's scroll position when the
  list opens, while it is open, or when it closes.
- **FR-004**: `↑` and `↓` MUST move the highlight between rows, wrapping at both ends.
- **FR-005**: `enter` MUST replace the `/link` line with a markdown link to the highlighted record,
  using the same link format and the same relative-path computation as a single-match insertion, and
  MUST close the list.
- **FR-006**: `esc` MUST close the list and leave the `/link` line byte-identical to what the writer
  typed.
- **FR-007**: While the list is open, the footer MUST state every key that acts on it, and keys other
  than those MUST NOT modify the document.
- **FR-008**: Each row MUST show the record's title, its collection, and its date.
- **FR-009**: Rows MUST be ordered newest first, with ties broken by title so repeating a search
  produces the same order; records with no date MUST sort after all dated records.
- **FR-010**: The list MUST occupy a bounded number of rows regardless of how many records match, and
  MUST scroll within itself when the match count exceeds what it shows.
- **FR-011**: When exactly one record matches, the system MUST insert the link directly, with no list
  and no additional keystroke.
- **FR-012**: When no record matches, the system MUST report as it does today and MUST NOT show a list.
- **FR-013**: If the highlighted record cannot be resolved at the moment of insertion, the system MUST
  report that and leave the line as typed rather than inserting an unresolvable link.
- **FR-014**: The set of records the list offers MUST be exactly what the current `/link` search
  finds — titles, ids, types, and tags — with no change to what counts as a match.
- **FR-015**: When the available space is too small to render a usable list, the system MUST fall back
  to the existing report-and-stop behaviour rather than rendering a degraded list.

### Key Entities

- **Link candidate**: One record the search matched, as offered in the list. Carries the title shown,
  the collection it belongs to (meeting, note, or task), its date, and enough identity to insert a
  link to it. Distinct from any other candidate even when title, collection, and date coincide.
- **Selection list**: The ordered set of candidates currently offered, plus which one is highlighted.
  Exists only while a choice is pending; it is not written anywhere and does not survive dismissal.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A writer who submits an ambiguous `/link` search completes the link without leaving the
  document and without retyping the search — at most two keystrokes beyond submitting the command for
  any candidate visible in the list.
- **SC-002**: Of the `/link` searches that match at least one record, 100% can be completed to an
  inserted link, compared with only the exactly-one-match subset today.
- **SC-003**: Two records that share a title are distinguishable from their rows alone, with no need
  to open, preview, or search for either.
- **SC-004**: The cursor position, scroll position, and current screen after inserting or cancelling
  are identical to what they were before the command was submitted, in every case.
- **SC-005**: The single-match and zero-match paths require the same number of keystrokes after this
  change as before it.
- **SC-006**: The list appears without a perceptible pause after the command is submitted, in a
  workspace of a thousand records.

## Assumptions

- The list is keyboard-only. Mouse or click selection is not assumed, consistent with the rest of the
  interface.
- The candidate set is fixed when the list opens. Typing while it is open does not re-filter it —
  narrowing means cancelling and submitting new terms. Filter-as-you-type is a separate feature and is
  not assumed here.
- Keys other than `↑`, `↓`, `enter`, and `esc` are ignored while the list is open, rather than
  dismissing it and passing through, so no keystroke aimed at the list can land in the document.
- "Newest first" reads the record's own recorded date (the same date the collection listings sort by),
  not file modification time.
- The command line is saved before the search runs, exactly as `/link` does today; opening the list
  does not add or remove a save.
- Records are identified in rows by collection name (meeting, note, task), the same vocabulary the
  rest of the interface uses.
- The existing search already reports every match with the identity a row needs; ordering newest-first
  is the one guarantee it does not currently make.

## Out of Scope

- Fuzzy or ranked matching. Matching stays exactly what it is today.
- Searching document bodies. Titles, ids, types, and tags only.
- Any picker outside the editor — the CLI's link authoring is unchanged, and no list screen or preview
  surface gains one.
- Filtering or refining the candidate list once it is open.
- Multi-select, or inserting more than one link from a single command.
- Creating a record from the picker when nothing suitable matched.

## Dependencies

- Builds on the shipped document-links primitive (issue #27, spec `008-document-links`), which defines
  the link format, `find_link_targets`, and the `/link` command this extends.
- Uses the editor's existing slash-command plumbing, shared with `/ai` and `/link` today. This feature
  adds a widget and a selection handler, not a new command surface.
- The multi-word search fix has landed, so ambiguity is hit less often than when issue #46 was
  written. It does not remove ambiguity, and this feature is what handles what remains.
- Related: inline task capture (issue #21) will want the same picker if it grows a "link this task to
  a document" step. Nothing here is designed to preclude that, and nothing here waits on it.
