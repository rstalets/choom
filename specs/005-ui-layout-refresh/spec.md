# Feature Specification: UI Layout Refresh

**Feature Branch**: `005-ui-layout-refresh`

**Created**: 2026-07-30

**Status**: Draft

**Input**: User description: "Issue 17"

**Source**: GitHub issue #17 "UI Improvements" (milestone v0.0.2), which asks for an updated layout
grid, month-scoped loading, explicit command verbs, a help pane, a version indicator, and two
hotkey fixes.

**Builds on**: Features `001-meeting-notes`, `002-general-notes`, `003-tasks`, and
`004-viewing-editing`, which delivered the workspace, the frontmatter schema, the three-pane
list/preview screen, the vertical collection menu, the `/` command bar, task toggling, and the
preview → edit state machine. This feature rearranges that surface and changes how much of the
workspace is read to fill it; it adds no new document types and no new storage.

**Scope note**: This is a terminal-interface feature end to end. It adds no command-line surface,
because none of it is behaviour — it is presentation and navigation of behaviour the command line
already exposes (`endpaper meetings`, `endpaper notes`, `endpaper tasks`, and their filter flags).
The one exception is the version indicator, whose value must match what the command line already
reports.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Collections live along the top, and Tab walks them (Priority: P1)

The user opens endpaper and sees, on a single line at the top, the product name, a divider, and the
three collections. The one they are looking at is visibly highlighted. Pressing Tab moves one
collection to the right and the whole content area follows immediately; shift+Tab moves left. They
never navigate into a menu, never press Enter to commit the choice, and never lose a pane of screen
width to a list of three words.

**Why this priority**: Every other story in this feature assumes the left pane is free. Today the
left pane holds the collection menu, so month navigation and task categories have nowhere to live.
Moving collections to the top is the structural change the rest hangs off, and it stands alone: on
its own it already makes switching collections one keystroke instead of three and returns a third
of the horizontal space to the list and preview.

**Independent Test**: Launch the tool, confirm the top bar lists all three collections with exactly
one highlighted, press Tab and shift+Tab through every position, and confirm the list and preview
panes show the highlighted collection's contents at each stop without any further keypress.

**Acceptance Scenarios**:

1. **Given** the tool is launched, **When** the list screen appears, **Then** the top line reads the
   product name, a divider, and the collection names in the order Tasks, Notes, Meetings, with
   exactly one collection highlighted and the content area showing that collection.
2. **Given** Notes is highlighted, **When** the user presses Tab, **Then** Meetings becomes
   highlighted, the middle pane lists meetings, and the left and right panes show the meeting
   collection's left-pane content and preview.
3. **Given** Notes is highlighted, **When** the user presses shift+Tab, **Then** Tasks becomes
   highlighted and the content area shows tasks.
4. **Given** the rightmost collection is highlighted, **When** the user presses Tab, **Then** the
   leftmost collection becomes highlighted.
5. **Given** the leftmost collection is highlighted, **When** the user presses shift+Tab, **Then**
   the rightmost collection becomes highlighted.
6. **Given** any collection is highlighted, **When** the user switches to it, **Then** the keyboard
   is already positioned on the middle pane with its top row highlighted, with no extra keypress.
7. **Given** the command bar is open and receiving text, **When** the user presses Tab, **Then** the
   collection selection does not move and the keystroke is handled by the bar.

---

### User Story 2 - One month at a time (Priority: P1)

The user opens Notes or Meetings and sees the current month and year in the left pane, with the
middle pane already listing that month's documents. Moving up or down the left pane moves to an
adjacent month, and the middle pane follows. A workspace with three years of standups opens as
fast as an empty one, because only the month on screen has been read.

**Why this priority**: This is the performance half of the issue and the reason the left pane was
freed. Today every launch reads every markdown file under `meetings/` and `notes/`, so start-up
cost grows without bound as the workspace fills — precisely as the tool becomes worth keeping. It
is independently testable and independently valuable: the layout from Story 1 is usable without it,
but a workspace with a year of history is not.

