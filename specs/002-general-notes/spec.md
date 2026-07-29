# Feature Specification: General Notes

**Feature Branch**: `002-general-notes`

**Created**: 2026-07-28

**Status**: Draft

**Input**: User description: "requirements.md feature 3.2"

**Source**: `REQUIREMENTS.md` §3.2, plus the parts of §3.5 (preview only), §4.2, §4.3, §4.4, and §4.6 needed to make §3.2 shippable.

**Builds on**: Feature `001-meeting-notes`, which established the workspace, the frontmatter schema, the slug and collision rules, the tag conventions, the list-and-preview screen, and the command-line discipline. This feature adds a second kind of document to that foundation and reuses those rules rather than restating them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Keep one note per day without deciding anything (Priority: P1)

The user has a thought, a phone call, or a scratch list that is not attached to a meeting. They
issue one command with no arguments and land in today's note. Later the same day they issue the
same command again and land in the same note, with everything they already wrote still there. They
never name the file, never pick a folder, and never wonder whether they already made one today.

**Why this priority**: The daily note is the lowest-friction capture surface in the product and the
only one that needs no thought at all. It is also the case where getting it wrong is most
damaging — a second file for the same day silently splits the day's thinking in two.

**Independent Test**: From a fresh workspace, run the daily-note command twice on the same day with
content written in between, and confirm exactly one file exists, its content is unchanged by the
second invocation, and it is reachable from the notes list.

**Acceptance Scenarios**:

1. **Given** an initialized workspace with no note for today, **When** the user runs `/note` in the
   interface, **Then** exactly one file is created at `notes/daily/YYYY-MM-DD.md` using today's date,
   carrying frontmatter with `type: daily`, and the user is left viewing that note.
2. **Given** a daily note that already exists for today and contains user-written body text,
   **When** the user runs `/note` again the same day, **Then** no new file is created, the existing
   file's body and frontmatter are byte-identical to before the command, and the user is left
   viewing that note.
3. **Given** an initialized workspace with no note for today, **When** the user runs
   `endpaper note today`, **Then** the file is created as in scenario 1, its path is printed to
   standard output, and the command exits 0.
4. **Given** a daily note that already exists for today, **When** the user runs
   `endpaper note today`, **Then** the same path is printed, the file is not modified in any way,
   and the command exits 0.
5. **Given** a workspace whose `notes/daily/` directory is missing, **When** the user requests
   today's note, **Then** the directory is created and the note is written into it.
6. **Given** any daily-note invocation, **When** it completes, **Then** no other file in the
   workspace has been modified, written, or removed.

---

### User Story 2 - Write a research note, an idea, or a draft (Priority: P2)

The user is starting something that is not a meeting and not today's scratch pad — a vendor
comparison, a design idea, a draft they will come back to. They issue one command containing the
kind of thing it is and what it is about, and a correctly named, correctly dated, correctly tagged
file exists.

**Why this priority**: This is the other half of §3.2 and the half that produces the documents worth
finding later. It depends on nothing in Story 1.

**Independent Test**: From a fresh workspace, create typed notes from both the interface and the
command line and inspect the resulting files for location, name, frontmatter, title, and tags.

**Acceptance Scenarios**:

1. **Given** an initialized workspace, **When** the user runs `/note.research vendor landscape
   #procurement` in the interface, **Then** exactly one file is created under `notes/`, named with
   today's date, the type, and a slug of the description, containing frontmatter with
   `type: research`, `tags: [procurement]`, `title: vendor landscape`, today's `created`, and a
   matching `updated`.
2. **Given** the same workspace, **When** the user runs
   `endpaper note new "vendor landscape" --type research --tag procurement`, **Then** the resulting
   file is identical to the file from scenario 1 in every respect except the generated identifier
   and the timestamps, its path is printed to standard output, and the command exits 0.
3. **Given** a typed note already created today from the description "vendor landscape", **When**
   the user creates another with the same description and type on the same day, **Then** two
   distinct files exist, the first is unmodified, and the second's name is disambiguated with a
   numeric suffix.
4. **Given** the command line, **When** the user includes a `#tag` inside a quoted description,
   **Then** the tag is recorded in frontmatter and removed from the title; **and When** the user
   passes `--tag` more than once, **Then** every tag appears in frontmatter in the order given, with
   duplicates removed.
5. **Given** the interface, **When** the user runs `/note` followed by a description and no type,
   **Then** an untyped note is created under `notes/`, and today's daily note is neither created nor
   opened.
