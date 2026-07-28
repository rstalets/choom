# Feature Specification: Meeting Notes (with project scaffolding)

**Feature Branch**: `001-meeting-notes`

**Created**: 2026-07-28

**Status**: Draft

**Input**: User description: "Read requirements.md in its entirety. Write a spec for feature 3.1 (meeting notes), including creating any scaffolding required to start the project. All shipped code should live in src/. The project will be distributed on PyPI and installable using `uv tool install endpaper`. The TUI should open when `endpaper` is typed into console without CLI arguments."

**Source**: `REQUIREMENTS.md` §3.1, plus the subset of §3.4, §4.1, §4.2, §4.3, §4.6, and §4.7 required to make §3.1 shippable.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install endpaper and get a workspace (Priority: P1)

A corporate employee on a managed laptop, with no admin rights, wants to start keeping notes.
They run a single install command, run a single init command inside a folder they already
have, and then type `endpaper` and see the tool running. Nothing asks them to choose a
storage location, create an account, or connect to a network.

**Why this priority**: Nothing else in this feature is reachable without it. This story alone
delivers a working install, a workspace on disk, and a launchable interface — the minimum
that can be published and tried by someone else.

**Independent Test**: On a clean machine with no admin rights, and with no network access after
the install step, install the tool, run init in an empty directory, confirm the expected files
and folders exist, and launch the interface with a bare command.

**Acceptance Scenarios**:

1. **Given** a machine with no administrator rights, **When** the user installs endpaper using the
   documented single command, **Then** the `endpaper` command is available on their PATH and
   `endpaper --version` prints a version and exits 0.
2. **Given** an empty directory, **When** the user runs `endpaper init`, **Then** the workspace
   configuration file, an `AGENTS.md` file, a `meetings/` directory, a `notes/daily/` directory,
   and an empty `tasks.md` exist, and the command exits 0.
3. **Given** a directory that is already an endpaper workspace, **When** the user runs
   `endpaper init` again, **Then** the command exits with the workspace error code, prints a
   message naming the existing workspace, and changes no file on disk.
4. **Given** an initialized workspace, **When** the user types `endpaper` with no arguments,
   **Then** the terminal interface opens on a single screen showing the meetings list.
5. **Given** a directory that is not inside any workspace, **When** the user runs `endpaper` with
   no arguments, **Then** they are told no workspace was found and how to create one, and the
   command exits with the workspace error code rather than opening an empty interface.

---

### User Story 2 - Capture a meeting note in the seconds before the call (Priority: P2)

The user is about to join a standup. They issue one short command containing only what they
would have said out loud — the kind of meeting and what it is about — and a correctly named,
correctly dated file exists. They never choose a folder or a filename.

**Why this priority**: This is the feature's reason to exist. It depends only on Story 1.

**Independent Test**: From a fresh workspace, create meetings from both the terminal interface
and the command line, and inspect the resulting files on disk for correct location, name,
frontmatter, and title.

**Acceptance Scenarios**:

1. **Given** an initialized workspace, **When** the user runs `/meeting.standup Q3 planning #platform`
   in the interface, **Then** exactly one file is created under `meetings/`, named with today's
   date, the type, and a slug of the description, containing frontmatter with `type: standup`,
   `tags: [platform]`, `title: Q3 planning`, today's `created`, and a matching `updated`.
2. **Given** the same workspace, **When** the user runs
   `endpaper meeting new "Q3 planning" --type standup --tag platform`, **Then** the resulting file is
   identical to the file from scenario 1 in every respect except the generated identifier and the
   timestamps, and the command prints the file's path to standard output and exits 0.
3. **Given** a meeting already created today from the description "Q3 planning", **When** the user
   creates another meeting with the same description and type on the same day, **Then** two
   distinct files exist, the first is unmodified, and the second's name is disambiguated with a
   numeric suffix.
