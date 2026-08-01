# Feature Specification: Document Links

**Feature Branch**: `008-document-links`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "Issue 27"

**Source**: GitHub issue #27 "[Feature]: Document links as a reusable primitive", which asks for a
general-purpose way for any record in a workspace to point at any other: a link syntax that is an
ordinary markdown link, an id scheme that survives file moves, self-repair of stale paths, backlinks
computed by scanning rather than stored, command-line and in-editor authoring, and a preview-pane
surface for following links.

---

## Overview

Nothing in a workspace can point at anything else. A meeting that continues last week's meeting, a
note that gathers the research behind a decision, a followup that exists because of a specific
conversation — these are relationships a person holds in their head and the workspace does not
record. An assistant reading the workspace inherits the same gap: it can find documents by search,
but not by relation.

This feature builds the relationship as a reusable primitive rather than as a field on one record
type. A link is written once, resolved the same way everywhere, repaired the same way everywhere,
and consumed by whatever feature needs an edge between two records.

Three properties define it:

1. **The id is the identity; the path is the route.** The `#id` fragment is what the system resolves
   against and it never changes. The path exists so the link is clickable in a plain markdown viewer,
   on a code-hosting site, or in whatever editor someone opens the folder with — and so an assistant
   following a link has a file it can simply read.
2. **Nobody counts `../` by hand.** Paths are computed by the system from two real file locations. A
   link written by hand with no path at all is valid input and gains its path on the next save.
3. **Nothing is stored.** Inbound links are computed by scanning at the moment they are asked for.
   There is no index, no cache, and no back-reference written into any file.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ids name their collection in full (Priority: P1)

Every id in every link inherits whatever the id scheme is, so the scheme has to be settled before any
link is written. Today ids use a single-letter prefix (`m_`, `n_`, `t_`). A person or an assistant
reading `m_20260728_a1b2c3d4` has to be told what `m` stands for, and a workspace that ever grows a
second collection beginning with the same letter has no way to arbitrate between them.

Ids become `meeting_20260728_a1b2c3d4`, `note_20260728_a1b2c3d4`, `task_a1b2`. The prefix is derivable
from the collection name itself, so a new collection needs no registry of hand-assigned abbreviations
and no decision about who gets `m_`.

**Why this priority**: This is a prerequisite, not a feature. Every link written by every later story
carries an id, and changing the id scheme afterwards means rewriting ids that already exist in real
workspaces — a migration. endpaper is pre-release; doing it now costs four string literals and a pass
over the documentation, and doing it later costs a migration path.

**Independent Test**: Create a meeting, a note, and a task in a fresh workspace and confirm each id
carries its collection's full name as prefix. Confirm a workspace created before the change still
lists, reads, and resolves every one of its existing records.

**Acceptance Scenarios**:

1. **Given** a fresh workspace, **When** a meeting is created, **Then** its frontmatter `id` begins
   with `meeting_`.
2. **Given** a fresh workspace, **When** a note and a daily note are created, **Then** both ids begin
   with `note_`.
3. **Given** a fresh workspace, **When** a task is added, **Then** its id begins with `task_`.
4. **Given** a workspace holding records created under the old single-letter scheme, **When** it is
   listed, read, and searched, **Then** every existing record resolves by its existing id verbatim and
   no file is rewritten.
5. **Given** the generated `AGENTS.md` in a workspace, **When** it is read, **Then** it states the
   current prefixes and no longer states the old ones.

---

### User Story 2 - A link resolves, and repairs itself (Priority: P2)

A person writes `See [Q3 planning](#meeting_20260728_a1b2c3d4) for context.` in a note, by hand, in
whatever editor they have open. They do not count directory levels, because they should not have to —
a workspace that claims to be hand-editable cannot have a link syntax that is hostile to hands. The
link resolves immediately. The next time the file is saved, the system fills in the correct relative
path, and the link becomes clickable everywhere.

Later the target document is moved to a different month directory. Every link to it still resolves,
because the id never changed. The paths are now stale, and the next save of each linking file repairs
them.

**Why this priority**: This is the primitive. Every other story is either a consumer of it or a
surface on top of it.

**Independent Test**: Write a fragment-only link by hand, confirm it resolves. Save the file and
confirm a correct relative path appeared. Move the target, save again, confirm the path was corrected
and the link still resolves.

**Acceptance Scenarios**:

1. **Given** a note containing `[label](#meeting_20260728_a1b2c3d4)` with no path at all, **When** the
   link is resolved, **Then** it resolves to that meeting.
2. **Given** the same note, **When** it is next saved, **Then** the link carries a correct relative
   path to the meeting file and the link text is unchanged.
3. **Given** a note containing a link with a correct path and no `#id` fragment, **When** the link is
   resolved, **Then** it resolves to the file at that path; **and When** the note is next saved,
   **Then** the link gains that record's id as its fragment.
4. **Given** a note containing a link with a correct id and a wrong path, **When** the link is
   resolved, **Then** it resolves by id; **and When** the note is next saved, **Then** the path is
   corrected.
5. **Given** a note containing a link whose id resolves to nothing, **When** the note is saved,
   **Then** the link is left exactly as written, a warning naming the file and line is produced, and
   the save succeeds.
6. **Given** a note containing one stale link and one dead link, **When** the note is saved, **Then**
   the stale link is repaired and the dead link is untouched.
7. **Given** a file is saved, **When** the save completes, **Then** no file other than the saved file
   has been modified.
8. **Given** a link written inside a fenced code block or an inline code span, **When** the file is
   saved, **Then** it is not rewritten — it is content, not a link.

---

### User Story 3 - Ask what points at a record (Priority: P3)

An assistant is asked why a followup exists. It has the task's id and needs the meeting it came from.
Or the reverse: it has a meeting and needs everything that refers back to it — the followups, the
notes that cite it, the next meeting in the series.

`endpaper links <id>` answers both directions. Nothing is stored to make this work: the answer is
computed by scanning the workspace, the same way search already works, at the moment it is asked for.

**Why this priority**: Traversal is the reason the primitive exists. A link that can be written but
not followed backwards records the relationship without making it useful.

**Independent Test**: Create a meeting, create a task and a note that each link to it, then ask what
points at the meeting and confirm both are listed with the file, line, and link text.

**Acceptance Scenarios**:

1. **Given** a meeting linked from one task and one note, **When** inbound links for its id are
   requested, **Then** both the task and the note are listed.
2. **Given** a note containing three links, **When** outbound links for its id are requested, **Then**
   all three targets are listed, including any that do not resolve.
3. **Given** any record, **When** links are requested with no direction specified, **Then** both
   inbound and outbound links are returned.
4. **Given** a record no other record points at, **When** inbound links are requested, **Then** an
   empty result is returned and the command exits 0.
5. **Given** a workspace, **When** inbound links are computed, **Then** no file is written and nothing
   persists between calls.
6. **Given** a record whose id appears as plain prose text in another file but not inside a link,
   **When** inbound links are requested, **Then** that occurrence is not reported as a link.
7. **Given** a record, **When** inbound links are requested, **Then** the record's own frontmatter id
   is not reported as a link to itself.

---

### User Story 4 - Audit and repair from the command line (Priority: P4)

The whole reason the path is carried and repaired is that an assistant follows links by reading files.
It should never be left holding a route that goes nowhere, and it needs a way to fix one when it finds
one.

`endpaper links check` reports what is broken, in two classes that need different responses: a
**stale** link whose id resolves but whose path is wrong is mechanically fixable; a **dead** link whose
id resolves to nothing needs a decision — relink, remove, or recreate the target — that no tool should
make on someone's behalf. `endpaper links heal` fixes every stale link and touches no dead one.

**Why this priority**: Save-time repair covers files endpaper writes. A workspace edited by hand, by
another editor, or by an assistant needs a deliberate pass, and that pass has to be safe enough to run
without reading the diff first.

**Independent Test**: Move a document, run `check` and confirm the now-stale links are reported as
stale. Delete a document, confirm links to it are reported as dead. Run `heal --dry-run`, confirm it
reports exactly the stale set and writes nothing, then run `heal` and confirm only stale links changed.

**Acceptance Scenarios**:

1. **Given** a workspace with stale and dead links, **When** `check` runs, **Then** each is reported in
   its own class with the source file, line, link text, and target id.
2. **Given** a dead link, **When** `check` reports it, **Then** the unresolvable id is included, so a
   reader has everything needed to choose a fix.
3. **Given** a workspace with any stale or dead link, **When** `check` runs, **Then** it exits
   non-zero; **Given** a workspace with neither, **Then** it exits 0.