6. **Given** either front door, **When** the user supplies `daily` as the type, **Then** the command
   is rejected as a usage error naming the daily-note command to use instead, and no file is created.
7. **Given** either front door, **When** the user supplies a type containing a path separator, a
   dot, or a leading dash, **Then** the command is rejected as a usage error and no file is written
   outside `notes/`.

---

### User Story 3 - Find and read a note written weeks ago (Priority: P3)

The user remembers writing something about a vendor but not when, or which day's scratch note it
landed in. They open the notes list, type a few characters, and the list narrows until the note is
on screen. They press enter and read it rendered.

**Why this priority**: Capture has value on its own; retrieval multiplies it. It depends on Stories
1 and 2 having produced files to find.

**Independent Test**: Create a known set of daily and typed notes across several dates, types, and
tags, then verify list ordering, live filtering in the interface, preview rendering, and each filter
option on the command line.

**Acceptance Scenarios**:

1. **Given** a workspace containing both daily and typed notes, **When** the user opens the notes
   list in the interface, **Then** all of them appear together, sorted by date descending, each row
   showing date, type, title, and tags, with daily notes distinguishable by their `daily` type.
2. **Given** the notes list, **When** the user filters by typing text, **Then** the visible rows
   narrow with each keystroke to those whose title, type, or tags contain the typed text,
   case-insensitively, with no perceptible delay and no disk access per keystroke.
3. **Given** the notes list, **When** the user presses enter on a row, **Then** that note opens in a
   full-screen rendered markdown preview, and one keystroke returns to the list.
4. **Given** a workspace with notes, **When** the user runs `endpaper note list --json`, **Then**
   standard output is a single array of objects, each having exactly the keys `id`, `path`, `title`,
   `type`, `tags`, `created`, and `updated`, and nothing else is written to standard output.
5. **Given** a workspace with notes, **When** the user runs `endpaper note list` with `--tag`,
   `--type`, or `--since`, **Then** only matching notes are returned, and combining filters returns
   only notes matching all of them; **and When** the user passes `--type daily`, **Then** only daily
   notes are returned.
6. **Given** a workspace with no notes, **When** the user lists notes, **Then** the interface shows
   an empty-state message and the command line prints an empty array (with `--json`) or nothing
   (without), exiting 0 in both cases.
7. **Given** a workspace containing both meetings and notes, **When** the user lists notes, **Then**
   no meeting appears; **and When** the user lists meetings, **Then** no note appears.
8. **Given** the interface showing the meetings list, **When** the user switches to the notes list
   and back, **Then** each list shows current content and the active collection is identifiable on
   screen.

---

### User Story 4 - An AI assistant works with notes unassisted (Priority: P4)

An assistant already able to search and create meetings in the workspace discovers notes the same
way: by reading the guidance file at the root. It lists notes, reads one, and creates a new one
without a human explaining the difference between a daily note and a typed note.

**Why this priority**: The assistant-facing contract is a hard product requirement, but it is
verifiable only once Stories 1–3 exist to be driven.

**Independent Test**: With no human in the loop, run every note command with output redirected to a
file, and confirm nothing blocks, nothing decorates, every result parses, and the guidance file
describes the commands used.

**Acceptance Scenarios**:

1. **Given** a freshly initialized workspace, **When** an assistant reads `AGENTS.md`, **Then** it
   finds the note commands alongside the meeting commands, learns that `notes/daily/` holds one file
   per day and `notes/` holds typed notes, and the file remains roughly 60 lines or fewer.
2. **Given** any note command, **When** it is run with output redirected to a file, **Then** no
   prompt appears, no editor opens, no pager runs, no colour or cursor control characters are
   written, and the command terminates without waiting for input.
3. **Given** any note command, **When** it fails, **Then** the explanation is written to standard
   error, nothing is written to standard output, and the exit code is 1 for a missing target, 2 for
   a usage error, and 3 for a workspace problem.
4. **Given** a workspace upgraded from the previous feature that has never had a note, **When** an
   assistant lists notes, **Then** the command succeeds and returns an empty result rather than
   failing on the absence of note files.

---

### Edge Cases

- **A daily note exists for today but its frontmatter is missing, malformed, or has a different
  `type`.** The daily-note command still opens that file rather than creating a second one for the
  day. It does not rewrite or repair the file, and it does not fail.
- **A daily note exists for today but is completely empty (zero bytes).** Treated as existing. It is
  opened, not replaced, and no frontmatter is injected.