4. **Given** any create command, **When** the user omits the type, **Then** an untyped meeting is
   created whose filename contains no type segment and whose frontmatter records an empty type.
5. **Given** the command line, **When** the user includes a `#tag` inside a quoted description,
   **Then** the tag is recorded in frontmatter and removed from the title.
6. **Given** the command line, **When** the user passes `--tag` more than once, **Then** every tag
   appears in frontmatter in the order given, with duplicates removed.
7. **Given** the interface, **When** the user includes multiple `#tag` tokens anywhere in the
   description, **Then** all are recorded as tags and none appear in the title.

---

### User Story 3 - Find a meeting from last month (Priority: P3)

The user remembers a vendor conversation but not when it happened. They open the list, type a
few characters, and the list narrows as they type until the meeting they want is on screen.

**Why this priority**: Capture has value on its own; retrieval multiplies it. It depends on
Story 2 having produced files to find.

**Independent Test**: Create a known set of meetings across several dates, types, and tags, then
verify list ordering, live filtering in the interface, and each filter option on the command line.

**Acceptance Scenarios**:

1. **Given** a workspace with several meetings, **When** the user opens the meetings list in the
   interface, **Then** meetings appear sorted by date descending, each row showing date, type,
   title, and tags.
2. **Given** the meetings list, **When** the user presses the filter key and types text, **Then**
   the visible rows narrow with each keystroke to those whose title, type, or tags contain the
   typed text, case-insensitively, with no perceptible delay.
3. **Given** the meetings list, **When** the user presses up/down or `j`/`k`, **Then** the selection
   moves one row and stops at the ends of the list without wrapping or erroring.
4. **Given** a workspace with meetings, **When** the user runs `endpaper meeting list --json`,
   **Then** standard output is a single array of objects, each having exactly the keys `id`, `path`,
   `title`, `type`, `tags`, `created`, and `updated`, and nothing else is written to standard output.
5. **Given** a workspace with meetings, **When** the user runs `endpaper meeting list` with `--tag`,
   `--type`, or `--since`, **Then** only matching meetings are returned, and combining filters
   returns only meetings matching all of them.
6. **Given** a workspace with no meetings, **When** the user lists meetings, **Then** the interface
   shows an empty-state message and the command line prints an empty array (with `--json`) or
   nothing (without), exiting 0 in both cases.

---

### User Story 4 - An AI assistant works in the workspace unassisted (Priority: P4)

An assistant is pointed at the workspace with no briefing. It reads the guidance file at the
root, learns the layout and the commands, and lists and creates meetings without a human
translating anything for it.

**Why this priority**: This is a stated hard requirement of the product, but it is verifiable
only once Stories 1–3 exist to be driven.

**Independent Test**: With no human in the loop, run every command in this feature with output
redirected to a file rather than a terminal, and confirm nothing blocks, nothing decorates, and
every result parses.

**Acceptance Scenarios**:

1. **Given** a freshly initialized workspace, **When** an assistant reads `AGENTS.md`, **Then** it
   finds the folder layout, the frontmatter schema, and the meeting commands, in a file of roughly
   60 lines or fewer, that explicitly documents `--tag` as the command-line form for tags.
2. **Given** any command in this feature, **When** it is run with output redirected to a file,
   **Then** no prompt appears, no editor opens, no pager runs, no colour or cursor control
   characters are written, and the command terminates without waiting for input.
3. **Given** any command in this feature, **When** it fails, **Then** the explanation is written to
   standard error, nothing is written to standard output, and the exit code is 1 for a missing
   target, 2 for a usage error, and 3 for a workspace problem.
4. **Given** a successful read command with `--json`, **When** its standard output is parsed as
   JSON, **Then** parsing succeeds with no preamble, banner, or trailing text.

---

### Edge Cases

- A description that produces an empty slug (only punctuation, emoji, or whitespace): the file is
  still created with a stable non-empty fallback name, and the title is preserved verbatim.