**Independent Test**: Populate a workspace with documents across several months, open the tool, and
confirm that only the current month's files were read and that the middle pane lists exactly that
month's documents; then move to an adjacent month and confirm the middle pane changes and only that
month's files were read.

**Acceptance Scenarios**:

1. **Given** a workspace with notes in several months, **When** the user selects Notes, **Then** the
   left pane shows the current month and year highlighted, and the middle pane lists only that
   month's notes, newest first.
2. **Given** the left pane has focus with a month highlighted, **When** the user moves the highlight
   to an adjacent month, **Then** the middle pane lists that month's documents and the preview shows
   the top document of that month.
3. **Given** a month is displayed and no filter is active, **When** the middle pane is filled,
   **Then** no document outside that month has been read from disk during that action.
4. **Given** the current month contains no documents, **When** the user selects the collection,
   **Then** the current month is still shown and highlighted in the left pane and the middle pane
   shows the collection's empty-state message.
5. **Given** the user has moved to an earlier month, **When** they switch to another collection and
   back, **Then** the collection opens on the current month again.
6. **Given** the user creates a document while an earlier month is displayed, **When** the create
   completes, **Then** the displayed month becomes the new document's month and the new document is
   the highlighted row.
7. **Given** a month whose documents include one with unreadable frontmatter, **When** that month is
   displayed, **Then** the readable documents are listed and the warning count for the collection
   reflects only the displayed month.

---

### User Story 3 - To-Do and Done are places, not a toggle (Priority: P2)

The user opens Tasks and lands in To-Do with the top task highlighted, ready to press space. When
they want to see what they finished, they move to Done in the left pane instead of remembering a
toggle key. The right pane stays blank — a task has nothing to preview.

**Why this priority**: Tasks are the collection the user touches most often, and today "show done"
is an invisible mode behind a single letter with no on-screen indication of which mode is active.
Making it a pane makes the state visible. It ranks below the month panes because task volume is
bounded by a single file, so nothing here is a performance fix.

**Independent Test**: Open Tasks with a mix of open and completed tasks, confirm To-Do is
highlighted and lists only open tasks, move to Done and confirm it lists only completed tasks, and
confirm the right pane is blank throughout.

**Acceptance Scenarios**:

1. **Given** the user selects Tasks, **When** the collection opens, **Then** the left pane shows
   To-Do and Done with To-Do highlighted, the middle pane lists open tasks with the top one
   highlighted, and the keyboard is on the middle pane.
2. **Given** To-Do is highlighted, **When** the user moves the left-pane highlight to Done, **Then**
   the middle pane lists only completed tasks.
3. **Given** Done is displayed, **When** the user toggles a task back to open, **Then** the task
   leaves the Done list and appears in To-Do.
4. **Given** To-Do is displayed, **When** the user toggles a task complete, **Then** the task leaves
   the To-Do list and appears in Done.
5. **Given** any task is highlighted in the middle pane, **When** the screen is drawn, **Then** the
   right pane is blank.
6. **Given** a new task is created from the command bar while Done is displayed, **When** the create
   completes, **Then** To-Do is displayed with the new task highlighted.

---

### User Story 4 - Editing starts where the user is looking (Priority: P2)

The user highlights yesterday's standup in the list and presses `e`. The editor opens on that
document. When they create a new note, they are typing into it immediately rather than staring at a
rendered empty page and pressing another key to start writing.

**Why this priority**: `e` already means "edit" one screen deeper, and today it does nothing in the
list — a dead key that teaches the user the wrong thing. Creating a document and being shown a
read-only view of the thing you just made, with nothing in it, is the most common wasted keystroke
in the tool. Both are small, independent, and immediately felt.

**Independent Test**: From the list, highlight a document and press `e`; confirm the editor opens on
that document's raw markdown. Separately, create a document from the command bar and confirm the
editor opens on it with no intervening read view.

**Acceptance Scenarios**:

1. **Given** a document is highlighted in the middle pane, **When** the user presses `e`, **Then**
   the editor opens containing that document's raw markdown, with the same save and exit keys as the
   editor reached through the preview.