- **Midnight crosses while the interface is open.** The daily-note command uses the date at the
  moment it is invoked, so a note requested after midnight belongs to the new day.
- **A file in `notes/daily/` whose name is not an ISO date.** It is listed if its frontmatter parses
  and skipped with a warning if not. It is never a candidate for "today's note", which is resolved
  by filename.
- **A file in `notes/` whose frontmatter says `type: daily`.** It lists as a daily note but is never
  returned by the daily-note command, which resolves only by path. Creating such a file through
  endpaper is prevented by the reserved-type rule.
- **A description that produces an empty slug** (only punctuation, emoji, or whitespace): the file is
  still created with a stable non-empty fallback name, and the title is preserved verbatim.
- **A description longer than the slug limit**: the filename is truncated at the limit without
  leaving a trailing hyphen, while the title in frontmatter stays complete.
- **A description or tag containing characters illegal in filenames on Windows**: the slug excludes
  them; the title and tags retain them.
- **An unquoted `#tag` on the command line**: the shell strips it before endpaper sees it, and the
  tag is silently absent. `--tag` must remain the documented form in help text and `AGENTS.md`.
- **More than nine typed notes from the same description, type, and day**: suffixes continue past
  `-9` without collision.
- **`notes/` contains a file that is not markdown, or a nested directory other than `daily/`.**
  Ignored by listing.
- **A file in `notes/` with absent or unparseable frontmatter**: skipped with a logged warning; every
  other note still lists; the offending file is never rewritten.
- **`--since` given a value that is not a date**: usage error, exit code 2, nothing listed.
- **The workspace directory is read-only, or the disk is full during create**: the command fails with
  a clear message and leaves no partial file behind.
- **A workspace path containing spaces, non-ASCII characters, or approaching the Windows path length
  limit**: creation and listing succeed.

## Requirements *(mandatory)*

### Functional Requirements

**Daily notes**

- **FR-001**: Users MUST be able to open today's daily note from the terminal interface with `/note`
  taking no description, and from the command line with `endpaper note today`.
- **FR-002**: The daily note MUST be a markdown file at `notes/daily/YYYY-MM-DD.md`, where the date
  is the local date at the moment the command is invoked.
- **FR-003**: When no file exists at that path, the daily-note command MUST create it with
  frontmatter carrying `type: daily`.
- **FR-004**: When a file already exists at that path, the daily-note command MUST open it and MUST
  NOT create a second file, alter its body, alter its frontmatter, or update its `updated`
  timestamp.
- **FR-005**: The daily note for a given day MUST be resolved by path alone, so that a file with
  unparseable or unexpected frontmatter is still recognised as that day's note.
- **FR-006**: The daily-note command MUST create the `notes/daily/` directory if it is absent.
- **FR-007**: On the command line, the daily-note command MUST print the note's path to standard
  output and exit 0, whether the note was created or already existed.

**Typed and untyped notes**

- **FR-008**: Users MUST be able to create a note from the terminal interface with
  `/note.<type> <description>` and from the command line with
  `endpaper note new <description> --type <type>`, both producing the same result.
- **FR-009**: The type MUST be optional and free-form. In the interface, `/note <description>` with
  a non-empty description MUST create an untyped note and MUST NOT create or open the daily note.
- **FR-010**: A created note MUST be a markdown file at `notes/YYYY-MM-DD-<type>-<slug>.md`, omitting
  the type segment when untyped, and MUST NOT be placed in `notes/daily/`.
- **FR-011**: Slug derivation, filename collision suffixing, tag parsing (`#tag` inline in the
  interface, `--tag` repeatable on the command line, `#tag` inside a quoted command-line
  description), title derivation, and the exact frontmatter field set MUST follow the same rules
  already specified for meetings, with no note-specific variation.
- **FR-012**: `daily` MUST be a reserved type. Supplying it to the note-creation command from either
  front door MUST be rejected as a usage error that names the daily-note command instead, and MUST
  create no file.
- **FR-013**: A type containing a path separator, a dot, or a leading dash MUST be rejected as a
  usage error, so no file is ever written outside `notes/`.
- **FR-014**: On the command line, creating a note MUST print the created file's path to standard
  output and exit 0.
- **FR-015**: Creating a note MUST NOT modify any other file in the workspace.

**Listing notes**

- **FR-016**: Users MUST be able to list notes from the terminal interface with `/notes` and from the
  command line with `endpaper note list`.
- **FR-017**: Listing MUST include both typed notes from `notes/` and daily notes from
  `notes/daily/`, presented as one collection sorted by date descending, showing date, type, title,
  and tags.