- A description longer than the slug limit: the filename is truncated at the limit without leaving
  a trailing hyphen, while the title in frontmatter stays complete.
- A description or tag containing characters illegal in filenames on Windows: the slug excludes
  them; the title and tags retain them.
- A type containing a path separator, a dot, or a leading dash: rejected as a usage error, so no
  file is ever written outside `meetings/`.
- An unquoted `#tag` on the command line: the shell strips it before endpaper sees it, and the tag
  is silently absent. Help text and `AGENTS.md` must document `--tag` prominently enough that a
  user is unlikely to reach this state.
- More than nine meetings created from the same description, type, and day: suffixes continue past
  `-9` without collision.
- A workspace path containing spaces, non-ASCII characters, or approaching the Windows path length
  limit: creation and listing succeed.
- A file in `meetings/` with absent, malformed, or non-conforming frontmatter: it is skipped with a
  logged warning and every other meeting still lists. Listing never raises and never rewrites the
  offending file.
- A file in `meetings/` that is not markdown: ignored.
- `--since` given a value that is not a date: usage error, exit code 2, nothing listed.
- The terminal window is very small, or is resized while the interface is open: the layout adapts
  without crashing.
- The workspace directory is read-only, or the disk is full during create: the command fails with a
  clear message and leaves no partial file behind.

## Requirements *(mandatory)*

### Functional Requirements

**Distribution and entry point**

- **FR-001**: The tool MUST be publishable under the name `endpaper` and installable with
  `uv tool install endpaper` and with `pipx install endpaper`, neither requiring administrator rights.
- **FR-002**: Installation MUST provide a single console command named `endpaper`.
- **FR-003**: Running `endpaper` with no arguments MUST open the terminal interface.
- **FR-004**: Running `endpaper` with any subcommand MUST run that subcommand non-interactively and
  MUST NOT open the terminal interface.
- **FR-005**: `endpaper --version` and `endpaper --help` MUST work from any directory, including
  outside a workspace, and exit 0.
- **FR-006**: All shipped code MUST reside under `src/`, and the packaged distribution MUST contain
  only that code and its declared data files.
- **FR-007**: No operation in this feature may require network access.

**Workspace**

- **FR-008**: `endpaper init` MUST create, in the current directory, a workspace configuration file,
  `AGENTS.md`, `meetings/`, `notes/daily/`, and an empty `tasks.md`.
- **FR-009**: `endpaper init` in a directory that is already a workspace MUST exit with the workspace
  error code, explain why, and modify nothing.
- **FR-010**: Commands MUST locate the workspace by searching the current directory and then its
  ancestors, using the nearest workspace found.
- **FR-011**: When no workspace is found, every command in this feature MUST exit with the workspace
  error code and state how to create one.
- **FR-012**: `AGENTS.md` MUST be generated at init, MUST be roughly 60 lines or fewer, and MUST
  state the folder layout, the frontmatter schema, the meeting commands, and that `--tag` is the
  command-line form for tags.

**Creating a meeting**

- **FR-013**: Users MUST be able to create a meeting from the terminal interface with
  `/meeting.<type> <description>` and from the command line with
  `endpaper meeting new <description> --type <type>`, both producing the same result.
- **FR-014**: The type MUST be optional and free-form. Omitting it MUST create an untyped meeting.
- **FR-015**: A created meeting MUST be a markdown file at `meetings/YYYY-MM-DD-<type>-<slug>.md`,
  omitting the type segment when untyped.
- **FR-016**: Slugs MUST be derived from the description, lowercase, containing only alphanumeric
  characters and hyphens, and truncated to 40 characters.
- **FR-017**: When the target filename already exists, the new file MUST be created with a numeric
  suffix (`-2`, `-3`, …), and the existing file MUST NOT be read, modified, or overwritten.
- **FR-018**: Every created meeting MUST carry frontmatter with exactly the fields `id`, `type`,
  `title`, `tags`, `created`, and `updated`, and no others.