2. **Given** the editor was opened with `e` from the list, **When** the user saves and exits,
   **Then** they land back on the list with that document still highlighted and its row reflecting
   any title, type, or tag change.
3. **Given** a task is highlighted in the middle pane, **When** the user presses `e`, **Then**
   nothing happens and no editor opens.
4. **Given** the middle pane shows an empty-state message, **When** the user presses `e`, **Then**
   nothing happens.
5. **Given** the user creates a note or meeting from the command bar, **When** the create succeeds,
   **Then** the editor opens on the new document with its frontmatter present and the cursor ready
   for input, without a read-only view appearing first.
6. **Given** the user opens today's daily note from the command bar, **When** it opens, **Then** the
   editor opens on it, whether or not the note already existed.
7. **Given** the editor was opened by a create, **When** the user saves and exits, **Then** they
   land on the list, in the created document's collection and month, with the new document
   highlighted.

---

### User Story 5 - Commands are typed as commands (Priority: P3)

The user presses `/` and the slash stays on screen as a fixed prefix they cannot backspace away, so
they can see they are in command mode. Filtering is a command like any other: `/filter budget`, or
`/f budget`. Typing a word the tool does not recognise gets an error naming the problem, not a
silent reinterpretation of the word as a search term.

**Why this priority**: Today any unrecognised first word is silently treated as a filter, which
means every future command name is a breaking change waiting to happen and every typo is a search.
Making filter an explicit verb removes the collision. It is P3 because the current behaviour works
for the commands that exist today; this is the change that keeps it working as commands are added.

**Independent Test**: Press `/`, confirm a leading slash is displayed and cannot be deleted, run
`/filter <term>` and `/f <term>` and confirm both narrow the list identically, and type an
unrecognised verb and confirm an error naming it rather than a filtered list.

**Acceptance Scenarios**:

1. **Given** the list screen, **When** the user presses `/`, **Then** the command bar opens showing a
   leading `/` and the cursor positioned after it.
2. **Given** the bar is open with only the leading `/`, **When** the user presses backspace,
   **Then** the `/` remains and the bar stays open.
3. **Given** the bar is open in Notes or Meetings, **When** the user types `filter budget` and
   submits, **Then** the middle pane lists every matching document in the collection, from any
   month, newest first, and the left pane shows that the month scope is suspended.
4. **Given** the bar is open, **When** the user types `f budget` and submits, **Then** the result is
   identical to `filter budget` in every respect.
5. **Given** a filter is applied, **When** the user submits `/filter` with no term, **Then** the
   filter is cleared, the previously displayed month is restored, and its full list returns.
6. **Given** the bar is open, **When** the user types a word that is not a known command and submits,
   **Then** the list is unchanged and an error naming the unknown command is shown.
7. **Given** the bar is open with typed text, **When** the user presses escape, **Then** the bar
   closes, any filter is cleared, the previously displayed month is restored, and the keyboard
   returns to the middle pane.
8. **Given** a cross-month filter is active, **When** the user opens a matching document from
   another month and returns to the list, **Then** the filtered results are still shown with that
   document highlighted.

---

### User Story 6 - The tool explains itself, and says which one it is (Priority: P3)

The user presses `/help` and a pane slides up over the bottom of the screen listing every command
with a one-line description. Dismissing it returns them exactly where they were. The version they
are running sits in the bottom-right corner, always visible, so a bug report can name it.

**Why this priority**: With commands now explicit, they must also be discoverable — an explicit verb
the user cannot find is worse than an implicit one. The version indicator is a one-line change that
makes every future issue report actionable. Both are additive and depend on nothing else here.

**Independent Test**: Press `/help`, confirm every command the bar accepts appears with a
description, dismiss it, and confirm the underlying screen is unchanged. Separately, confirm the
bottom-right of the screen shows the running version.

**Acceptance Scenarios**:

1. **Given** the list screen, **When** the user submits `/help`, **Then** a pane appears over the
   lower part of the screen listing every command the bar accepts, each with a short description,
   including aliases.