4. **Given** stale links, **When** `heal --dry-run` runs, **Then** it reports exactly the set that
   `heal` would change and writes no file.
5. **Given** stale and dead links in the same file, **When** `heal` runs, **Then** every stale link is
   rewritten and every dead link is left byte-identical.
6. **Given** `heal` is run with no path arguments, **When** it completes, **Then** the whole workspace
   was considered; **Given** it is run with paths, **Then** only those files were considered.
7. **Given** `heal` completes with dead links remaining, **When** it exits, **Then** the exit code is
   non-zero and the dead links are named.
8. **Given** a workspace where nothing is stale, **When** `heal` runs, **Then** no file is written and
   it exits 0.
9. **Given** any of these commands, **When** run with `--json`, **Then** the output is a stable schema
   and no prompt, pager, or confirmation is presented.

---

### User Story 5 - A task remembers where it came from (Priority: P5)

A followup exists because of a conversation. The task line records that with a `links:` field in the
metadata comment it already carries — comma-separated ids, shaped exactly like `tags:`.

```
- [ ] call Terry about the renewal <!-- id:task_a1b2 type:followup links:meeting_20260728_a1b2c3d4 created:2026-07-30 -->
```

Ids only, no paths: a task line is already one line of metadata, and the id prefix says which
collection to look in without a lookup.