- **FR-019**: The `id` MUST be unique within the workspace and stable for the life of the file.
- **FR-020**: `title` MUST be the description with tag tokens removed and surrounding whitespace
  collapsed, preserving the user's original casing and characters.
- **FR-021**: In the terminal interface, `#tag` tokens MUST be accepted inline anywhere in the
  description, repeatably.
- **FR-022**: On the command line, `--tag` MUST be accepted repeatably, and `#tag` tokens appearing
  inside a quoted description MUST also be parsed as tags and stripped from the title.
- **FR-023**: Tags MUST be stored in the order supplied, with duplicates removed.
- **FR-024**: On the command line, creating a meeting MUST print the created file's path to standard
  output and exit 0.
- **FR-025**: Creating a meeting MUST NOT modify any other file in the workspace.

**Listing meetings**

- **FR-026**: Users MUST be able to list meetings from the terminal interface with `/meetings` and
  from the command line with `endpaper meeting list`.
- **FR-027**: Meetings MUST be listed sorted by date descending, showing date, type, title, and tags.
- **FR-028**: The command line MUST support `--json`, `--tag`, `--type`, and `--since` filters, which
  MUST combine conjunctively.
- **FR-029**: `--json` MUST emit an array of objects with exactly the keys `id`, `path`, `title`,
  `type`, `tags`, `created`, and `updated`.
- **FR-030**: The terminal interface MUST provide a filter input that narrows the visible list as the
  user types, matching against title, type, and tags, case-insensitively.
- **FR-031**: Filtering MUST operate on data already held in memory and MUST NOT read from disk per
  keystroke.
- **FR-032**: The terminal interface MUST support moving the selection with up/down and with `j`/`k`.
- **FR-033**: Listing MUST tolerate malformed files: a meeting file with missing or unparseable
  frontmatter MUST be skipped with a warning, MUST NOT be rewritten, and MUST NOT prevent other
  meetings from listing.

**Interface behaviour**

- **FR-034**: The terminal interface MUST present a single screen consisting of a filterable list
  and a preview pane.
- **FR-035**: Every key binding active in the current state MUST be visible in a footer.
- **FR-036**: The interface MUST NOT bind the terminal's reserved interrupt or quit keys to any
  other action.
- **FR-037**: Pressing enter on a meeting row MUST open that meeting in a full-screen rendered
  markdown preview, from which one keystroke returns to the list. Creating a meeting from the
  interface MUST leave the user in that same preview of the new file. Entering an editing state
  from the preview is out of scope for this feature and is specified in REQUIREMENTS.md §3.5; until
  it is delivered, the preview MUST NOT offer or imply an edit action in its footer.

**Command-line discipline**

- **FR-038**: No command in this feature may open an editor, prompt for input, wait for a keypress,
  or page its output.
- **FR-039**: No command may write colour or cursor control characters when its output is not a
  terminal.
- **FR-040**: Data MUST be written to standard output and diagnostics to standard error, never
  interleaved.
- **FR-041**: Exit codes MUST be 0 for success, 1 for a target that was not found, 2 for a usage
  error, and 3 for a workspace error.

**Platform**

- **FR-042**: Windows, macOS, and Linux MUST be supported, with Windows treated as a primary target.
- **FR-043**: Workspace paths containing spaces and non-ASCII characters MUST work on all supported
  platforms.
- **FR-044**: Generated paths MUST stay well within the Windows maximum path length, assuming a long
  synced-folder root.

### Key Entities

- **Workspace**: A directory containing a configuration marker, the fixed folder structure, and the
  guidance file. It is the boundary for all listing and creation in this feature.
- **Meeting**: A single markdown file in `meetings/`. Identified by a stable id, described by a type,
  title, tags, and creation and update timestamps, and located by a date-first filename so that
  lexical order matches chronological order. Its body is free-form markdown owned by the user.