2. **Given** the help pane is open, **When** the user presses escape, **Then** the pane closes and
   the screen underneath is unchanged, including the highlighted row, the displayed month or
   category, and any active filter.
3. **Given** the help pane is open, **When** it is drawn, **Then** the list underneath remains at
   least partly visible rather than being replaced.
4. **Given** a command exists that the bar accepts, **When** the help pane is shown, **Then** that
   command is listed — no accepted command is missing.
5. **Given** any screen of the tool, **When** it is drawn, **Then** the running version is shown in
   the bottom-right, matching the version the command line reports.

---

### Edge Cases

- **A month with no documents**: the left pane still shows and highlights it; the middle pane shows
  the collection's empty-state message; the preview is blank.
- **A workspace with no documents at all**: the left pane shows the current month alone; every pane
  is empty but navigable, and Tab still moves between collections.
- **Moving past the earliest or latest month with content**: the left pane's month range is bounded
  by the months that exist plus the current month; the highlight stops at the ends rather than
  scrolling into empty years.
- **A document dated in a month the user is not viewing** (created by an assistant, or by hand,
  while the tool is open): it is not shown until the user visits that month; nothing claims the
  workspace is empty when it is not.
- **A filter that matches nothing anywhere**: the middle pane shows an explicit "no matches" state
  distinguishable from "this month is empty", and clearing the filter restores the previously
  displayed month.
- **A filter run against a large workspace**: the first cross-month filter is the one action in the
  tool that may read the whole collection; it must stay responsive while it does, and must not
  repeat that read for subsequent filters in the same session.
- **A filter cleared after matches were opened from other months**: the display returns to the month
  the user was on before filtering, not the month of the last document they opened.
- **Tab pressed while the command bar is open, the help pane is open, or the editor has focus**: the
  collection selection does not move; the keystroke belongs to whatever has focus.
- **`/help` submitted while a filter is active**: the filter survives the pane opening and closing.
- **The version cannot be determined** (running from a source checkout without package metadata):
  the corner shows a fallback rather than an empty space or a crash.
- **A terminal too narrow for three panes plus the top bar**: the layout degrades without truncating
  the collection names into ambiguity, and the highlighted collection remains identifiable.
- **A month directory containing a file whose frontmatter cannot be read**: it is counted as a
  warning for that month and does not prevent the rest of the month from listing.

## Requirements *(mandatory)*

### Functional Requirements

**Top bar and collection navigation**

- **FR-001**: The topmost line MUST show the product name, a divider, and the names of all three
  collections in the order Tasks, Notes, Meetings.
- **FR-002**: Exactly one collection MUST be visibly highlighted at all times on the list screen.
- **FR-003**: Tab MUST move the highlight one collection to the right and shift+Tab one to the left,
  wrapping at both ends.
- **FR-004**: Moving the collection highlight MUST immediately switch the content area to that
  collection, with no confirmation keystroke.
- **FR-005**: On switching to a collection, the keyboard focus MUST be placed on the middle pane
  with its top row highlighted.
- **FR-006**: The vertical collection menu MUST be removed from the left pane, and the width it
  occupied MUST be returned to the list and preview panes.
- **FR-007**: Tab and shift+Tab MUST NOT change the collection while the command bar, the help pane,
  or the editor holds focus.
- **FR-008**: The existing pane-movement keys (left/right and `h`/`l`) MUST move focus between the
  left and middle panes, and the existing up/down keys (`j`/`k` and arrows) MUST move the highlight
  within the focused pane.

**Month-scoped notes and meetings**

- **FR-009**: For Notes and Meetings, the left pane MUST list months as month-and-year entries, with
  exactly one highlighted.
- **FR-010**: Selecting a Notes or Meetings collection MUST default the left pane to the current
  month and year.
- **FR-011**: The middle pane MUST list only the documents belonging to the highlighted month.
- **FR-012**: With no filter active, filling the middle pane MUST read only the documents of the
  highlighted month; no document outside that month may be read. An active filter is the only
  exception (FR-032).
- **FR-013**: Moving the left-pane highlight to another month MUST refill the middle pane from that
  month and update the preview to that month's top document.
