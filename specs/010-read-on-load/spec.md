# Feature Specification: Read From Disk on View Load

**Feature Branch**: `010-read-on-load`

**Created**: 2026-08-01

**Status**: Draft

**Input**: User description: "Issue 51"

**Source**: GitHub issue #51 "[Feature]: Read from disk on view load; retire the session cache", milestone
v0.0.3. The issue is the output of a design review that followed a bug surfaced by #21: the TUI parses the
workspace once at mount and keeps it in memory for the life of the session, so a change made by anyone
other than the running app — most importantly an AI assistant working in the same workspace from another
process — is invisible until the app is restarted. Three designs were compared in that review; the one
that survived is captured here.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An assistant's changes appear when the view is opened (Priority: P1)

Someone has choom open on their Notes list. They ask their AI assistant, running in the same workspace from
a separate process, to write up a meeting and tick off the follow-up it produced. They switch to Meetings
and back, or open the document. What they see reflects what is on disk right now: the new meeting is in the
list, and the task reads done.

Today, none of that appears. The list is drawn from a snapshot taken when the app started, and navigating
between views redraws that same snapshot. Only quitting and relaunching reconciles it.

**Why this priority**: This is the whole problem. choom's premise is that a person and an assistant share
one workspace (Principle II); a view that can only see the person's own writes breaks that premise silently,
and in the direction that matters most — the person believes they are looking at the workspace, and they are
not. It is also the change that makes the rest possible: the timer and the filter hydration in US2 and US3
are only coherent once nothing is cached.

**Independent Test**: With the app parked on any list, modify the workspace from outside the process (create
a document, tick a task, edit a body, delete a file), navigate away and back, and confirm the view matches
disk. Delivers the entire correctness fix on its own; US2 and US3 are refinements of when the read happens,
not whether it happens.

**Acceptance Scenarios**:

1. **Given** the Meetings list is showing one meeting, **When** another process creates a second meeting in
   the displayed month and the user leaves the view and returns, **Then** both meetings are listed.
2. **Given** the Tasks list shows a task as open, **When** another process marks that task done and the user
   leaves the view and returns, **Then** the task renders as done and appears under the Done category.
3. **Given** a document is listed, **When** another process deletes it and the user leaves the view and
   returns, **Then** it is no longer listed and no error is shown.
4. **Given** a document is listed, **When** another process rewrites its title or body and the user opens it
   in the preview, **Then** the preview shows the current content, not the content as it was at app start.
5. **Given** the user ticks a checkbox inside a document body, **When** they return to the Tasks list,
   **Then** the task shows as done — without any explicit refresh call having been wired for that path.
6. **Given** another process writes a document that cannot be parsed, **When** the user loads the view,
   **Then** the malformed file is skipped, the rest of the list renders, and the warning count in the status
   bar reflects the current state of the workspace (Principle IV).
7. **Given** a document was created in the app moments ago, **When** the list is loaded, **Then** it appears
   exactly once — the read from disk is the only source of what is listed.

---

### User Story 2 - An open view keeps up on its own (Priority: P2)

The user leaves choom open on the Tasks list while their assistant works through a backlog in the same
workspace. Without touching the keyboard, they watch tasks flip to done as they are completed.

**Why this priority**: US1 makes the workspace knowable; this makes it observable without the user having to
guess that navigating away and back is what refreshes things. It is a genuine improvement to the shared-
workspace story but not a correctness fix, and it depends on US1 having removed the cache first.

**Independent Test**: Park the app on a list, change the workspace from another process, touch nothing, and
confirm the list catches up within a couple of seconds. Testable in isolation once US1 has landed.

**Acceptance Scenarios**:

1. **Given** the Tasks list is open and untouched, **When** another process completes a task, **Then** the
   list shows it as done within approximately two seconds without any user input.
2. **Given** a list is open and nothing in the workspace has changed, **When** the refresh interval elapses,
   **Then** the view does not visibly change — no flicker, no scroll jump, no re-render.
3. **Given** the user has a row selected partway down a list, **When** a refresh adds a document that sorts
   above it, **Then** the same record stays selected and the view does not jump to the top.
4. **Given** the user has a row selected, **When** a refresh finds that record gone from disk, **Then** the
   list renders without it and selection lands on a sensible neighbour rather than being lost.
5. **Given** the user is reading a document in the preview, **When** the refresh interval elapses, **Then**
   the preview is not re-rendered underneath them.
6. **Given** the user is mid-edit in a document, **When** the refresh interval elapses, **Then** nothing they
   have typed is disturbed and no save is triggered.

---

### User Story 3 - Filtering stays instant (Priority: P3)