- **FR-018**: Notes and meetings MUST remain separate collections: listing notes MUST return no
  meetings, and listing meetings MUST return no notes.
- **FR-019**: The command line MUST support `--json`, `--tag`, `--type`, and `--since` filters, which
  MUST combine conjunctively, and `--type daily` MUST select exactly the daily notes.
- **FR-020**: `--json` MUST emit an array of objects with exactly the keys `id`, `path`, `title`,
  `type`, `tags`, `created`, and `updated` — the same schema already emitted for meetings.
- **FR-021**: Listing MUST tolerate malformed files: a note file with missing or unparseable
  frontmatter MUST be skipped with a warning, MUST NOT be rewritten, and MUST NOT prevent other
  notes from listing.
- **FR-022**: Listing MUST succeed and return an empty result in a workspace that contains no notes,
  including one created before this feature existed.
- **FR-023**: Files under `notes/` that are not markdown, and directories under `notes/` other than
  `daily/`, MUST be ignored by listing.

**Interface behaviour**

- **FR-024**: `note` and `notes` MUST be registered command verbs in the interface's single
  filter-and-command input, so that input beginning with either resolves to a command rather than a
  filter, and the resolved mode MUST be shown to the user before they commit it.
- **FR-025**: The interface MUST show notes on the same single screen already used for meetings — a
  filterable list and a preview pane — and the active collection MUST be identifiable on screen.
- **FR-026**: Filtering the notes list MUST operate on data already held in memory and MUST NOT read
  from disk per keystroke.
- **FR-027**: The interface MUST support moving the selection with up/down and with `j`/`k`, and
  pressing enter MUST open the selected note in a full-screen rendered markdown preview from which
  one keystroke returns to the list.
- **FR-028**: Creating or opening a note from the interface MUST leave the user in the preview of
  that note. Because the editing state is not delivered by this feature, the preview MUST NOT offer
  or imply an edit action.
- **FR-029**: Every key binding active in the current state MUST be visible in the footer, and the
  terminal's reserved interrupt and quit keys MUST NOT be bound to any other action.
- **FR-030**: Switching between the meetings list and the notes list MUST show current content in
  each, reflecting any note or meeting created during the session.

**Guidance file**

- **FR-031**: `AGENTS.md` generated at init MUST describe the note commands alongside the meeting
  commands, state that `notes/daily/` holds one file per day and `notes/` holds typed notes, and
  remain roughly 60 lines or fewer.

**Command-line discipline and platform**

- **FR-032**: No note command may open an editor, prompt for input, wait for a keypress, or page its
  output; none may write colour or cursor control characters when output is not a terminal; data
  MUST go to standard output and diagnostics to standard error, never interleaved.
- **FR-033**: Exit codes MUST be 0 for success, 1 for a target that was not found, 2 for a usage
  error, and 3 for a workspace error.
- **FR-034**: Windows, macOS, and Linux MUST be supported, with workspace paths containing spaces and
  non-ASCII characters working on all three, and generated paths staying well within the Windows
  maximum path length.
- **FR-035**: No operation in this feature may require network access, and no state may be introduced
  outside the markdown files themselves.

### Key Entities

- **Note**: A markdown file representing something the user wrote that is not a meeting. Carries the
  same identity and metadata as a meeting — stable id, type, title, tags, created and updated
  timestamps — and is located by a date-first filename so lexical order matches chronological order.
  Its body is free-form markdown owned by the user.
- **Daily note**: The distinguished note for a calendar day, at a fixed path derived from that date,
  with the reserved type `daily`. Exactly zero or one exists per day per workspace. It is the only
  document in the product addressed by date rather than by description.
- **Typed note**: A note created from a description and an optional free-form type, named and tagged
  by the same rules as a meeting, intended for ideas, research, drafts, and reference material.
- **Note collection**: The in-memory, machine-readable projection of every note in the workspace,
  shared by the interface's list and the command line's JSON output, using the same fixed field set
  as the meeting collection and kept separate from it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from a cold terminal to writing in today's note with a single command and
  zero decisions — measured as zero prompts, zero path arguments, and zero type arguments in the
  documented daily-note flow.
- **SC-002**: Invoking the daily-note command any number of times in one day yields exactly one file,
  with a 0% rate of duplicate day files across repeated runs including runs from both front doors.
- **SC-003**: Re-opening an existing daily note leaves the file byte-identical, with a 0% rate of
  unrequested modification to body, frontmatter, or timestamps.