**Why this priority**: This is the first consumer of the primitive and the reason it was built as a
primitive rather than a bespoke field. It is also what unblocks inline task capture (#21).

**Independent Test**: Write a task line with a `links:` field by hand, confirm it parses and the link
is reported in both directions. Confirm a workspace of existing task lines with no `links:` field
parses byte-for-byte as it does today.

**Acceptance Scenarios**:

1. **Given** a task line carrying `links:` with one id, **When** `tasks.md` is parsed, **Then** the
   task reports that link.
2. **Given** a task line carrying `links:` with several comma-separated ids, **When** parsed, **Then**
   all are reported, in the order written.
3. **Given** an existing `tasks.md` with no `links:` field on any line, **When** it is parsed and
   rewritten, **Then** every line is byte-identical to before — no migration and no rewrite.
4. **Given** a task with links, **When** its line is rewritten by any operation, **Then** the metadata
   fields appear in the order `id`, `type`, `tags`, `links`, `created`, and empty fields are omitted.
5. **Given** a task whose `links:` field names an id that resolves to nothing, **When** parsed,
   **Then** the id is preserved verbatim, a warning is produced, and the task still parses.
6. **Given** a task line with a malformed `links:` value, **When** parsed, **Then** the failure is
   reported and every other task in the file still parses — the same hand-edit tolerance the parser
   already holds to.
7. **Given** a task linking a meeting, **When** inbound links for that meeting are requested, **Then**
   the task is listed.
8. **Given** any task line, **When** `tasks.md` is rendered in a plain markdown viewer, **Then** it is
   valid CommonMark and renders as a checklist.

---

### User Story 6 - Insert a link without leaving the editor (Priority: P6)

Mid-sentence, in a note, a person needs to point at last week's meeting. They type `/link q3 planning`
on its own line and press enter. The line is replaced with the markdown link to the matching record,
with the path already correct. They keep typing.

**Why this priority**: Authoring is where a link syntax succeeds or fails. Correct paths that a person
has to construct by hand are correct paths nobody writes.

**Independent Test**: In the editor, type `/link` with search terms matching exactly one record, submit
it, and confirm the line became a correct markdown link. Repeat with terms matching nothing and with
terms matching several records, and confirm the typed line survives in both cases.

**Acceptance Scenarios**:

1. **Given** the editor, **When** `/link <terms>` on its own line is submitted and exactly one record
   matches by title or id, **Then** the line is replaced with a markdown link to that record whose
   path is correct from the current file's location.
2. **Given** search terms matching no record, **When** submitted, **Then** the line is left exactly as
   typed and the status bar names the failure.
3. **Given** search terms matching several records, **When** submitted, **Then** the line is left
   exactly as typed and the status bar reports the ambiguity and names candidates.
4. **Given** an unsaved buffer, **When** `/link` is submitted, **Then** the document is saved before
   the command acts.
5. **Given** any outcome, **When** the command completes, **Then** the user is still in the document —
   no dialog, no picker screen, no state change.
6. **Given** a line that begins with `/link` but has other text before it on the line, **When**
   submitted, **Then** it is ordinary document text and is not treated as a command.

---

### User Story 7 - See and follow links in the preview pane (Priority: P7)

Reading a meeting, a person sees what it points at and what points back at it, and presses one key to
open either.

Outbound links come from the document already on screen, so they cost nothing and are shown on open.
Inbound links require reading the workspace, so they are fetched when the section is actually opened —
not on every document open.

**Why this priority**: The TUI surface makes links visible to the person who writes them. It depends on
everything above and delivers no capability the command line does not already provide.

**Independent Test**: Open a document with outbound links and confirm they are listed on open. Open the
inbound section and confirm the records pointing at it are listed. Press the open key on each and
confirm the correct record opens.

**Acceptance Scenarios**:

1. **Given** a document with outbound links, **When** it is opened in preview, **Then** its outbound
   links are listed without any workspace scan.
2. **Given** a document, **When** the inbound section is opened, **Then** inbound links are computed
   and listed, below the outbound list.
3. **Given** a document nothing points at, **When** the inbound section is opened, **Then** it reports
   that plainly rather than appearing empty and broken.
4. **Given** a selected link, **When** the open key is pressed, **Then** that record opens in whichever
   collection it lives in.
5. **Given** a selected link whose target does not resolve, **When** the open key is pressed, **Then**
   the status bar says so and the view does not change.
6. **Given** the preview state, **When** the Links section is available, **Then** every binding that
   acts on it is visible in the footer.

---

### User Story 8 - The workspace has to actually be on disk (Priority: P8)

This scan, the task scan, and search all read the markdown files directly — there is no index to
consult instead. A workspace living in a cloud folder whose files are on-demand placeholders pays a
network round trip per file, and an AI assistant reading the folder has no way to trigger a download at
all.

The README says so, in the section where someone is actively choosing where to put their workspace.

**Why this priority**: Documentation, and the only story here that changes no behaviour. It matters
because it is the same property that makes endpaper work at all: files are the only state, so the files
have to be there.

**Independent Test**: Read the README's workspace-creation section and confirm it names the four common
providers and the exact setting each one needs.

**Acceptance Scenarios**:

1. **Given** the README's "Create a workspace" section, **When** it is read, **Then** it warns that a
   workspace in a cloud-synced folder must be pinned to local disk.
2. **Given** that warning, **When** it is read, **Then** it names the specific action for OneDrive
   ("Always keep on this device"), Dropbox ("Make available offline"), Google Drive ("Available
   offline"), and iCloud Drive (keep downloaded; do not let Optimize Storage evict it).
3. **Given** that warning, **When** it is read, **Then** it states why: there is no index, so the files
   have to be present — for endpaper and for the assistant reading the folder.

---

### Edge Cases

**Format and parsing**

- A link inside a fenced code block or an inline code span is content, not a link: never rewritten,
  never reported as stale or dead, never counted as an inbound link.
- A link with a URL scheme (`http:`, `https:`, `mailto:`) is external and is never touched.
- An image (`![alt](path)`) is not a record link; it is left alone.
- The same id linked twice in one file produces two independently repaired links and two inbound
  entries.
- A link from a record to itself resolves and is reported like any other.
- A path containing characters that require percent-encoding round-trips: what is written stays
  resolvable and stays clickable.
- Link paths use forward slashes regardless of the platform that wrote them, so a link authored on
  Windows resolves on macOS and Linux.

**Resolution**

- Two records carrying the same id (a copy-pasted file) is a workspace defect: resolution is
  deterministic rather than arbitrary, and the ambiguity is reported.
- An id that resolves to nothing is dead, not an error: the link stays, a warning names the file and
  line, and nothing else in the file is affected.
- A path pointing outside the workspace root resolves by id if it has one, and is otherwise left alone
  rather than rewritten to point somewhere inside.
- A link with neither a resolvable id nor a resolvable path is dead.

**Repair**

- A generated relative path stays well under the Windows 260-character limit, including the deepest
  `../` prefix the layout can produce.
- Repairing a link never alters the link text, the surrounding sentence, or the line ending style of
  the file.
- A file with no links is saved unchanged.
- A repair pass does not invent modifications: a file with nothing stale in it is not written and its
  `updated` timestamp does not move.

**Scale and environment**

- A workspace of several thousand documents answers an inbound-link question fast enough to be used
  interactively.
- An empty workspace, an empty `tasks.md`, and a document with no body all behave correctly rather than
  raising.
- A workspace on a cloud folder with on-demand placeholders is slow rather than wrong; the README says
  how to fix it.

---

## Requirements *(mandatory)*

### Functional Requirements

**Link format**

- **FR-001**: A link between records MUST be an ordinary CommonMark inline link of the form
  `[text](path#id)`, where the `#id` fragment names the target record.
- **FR-002**: The `#id` fragment MUST be authoritative and context-free — the value the system resolves
  against, independent of where either file sits.
- **FR-003**: The path MUST be treated as derived and perishable, present so the link is clickable in a
  plain markdown viewer and followable by an assistant that only reads files.
- **FR-004**: A fragment-only link (`[text](#id)`) MUST be valid input and MUST resolve.
- **FR-005**: A link with a path and no fragment MUST resolve by path.
- **FR-006**: Resolution order MUST be id first, path second.
- **FR-007**: A link MUST NOT be required to be authored with a path. Users and assistants MUST never
  need to count directory levels.
- **FR-008**: Every file the system writes MUST remain valid CommonMark, and every link in it MUST be
  clickable in a plain markdown viewer.
- **FR-009**: Text inside fenced code blocks and inline code spans MUST NOT be treated as a link for
  any purpose — resolution, repair, reporting, or inbound counting.
- **FR-010**: Links with a URL scheme and image links MUST be left untouched.

**Identifiers**

- **FR-011**: Newly generated record ids MUST carry their collection's full name as prefix:
  `meeting_`, `note_`, `task_`.
- **FR-012**: The prefix MUST be derivable from the collection name, so a new collection requires no
  registry of hand-assigned abbreviations and no arbitration between collections sharing a first
  letter.
- **FR-013**: Ids already present in a workspace MUST continue to resolve verbatim, and MUST NOT be
  rewritten by this change.
- **FR-014**: No id MUST be parsed by splitting on a separator or by fixed offset; an id is an opaque
  token matched whole.

**Task links**

- **FR-015**: `links` MUST be a recognized key in the task metadata comment, holding comma-separated
  record ids.
- **FR-016**: A task line without a `links` field MUST parse exactly as it does today, with no
  migration and no rewrite of existing files.
- **FR-017**: When a task line is written, metadata fields MUST appear in the order `id`, `type`,
  `tags`, `links`, `created`, with empty fields omitted.
- **FR-018**: The `links` field MUST hold ids only and MUST NOT hold paths.
- **FR-019**: An id in a `links` field that resolves to nothing MUST be preserved verbatim and reported
  as dead, never dropped.
- **FR-020**: A malformed `links` value MUST be reported and MUST NOT prevent other tasks in the file
  from parsing, and MUST NOT lose or truncate any line.

**Frontmatter**

- **FR-021**: No new frontmatter key MUST be introduced. Document frontmatter stays at exactly the six
  keys it carries today, and document links live in the body next to the prose that explains them.

**Self-healing**

- **FR-022**: When the system writes a file, every link in that file whose path is stale or absent, and
  whose id resolves, MUST be rewritten to the correct relative path.
- **FR-023**: A link with a resolvable path and no fragment MUST gain its target's id fragment when the
  file is next written.
- **FR-024**: Repair MUST be scoped to the file being written. A scan of the workspace MUST NOT trigger
  repair of files nobody touched.
- **FR-025**: A link whose id does not resolve MUST NOT be rewritten, MUST NOT be removed, and MUST NOT
  make the write fail. It MUST produce a warning naming the source file and line.
- **FR-026**: Repair MUST preserve link text, surrounding prose, and the file's line-ending style.

**Backlinks**

- **FR-027**: Inbound links MUST be computed at the moment they are requested, by scanning, and MUST
  NOT be persisted between calls.
- **FR-028**: No file MUST record that something points at it, and no index, cache, or derived link
  file MUST be written anywhere in the workspace.
- **FR-029**: The system MUST expose stateless operations to parse links out of a document or a task
  line, resolve an id to the record it names, and collect the links pointing at a given id.
- **FR-030**: Computing inbound links MUST NOT require parsing the frontmatter of every file in the
  workspace; a cheap candidate filter over file contents MUST narrow the set that gets parsed.
- **FR-031**: Inbound links MUST be computed only when asked for, never on every document open.

**Commands**

- **FR-032**: `endpaper links <id>` MUST report the links associated with a record, with
  `--direction out|in|both` selecting direction and `both` the default.
- **FR-033**: `endpaper links check [<path>...]` MUST report broken links, classified as **stale** (id
  resolves, path wrong or absent) or **dead** (id resolves to nothing).
- **FR-034**: A dead link MUST be reported with its source file, line, link text, and the unresolvable
  id.
- **FR-035**: `endpaper links heal [<path>...]` MUST rewrite every stale link and MUST touch no dead
  link.
- **FR-036**: With no path arguments, `check` and `heal` MUST operate on the whole workspace; with
  paths, only on those files.
- **FR-037**: `--dry-run` MUST report exactly the set `heal` would change and MUST write nothing.
- **FR-038**: These commands MUST be non-interactive: no prompt, no confirmation, no pager.
- **FR-039**: `--json` MUST be available and MUST emit a stable schema with the keys `file`, `line`,
  `text`, `target_id`, `old_path`, `new_path`, `status`.
- **FR-040**: Exit codes MUST follow the project contract: 0 when nothing is unresolved, 1 when
  unresolved links remain, 2 for usage errors, 3 for workspace errors. Data MUST go to stdout and
  errors to stderr.
- **FR-041**: Every capability above MUST be reachable from both interfaces except where inherently
  interactive or inherently non-interactive.

**In-editor authoring**

- **FR-042**: `/link <search terms>` submitted as an entire line in the editor MUST resolve the terms
  against record titles and ids and replace the line with a markdown link to the match.
- **FR-043**: The inserted link's path MUST be correct from the editing file's own location.
- **FR-044**: With no match or more than one match, the line MUST be left exactly as typed and the
  outcome MUST be reported in the status bar.
- **FR-045**: The document MUST be saved before the command acts, and the user MUST remain in the
  document in every outcome.
- **FR-046**: A line that is not entirely the command MUST be ordinary document text.

**Preview surface**

- **FR-047**: The preview pane MUST show a Links section with outbound links above inbound links.
- **FR-048**: Outbound links MUST be shown when the document opens, computed from the document itself
  with no workspace scan.
- **FR-049**: Inbound links MUST be computed when the section is opened, not when the document is
  opened.
- **FR-050**: Selecting a link and pressing the open key MUST open that record in whichever collection
  it lives in; an unresolvable target MUST report in the status bar and leave the view unchanged.
- **FR-051**: Every binding that acts on the Links section MUST be visible in the footer.

**Documentation**

- **FR-052**: The generated `AGENTS.md` MUST document the link syntax, the task `links` field, the
  current id prefixes, and the `endpaper links` commands, and MUST stay under roughly 60 lines.
- **FR-053**: The README's workspace-creation section MUST warn that a workspace in a cloud-synced
  folder must be pinned to local disk, naming the specific setting for OneDrive, Dropbox, Google Drive,
  and iCloud Drive, and stating why.
- **FR-054**: The changelog MUST record the id prefix change, the task line format change, the new
  commands, and the new JSON schema, with their version.

### Key Entities

- **Link**: A directed reference from a source record to a target record. Carries the link text, the
  target id, and a derived path. Lives in a document body as a markdown link, or in a task line's
  `links` field as a bare id.
- **Record id**: The stable, opaque identity of a meeting, note, or task. Prefixed with its
  collection's full name. Never changes, never re-derived, never parsed for structure.
- **Link status**: What is currently true of a link — resolved, **stale** (id resolves, path wrong or
  missing, mechanically fixable), or **dead** (id resolves to nothing, needs a human decision).
- **Link report**: What `check` and `heal` emit for one link — source file, line, link text, target id,
  old path, new path, status.
- **Collection prefix**: The id prefix derived from a collection's name, the property that makes ids
  self-describing and lets new collections exist without arbitration.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A link written entirely by hand as `[label](#<id>)`, with no path, resolves on the first
  read and carries a correct relative path after the file is next saved.
- **SC-002**: A link written by hand with a correct path and no fragment resolves, and gains the
  target's id fragment on the next save.
- **SC-003**: Moving a document to a different month directory leaves 100% of `#id` links to it
  resolving; a repair pass rewrites the now-stale paths, and a dry run first reports exactly the same
  set without writing a byte.
- **SC-004**: A link to a deleted document is reported as dead, is never rewritten or removed by a
  repair pass, and affects no other link in the same file.
- **SC-005**: A generated relative path is correct from every depth the layout produces — a document
  under a collection's `YYYY/MM`, a daily note under `notes/daily/YYYY/MM`, the root `tasks.md`, and a
  document sitting outside the dated layout all round-trip.
- **SC-006**: Asking what points at one record returns in under half a second on a workspace of 6,000
  documents, and requires no index, cache, or file to have been built beforehand.
- **SC-007**: Upgrading an existing workspace rewrites zero files: every existing id still resolves and
  every existing task line parses byte-identically.
- **SC-008**: A workspace-wide repair pass writes only the files that contained a stale link; a
  workspace with nothing stale sees zero writes.
- **SC-009**: A person can insert a correct link into a document in one line of typing, without leaving
  the editor and without knowing where either file sits on disk.
- **SC-010**: `tasks.md` and every note remain valid CommonMark, and every link in them is clickable in
  a plain markdown viewer.
- **SC-011**: An assistant that has read only the generated `AGENTS.md` can write a valid link, ask
  what points at a record, and repair stale paths, without further instruction.
- **SC-012**: Every command in this feature completes without a prompt, a confirmation, or a pager, and
  its exit code distinguishes "nothing unresolved" from "unresolved links remain".

---

## Assumptions

- **Existing ids are not migrated.** endpaper is pre-release, so new ids adopt the full-name prefix
  while ids already written to disk resolve verbatim and are never rewritten. Resolution matches ids
  whole, so an old-scheme id and a new-scheme id coexist without ambiguity.
- **`AGENTS.md` is regenerated only by workspace creation.** An existing workspace keeps the
  `AGENTS.md` it has until it is regenerated; this feature does not add a command to refresh it.
- **Ambiguity is a failure, not a prompt.** `/link` with more than one match reports and inserts
  nothing, because taking the user out of the document to choose contradicts the editor's design. The
  status bar names candidates so the user can retype with better terms.
- **The Links section is the only new preview surface.** Its bindings extend the existing preview
  footer rather than introducing a new screen or state; list → preview → edit remains the state model.
- **Inbound-link scanning uses the search read path.** It reads the same files search already reads,
  with no external binary and no network access.
- **Warnings ride the existing warning channel.** Dead links and malformed `links` fields surface the
  same way existing parse warnings do, rather than defining a second reporting mechanism.
- **`links check` exits non-zero for either class.** A stale link is unresolved at the moment of the
  check even though it is fixable; the exit code says "something needs attention" and the
  classification says what kind.
- **Duplicate ids are a defect, not a supported state.** Resolution is deterministic and the duplicate
  is reported; the feature does not add tooling to reconcile them.
- **The in-editor command plumbing already exists.** `/link` registers alongside the existing editor
  command surface and inherits its save-first, status-bar-report, never-leave-the-document behaviour.

---

## Dependencies and Relationships

- **#21 (inline task capture)** depends on this. It uses a link to record the document a task came
  from, rather than defining its own provenance field. Story 5 is what unblocks it.
- **#22** is reduced to the graph view by this feature; linking, backlinks, and the authoring syntax
  are settled here.
- **#19** shares the editor slash-command plumbing that Story 6 extends.
- **#26 (task bodies)** and **#17 (layout refresh)** define the preview surfaces where links appear;
  Story 7 depends on the preview pane as it now exists.
- Ships against the current constitution: markdown files remain the only state (III), all logic lands
  in core (I), both interfaces stay peers (II), hand-edited input is tolerated and never lost (IV),
  and the Links section's behaviour and bindings are decided here rather than at the keyboard (V).

---

## Out of Scope

- A graph view (#22).
- Cross-workspace links.
- Transclusion — a link points at a record; it does not pull the record's content in.
- Reciprocal back-reference blocks written into target documents. Rejected on measurement and on
  failure modes; if it is ever needed it is a cache layered on top of this work, not a replacement for
  it, and the trigger for revisiting is cloud-storage hydration latency on a real workspace, not scan
  cost.
- A stored backlink index of any kind.
- Wikilink syntax. It is not CommonMark, and an assistant following a wikilink must know endpaper's
  id-to-file mapping before it can open anything, while a relative path is just a file it can read.
- Repairing every file on scan. A deliberate workspace-wide pass is what `links heal` is for.
- Renaming or moving files to match links. endpaper never moves a user's files.