- **FR-014**: The month list MUST include every month for which the collection holds documents, plus
  the current month even when it holds none, and MUST be ordered most-recent-first.
- **FR-015**: Creating a document MUST move the display to that document's month and highlight the
  new document.
- **FR-016**: Warning counts shown for a collection MUST reflect only the displayed month.

**Task categories**

- **FR-017**: For Tasks, the left pane MUST show exactly two entries, To-Do and Done, with one
  highlighted.
- **FR-018**: Selecting Tasks MUST default the left pane to To-Do.
- **FR-019**: The middle pane MUST list open tasks when To-Do is highlighted and completed tasks
  when Done is highlighted.
- **FR-020**: Toggling a task's state MUST move it between the two categories on the next draw.
- **FR-021**: The right pane MUST remain blank for the Tasks collection.

**Editing hotkeys**

- **FR-022**: Pressing `e` with a document highlighted in the middle pane MUST open the editor on
  that document.
- **FR-023**: The editor opened from the list MUST behave identically to the editor opened from the
  preview, including its save and exit keys and its handling of unsaved changes.
- **FR-024**: Exiting the editor opened from the list MUST return to the list with that document
  highlighted and its row reflecting any change made.
- **FR-025**: Pressing `e` when the highlighted row is a task, or when there is no highlighted row,
  MUST do nothing.
- **FR-026**: Creating a note, a meeting, or the daily note MUST open the editor on the new document
  directly, with no read-only view shown first.

**Command bar**

- **FR-027**: Opening the command bar MUST display a leading `/` with the cursor after it.
- **FR-028**: The leading `/` MUST NOT be deletable by backspace, delete, or any editing key, and
  MUST NOT be treated as part of the typed command.
- **FR-029**: `filter` MUST be an explicit command verb taking a search term, with `f` as an alias.
- **FR-030**: `filter` with no term MUST clear the active filter.
- **FR-031**: A first word that is not a recognised command MUST produce an error naming the unknown
  command, and MUST NOT be interpreted as a filter term.
- **FR-032**: In Notes and Meetings, an active filter MUST search the entire collection across every
  month, reading months beyond the displayed one as needed, and MUST list all matches newest-first
  regardless of month. In Tasks, it MUST narrow within the highlighted category.
- **FR-033**: While a cross-month filter is active, the left pane MUST show that the month scope is
  suspended rather than continuing to claim a single month is being displayed.
- **FR-034**: Clearing or cancelling the filter MUST restore the month that was displayed before the
  filter was applied, and MUST return reading to that single month.
- **FR-035**: A filter MUST NOT read a month more than once per session; months already read for a
  previous filter or visit MUST be reused.
- **FR-036**: A filter that reads beyond the displayed month MUST keep the interface responsive
  while it does so, and MUST NOT block the user's next keystroke on a whole-collection read.
- **FR-037**: All command verbs that work today MUST continue to work unchanged, including the
  create verbs, their `verb.type` form, and the collection-switching verbs.

**Help and version**

- **FR-038**: `help` MUST be a command verb that opens a pane over the lower part of the screen.
- **FR-039**: The help pane MUST list every command the bar accepts, each with a one-line
  description, including aliases.
- **FR-040**: The help pane MUST be dismissable and MUST leave the underlying screen state
  unchanged, including highlighted row, displayed month or category, and active filter.
- **FR-041**: The help pane MUST leave part of the underlying screen visible rather than replacing
  it.
- **FR-042**: The running version MUST be displayed in the bottom-right corner of the bottom bar,
  and MUST match the version the command line reports.
- **FR-043**: The displayed version MUST be the version stamped into the built package. Code
  running from a source checkout rather than a built package MUST report `0.0.0`, so a development
  build can never be mistaken for a release.

**Preserved behaviour**

- **FR-044**: The bottom bar MUST continue to host the command and filter bar and the existing
  status and help text.
- **FR-045**: Document rows and task rows MUST keep their current content and ordering within the
  displayed scope.