- **SC-004**: Creating a typed note from a single typed command takes under 20 seconds from first
  keystroke to the file existing, including the user's typing time.
- **SC-005**: The notes list opens and displays a workspace of 1,000 notes within 2 seconds, and
  filtering it updates the visible rows within 100 milliseconds of a keystroke.
- **SC-006**: 100% of the acceptance scenarios in this specification are covered by automated tests
  that run without a terminal attached.
- **SC-007**: An AI assistant given only the workspace and its guidance file can list, read, and
  create both daily and typed notes correctly on its first attempt, encountering no interactive
  prompts.
- **SC-008**: Every note command produces valid, parseable output when redirected to a file, with a
  0% rate of control characters in redirected output.
- **SC-009**: A workspace containing hand-edited and malformed note files still lists every
  well-formed note, with a 0% rate of data loss or unrequested file modification.
- **SC-010**: A workspace created by the previous feature, with no notes in it, works with every note
  command without any migration step.
- **SC-011**: All acceptance scenarios pass on Windows, macOS, and Linux.

## Assumptions

- **`/note <description>` creates an untyped note, not the daily note.** REQUIREMENTS.md §3.2
  specifies `/note` (daily) and `/note.<type> <description>` (typed) but leaves `/note` followed by a
  description undefined. Two readings exist: treat the description as an error, or mirror meetings —
  where omitting the dot suffix creates an untyped document. This spec takes the mirroring reading,
  because it is consistent with §3.1, predictable from the meeting behaviour the user already knows,
  and the only reading in which typed text is never discarded. Bare `/note` with no description
  remains the daily note.
- **`daily` is reserved as a type.** REQUIREMENTS.md does not say so, but a note created at
  `notes/YYYY-MM-DD-daily-<slug>.md` would list as a daily note while being neither unique per day
  nor reachable by the daily-note command. Rejecting the type is cheaper than defining that
  ambiguity away later.
- **The daily note is created with frontmatter and an empty body.** No heading, template, or
  boilerplate is inserted. Frontmatter is required because listing depends on it; anything beyond it
  is content the user did not ask for.
- **The daily note's `title` is its ISO date**, so the list has something to show and filter on and
  the frontmatter field set stays exactly the six fields fixed in §4.6.
- **Opening a note from the interface lands in preview, not in an edit buffer.** REQUIREMENTS.md
  §3.2 says the daily note is "opened", and §3.5 defines opening as preview-first with editing one
  keystroke away. The edit state is deferred to its own feature, so this feature delivers the
  preview half only — the same boundary already drawn for meetings in feature 001.
- **Notes and meetings are separate collections, not one merged stream.** §3.2 specifies `/notes`
  with "same list behaviour as `/meetings`", which implies two lists rather than one combined one. A
  unified view across both is not requested and is not delivered.
- **Timestamps are local time without a timezone offset**, and "today" is the local calendar date,
  matching §4.6 and the meeting behaviour already shipped.
- **Tag matching on the command line is exact and case-insensitive**; substring matching applies to
  the interface's live filter, not to `--tag`.
- **`--since` accepts an ISO date** and is inclusive of that date.
- **The frontmatter schema, slug rules, collision rules, exit codes, and JSON key set are inherited
  unchanged** from feature 001. This feature adds no field, no key, and no exit code.

## Dependencies

- **Feature 001 (meeting notes and project scaffolding)** must be in place: the workspace and its
  `notes/daily/` directory, workspace resolution, the frontmatter reader and writer, slug and
  collision handling, tag parsing, the list-and-preview screen with its command bar, the JSON output
  schema, and the exit-code contract are all reused as-is.
- No new third-party dependency is anticipated; this feature is a second consumer of machinery that
  already exists.
- No dependency on features 3.3 (tasks), 3.4 (named workspaces), or 3.5 (editing).

## Out of Scope

Deferred to their own features, and explicitly not delivered here:

- The editing state — the raw buffer, line numbers, save and discard keys, and the unsaved-changes
  prompt (REQUIREMENTS.md §3.5)
- Tasks and `tasks.md` parsing (§3.3)
- Named workspaces, the shared root file, workspace switching, and the cross-workspace scope toggle
  (§3.4)
- `endpaper find`, `read`, `write`, and `append` (§4.2, §4.4)
- Any merged view spanning meetings and notes
- Templates, boilerplate, or per-type scaffolding for note bodies
- Backdating a daily note, or opening a daily note for a day other than today
- Everything listed in REQUIREMENTS.md §5