The user presses `/`, types a few letters, and sees matches from across every month of the collection with
no perceptible pause — the same as today, on a workspace where every read now goes to disk.

**Why this priority**: This is the one path that reads per keystroke, so it is the one place where removing
the cache could be felt. It is a performance protection for an existing behaviour rather than new user value,
and it only becomes necessary once US1 has landed.

**Independent Test**: On a workspace of a thousand documents, open the command bar and type a filter term;
confirm the `/` keypress itself never stalls and results appear as the term is typed. Measurable independently
of US1 and US2 once the cache is gone.

**Acceptance Scenarios**:

1. **Given** a workspace with a thousand documents across many months, **When** the user presses `/`, **Then**
   the command bar opens immediately with no perceptible delay.
2. **Given** the command bar is open, **When** the user types the first letter of a filter term, **Then**
   matches from every month of the collection are shown without a visible pause.
3. **Given** the user opens the command bar and types a non-filter verb, backspaces it away, and then types a
   filter term, **Then** filtering still responds immediately — the work started when the bar opened is not
   thrown away mid-session.
4. **Given** the command bar is closed without a filter ever being typed, **Then** no filter results are
   shown and nothing about the view has changed.
5. **Given** the user filters, then clears the filter, **Then** the view returns to the month scope they were
   on before filtering, showing current on-disk content.

---

### Edge Cases

- **A file changes while the view is being read.** A scan that encounters a half-written or vanished file
  skips it and records a warning rather than failing the load (Principle IV). The next read picks it up.
- **The workspace is on a synced folder.** choom shows what is on the local filesystem at the moment it
  reads. Sync latency from OneDrive or similar is outside choom's control and is not something the refresh
  interval can compensate for.
- **The selected record disappears between refreshes.** Selection must degrade gracefully — the list renders
  and something sensible is selected, rather than the app erroring or clearing the view.
- **A refresh lands while the command bar is open.** The user is typing; a list rebuild underneath them must
  not steal focus, close the bar, or discard the term in progress.
- **A refresh lands while a confirmation dialog is open.** The dialog stays; the list behind it is not
  re-rendered in a way that changes what the dialog refers to.
- **A filter is active.** Periodic refresh is suspended while a filter is showing. A filtered view is a
  full-collection read on every tick, and it answers a point-in-time question the same way the preview does;
  it reconciles when the filter is cleared, which restores the month scope and takes a normal scoped read.
  The filter term is never cleared by a refresh.
- **Scrolling a very large month.** The periodic read happens on the same thread that draws the screen, so a
  month large enough to scan slowly could be felt as a stutter while a movement key is held. The budget in
  SC-003 is what keeps this out of reach at the sizes choom targets.
- **An empty month or an empty workspace.** The empty-state message renders on every load, and a refresh that
  finds nothing does not replace it with an error.
- **Very large workspaces.** Well beyond the hundreds-to-low-thousands the tool targets, a per-load scan will
  eventually be felt. The spec states the budget it holds to (SC-003, SC-004); exceeding it is a signal to
  revisit, not a case to design around now.

## Requirements *(mandatory)*

### Functional Requirements

**Reading from disk (US1)**

- **FR-001**: Loading any list view MUST read the records it displays from the workspace files at that moment.
- **FR-002**: Returning to a list from any other screen MUST read from disk, not from anything retained while
  the user was away.
- **FR-003**: Opening a document for reading MUST read that document from disk, so the rendered body and
  metadata reflect its current on-disk content.
- **FR-004**: Records created, edited, completed, or deleted by any process — including one that is not the
  running app — MUST be reflected on the next view load with no user action beyond navigation.
- **FR-005**: choom MUST NOT retain parsed documents, tasks, or scan warnings across a view load in order to
  avoid re-reading them. No session-lifetime store of workspace content may remain (Principle III).
- **FR-006**: Correctness MUST NOT depend on a writer remembering to notify a view. No code path may be
  required to announce that it changed the workspace in order for the change to be seen.
- **FR-007**: A file that cannot be parsed MUST be skipped with a warning on every load, and the warning
  count the user sees MUST describe the workspace as it is now, not as it was at app start (Principle IV).
- **FR-008**: A read that fails part-way MUST leave the user with a usable view — the records that could be
  read, plus a warning — never an empty list presented as though the workspace were empty.

**Keeping an open view current (US2)**

- **FR-009**: While a list view is displayed, choom MUST re-read and re-render it periodically without user
  input, at an interval of approximately two seconds.
- **FR-010**: A periodic refresh that finds no change MUST NOT alter what the user sees in any way.
- **FR-011**: A periodic refresh MUST preserve the user's selection by identity, so a record that moves
  position stays selected.