- **Tag**: A short free-form label attached to a meeting. Supplied inline in the interface, and by an
  explicit option on the command line.
- **Meeting list record**: The in-memory, machine-readable projection of a meeting used by both the
  interface's list and the command line's JSON output, with a fixed and documented set of fields.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with no administrator rights can go from nothing installed to a created meeting
  note in under 3 minutes, following only the README.
- **SC-002**: Creating a meeting from a single typed command takes under 20 seconds from first
  keystroke to the file existing, including the user's typing time.
- **SC-003**: A user never has to choose a filename or a folder to create a meeting note — measured
  as zero prompts and zero path arguments in the documented create flow.
- **SC-004**: The interface opens and displays a workspace of 1,000 meetings within 2 seconds.
- **SC-005**: Filtering a 1,000-meeting list updates the visible rows within 100 milliseconds of a
  keystroke.
- **SC-006**: 100% of the acceptance scenarios in this specification are covered by automated tests
  that run without a terminal attached.
- **SC-007**: An AI assistant given only the workspace and its guidance file can list and create
  meetings correctly on its first attempt, encountering no interactive prompts.
- **SC-008**: Every documented command produces valid, parseable output when redirected to a file,
  with a 0% rate of control characters in redirected output.
- **SC-009**: A workspace containing hand-edited and malformed meeting files still lists every
  well-formed meeting, with a 0% rate of data loss or unrequested file modification.
- **SC-010**: All acceptance scenarios pass on Windows, macOS, and Linux.

## Assumptions

- **Scaffolding is in scope.** "Any scaffolding required to start the project" is read as: the
  packaged project layout under `src/`, publishing-ready packaging metadata, the console entry
  point, the test harness, and the linting, formatting, and type-checking configuration the
  constitution requires. It does not include continuous-integration provider configuration or a
  release pipeline, neither of which is user-facing behaviour.
- **A minimal single workspace is in scope.** Feature 3.1 cannot be exercised without somewhere to
  put a file, so the single-workspace half of REQUIREMENTS.md §3.4 (`endpaper init` with no name) is
  included. Named workspaces, the shared root file, workspace switching, and the cross-workspace
  scope toggle are deferred to their own feature.
- **`notes/daily/` and `tasks.md` are created but unused.** Init produces the full documented layout
  so that later features add behaviour rather than migrating existing workspaces.
- **"Byte-identical" is interpreted as "identical except for generated values."** REQUIREMENTS.md
  §3.1 acceptance criterion 2 asks that the command-line and interface create paths produce a
  byte-identical file. Taken literally this is unachievable, because the identifier and the
  timestamps differ between two invocations. The requirement is specified here as identical in every
  field except `id`, `created`, and `updated` — the testable form of the same intent: one create
  path, two front doors.
- **Timestamps are local time without a timezone offset**, matching the frontmatter example in
  REQUIREMENTS.md §4.6.
- **Tag matching on the command line is exact and case-insensitive**; substring matching applies to
  the interface's live filter, not to `--tag`.
- **`--since` accepts an ISO date** and is inclusive of that date.
- **Python 3.11 or newer** is the supported runtime, per REQUIREMENTS.md §4.1.

## Dependencies

- None on other endpaper features. This is the first feature; it establishes the project.
- The user's environment must provide `uv` or `pipx` to install, and a terminal capable of running a
  full-screen application in order to use the interface. The command-line half requires neither.

## Out of Scope

Deferred to their own features, and explicitly not delivered here:

- General notes and daily notes (REQUIREMENTS.md §3.2)
- Tasks and `tasks.md` parsing (§3.3)
- Named workspaces, the shared root file, workspace switching, cross-workspace scope (§3.4)
- Editing: the edit state, line numbers, save and discard keys, and the unsaved-changes prompt (§3.5)
- `endpaper find`, `read`, `write`, and `append` (§4.2, §4.4)
- Everything listed in REQUIREMENTS.md §5