- **FR-046**: The preview pane MUST keep its current rendering for the highlighted note or meeting.

### Key Entities

- **Collection selection**: which of the three collections is highlighted in the top bar; the single
  piece of state that determines what all three panes show.
- **Month scope**: for Notes and Meetings, the month and year currently displayed; determines both
  what is listed and what is read from disk.
- **Task category**: for Tasks, whether To-Do or Done is displayed; a view over the one task file
  rather than a scope on what is read.
- **Command**: a verb the bar accepts, with its aliases, its argument shape, and the one-line
  description the help pane shows.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Switching between any two collections takes exactly one keystroke per step, down from
  three today.
- **SC-002**: Opening a collection in a workspace holding two years of documents reads no more
  documents than the current month contains, and start-up time does not grow as older months
  accumulate. Browsing month to month never reads a month twice.
- **SC-003**: A user who has just opened a collection can act on the top item — toggle, open, or
  edit it — without any focus-moving keystroke.
- **SC-004**: A user who has never read the documentation can list every available command within
  ten seconds of first opening the tool.
- **SC-005**: Creating a document and typing its first word takes one keystroke fewer than today,
  and editing a document from the list takes two keystrokes fewer.
- **SC-006**: No word typed as the first token of a command can be silently reinterpreted as a
  search term; unrecognised input always produces a named error.
- **SC-007**: Every screen of the tool shows the running version without the user taking any action.
- **SC-008**: Which task category is being viewed is identifiable from the screen alone, with no
  reliance on remembered mode state.
- **SC-009**: A user searching for a document they created in any past month finds it from the
  filter without navigating to that month first.

## Assumptions

- **Collection order and startup**: the top bar reads Tasks, Notes, Meetings, matching the issue's
  mockups, and the tool opens on Tasks — the leftmost entry — so the bar has a predictable home
  position. This changes today's behaviour, where the tool opens on Meetings.
- **Filter reaches across months by decision**: month scoping governs browsing, not searching. A
  user who filters is looking for something they cannot see, so scoping the search to the month in
  front of them would make the feature useless. The cost — one potentially expensive read per
  session — is accepted and bounded by FR-035 and FR-036.
- **Month list bounds**: months are discovered from the collection's existing month folders rather
  than generated as an open-ended calendar, so the left pane cannot scroll into empty years. This
  keeps discovery to a folder lookup, not a document read.
- **The `a` "show all" toggle is retired**: the Done category replaces it. Keeping both would leave
  two ways to reach the same list, one of them invisible.
- **`e` is not bound in the Tasks collection**: tasks are lines in a shared file, not documents, so
  there is nothing for a document editor to open. Editing a task remains toggling it or editing the
  task file outside the tool.
- **Version display format**: the version is shown prefixed with `v` (for example `v0.0.4`) and is
  read from the same source the command line uses, so the two front-ends cannot disagree. Today that
  source is a hardcoded string that can drift from the built package's real version; this feature
  replaces it with a value stamped in at build time, reading `0.0.0` from a source checkout.
- **Help pane content is derived, not hand-written**: the pane is built from the same command
  definitions the bar parses, so a command cannot exist without appearing in help.
- **No new persisted state**: the displayed month, the task category, and the collection selection
  live only for the session. Nothing about the layout is written to the workspace.
- **The command line is unaffected**: no verb, flag, exit code, or `--json` schema changes.
  Assistants driving endpaper through the command line see no difference from this feature.
- **Preview remains reachable**: pressing Enter on a document still opens the full-screen read view;
  `e` is an additional path to the editor, not a replacement for the preview.
- **Month-scoped loading applies only to Notes and Meetings**: tasks live in a single file that is
  read whole, so no scoping applies to them.

## Dependencies

- The workspace layout established by features 001 and 002 stores documents under a per-month folder
  for each collection, which is what makes month-scoped reading a folder lookup rather than a scan.
- The editor and its save/discard behaviour from feature 004 are reused unchanged; this feature only
  adds new entry points into it.
- The task file format and toggling behaviour from feature 003 are reused unchanged; this feature
  only changes how the two states are presented.