- **FR-012**: A periodic refresh MUST NOT run while a document is being read in the preview or edited, nor
  while a filter is active.
- **FR-013**: A periodic refresh MUST NOT take focus, dismiss an open command bar or dialog, clear an active
  filter term, or interrupt typing.
- **FR-014**: The refresh interval MUST NOT be user-configurable; a sensible default is the whole of it
  (Principle III).

**Filtering (US3)**

- **FR-015**: Filtering MUST continue to match across every month of the active collection, including unfiled
  documents, exactly as it does today.
- **FR-016**: The keystroke that opens the command bar MUST NOT stall while the collection is read; the read
  MUST NOT block the interface.
- **FR-017**: The first filter term typed MUST match against the whole collection, waiting for the read to
  complete if it has not yet finished, rather than matching a partial set.
- **FR-018**: The read started when the command bar opens MUST remain available for the whole time the bar is
  open, including after the user types and erases a non-filter command.
- **FR-019**: Filter results MUST reflect the workspace as of when the command bar was opened; a filter
  session does not need to observe writes that land mid-session.

### Key Entities

- **Document**: A meeting or note, read from a markdown file. Its identity, title, date, and body all come
  from the file; nothing about it is remembered between reads.
- **Task**: A checkbox record in the workspace's task file, together with its state and any documents it is
  mirrored into. Read whole on each load.
- **Scan warning**: A note that a file could not be read or parsed, produced by a read and describing that
  read only. Warnings are not accumulated across reads.
- **View scope**: What the user has chosen to look at — collection, month or unfiled, task category, filter
  term. This is user intent, is held for the session, and is unaffected by this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A change made to the workspace by another process is visible to the user after navigating away
  from and back to the affected view, in 100% of cases — including creation, deletion, body edits, and task
  completion. Verified by the reproduction in issue #51, which currently reports one meeting where there are
  two and an open task that is done on disk.
- **SC-002**: Restarting the app is never required to see a change made outside it.
- **SC-003**: Loading a list on a workspace of 1,000 documents completes fast enough to be imperceptible when
  switching views — under 200 ms — and loading the task list under 100 ms.
- **SC-004**: On a workspace of 1,000 documents, opening the command bar never delays the keypress that opens
  it, and the first filter term returns matches in under 500 ms.
- **SC-005**: A change made by another process to a view the user is looking at, untouched, becomes visible
  within 5 seconds.
- **SC-006**: A refresh of an unchanged workspace produces no visible change and no loss of selection, across
  100 consecutive refreshes.
- **SC-007**: No sequence of in-app actions leaves a list disagreeing with the files on disk. Verified against
  every path that writes to the workspace, with no path requiring a refresh notification to stay correct.
- **SC-008**: choom holds no second source of truth for workspace content (Principle III): nothing that was
  read survives a view load, and no notification mechanism exists for telling a view that the workspace
  changed. Issue #51 inventories 38 sites that make up the current one; none has a replacement afterwards.

## Assumptions

- **Workspace size**: hundreds to low thousands of files, as the constitution assumes. The measurements in
  issue #51 — 2.95 ms to read 1,000 tasks, 29.4 ms to scan a 200-document month, 144 ms for a full
  1,000-document collection scan — are the basis for the budgets above.
- **Refresh interval**: approximately two seconds. A scoped month read costs 29.4 ms at 200 documents and a
  task read 2.95 ms at 1,000 tasks, so a 2-second cadence spends under 2% of one core in the worst case and
  far less typically — the interval is set by what feels immediate, not by what the disk can afford. Not
  configurable, per Principle III.
- **Preview is read-on-open but not on a timer**: re-rendering a body someone is mid-read on is disruptive in
  a way a list re-sort is not, and a preview reconciles the next time it is opened — which, with read-on-load,
  is every time. Settled in refinement on issue #51.
- **No filesystem watcher**: the two-second window is accepted rather than closed. A watcher means background
  work, new state, and invalidation logic that can be wrong while looking authoritative — the grounds on which
  issue #27 rejected a stored backlink index. The timer introduces no new state: it performs the same read a
  view load performs, on a schedule.
- **Speculative filter reads are accepted**: every `/` starts a collection read whether a filter follows or
  not — roughly 3 seconds of background work across twenty command-bar openings on a 1,000-document
  workspace. Stated here rather than discovered later.
- **Sequencing**: US1 is the substance and lands first; US2 and US3 each depend on the cache being gone and
  can follow within the same feature without blocking it.
- **Out of scope**: instant propagation of another process's changes, any index or watcher, and any change to
  what filtering matches or how records are sorted.
