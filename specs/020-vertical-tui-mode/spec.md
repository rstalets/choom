# Feature Specification: Vertical Layout for a Half-Width Window

**Feature Branch**: `020-vertical-tui-mode`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "issue #81. You are 020"

**Source**: GitHub issue #81 "[Feature]: Vertical TUI Mode" (milestone v0.0.4), refined via a
product-owner pass. An ultrawide-monitor user snaps choom to half the screen. Three panes across is
the wrong shape for that window: the record list and the preview are each squeezed into a third of a
half-width window, while the vertical space — of which there is plenty — goes unused. The issue asks
for `/config view vertical` to rearrange the same screen so the preview sits full-width along the
bottom, and `/config view horizontal` to restore today's arrangement, with the choice remembered.

**Builds on**: `005-ui-layout-refresh` (the three-pane list screen, the collection bar, the status
bar), `004-viewing-editing` (the `list → preview → edit` state machine and the full-screen reading
view), `010-read-on-load` (the list reading from disk rather than a snapshot), `011-ui-refinements`
(the four labelled columns and their narrow-terminal degradation), `013-assistant-discovery-file`
(`/config assistant`, the existing shape of the `/config` verb), `014-inline-editor-pane` (the editor
occupying the preview pane), and `015-link-picker` (the bounded picker in the bottom-bar region).

**Constitution note**: this feature is the one that triggered constitution amendment 2.1.0 (issue
#82), which removed Principle III's "configuration beyond workspace paths is out of scope" clause and
left "a setting that could be a sensible default MUST be a sensible default" standing on its own. Per
the repo owner's ruling recorded in that amendment, **the default is horizontal**. That is settled and
is not reopened here.

---

## Overview

choom's interactive screen is one screen with four regions: a collection bar across the top, a body,
and a status bar across the bottom, with the command bar and link picker sharing the bottom strip. The
body is three panes side by side — scope, records, preview.

This feature adds a second arrangement of those same regions and a setting that chooses between them:

- **horizontal** (today, and the default): scope | records | preview, three panes across the body.
- **vertical**: the body splits into two bands. The upper band is two columns — scope | records — and
  the lower band is the preview, full width, spanning underneath both. The collection bar and the
  status bar are unchanged, still running the full width at top and bottom.

Four properties define the feature:

1. **It rearranges; it does not add.** Vertical is the same one screen, with the same states, the same
   keys, and the same footer. Nothing is added to the interface but a value for one setting. There is
   no second screen, no mode with its own bindings, and nothing that appears in one arrangement and
   not the other.
2. **The default needs no configuration.** A user who never types the command gets exactly what they
   get today. The setting exists to override a good default, not to make the tool ask a question at
   first launch.
3. **It is one person's preference, so it is stored where one person's preferences belong.** A
   workspace can be a shared OneDrive folder. The orientation is remembered in per-user local state,
   outside every workspace — see "Decision: where the orientation is remembered" below.
4. **It never leaves the user with an unusable screen.** Vertical divides the vertical space it is
   given. When there is not enough of it, choom falls back to horizontal for as long as the terminal
   is that short, and says so when asked — it does not refuse, and it does not silently forget the
   setting.

---

## Decision: where the orientation is remembered

The issue asks to remember the orientation "via the config toml". **It is not stored in the
workspace's `.choom/config.toml`. It is stored in per-user local state, outside every workspace.**
This section is the reasoning, because the issue says otherwise and the difference is constitutional.

### The rule

Constitution, Platform & Distribution Constraints:

> Per-user state (such as the current workspace) MUST live in per-user local state, never in the
> shared workspace directory, so two people sharing a synced folder cannot overwrite each other's
> selection.

That rule is untouched by amendment 2.1.0. What 2.1.0 removed was Principle III's blanket ban on
workspace configuration beyond paths — it made a workspace setting *permissible*, and said nothing
about which settings belong there. The per-user rule still decides that question, and it decides it
against the workspace for this setting.

### Why this setting falls under it

A view orientation is a property of the person and their monitor, not of the notes. It is chosen
because someone snaps a window to half of an ultrawide display. Nothing about the vault, its records,
or how they are written depends on it, and no other user of the same vault benefits from, or is
served by, one person's window habits.

choom's workspace is designed to be shared through a synced folder — REQUIREMENTS.md's own statement
of what choom is says it "works on a OneDrive-synced folder so a team can share a workspace without a
server". Put the orientation in `.choom/config.toml` and:

- One person switching to vertical relayouts everyone else's screen, at whatever moment the sync
  happens to land. That is precisely the failure the rule names.
- Two people with different monitors cannot both be right, and the file will thrash between their two
  values every time either of them uses the command.
- A file both machines write on a preference change is a file that acquires OneDrive conflict copies
  (`config.toml (Ryan's conflicted copy)`), in the one directory choom depends on to identify a
  workspace at all.

### Why the existing `[assistant]` setting is not a counter-example

`.choom/config.toml` does hold `[assistant] name`, and that is a legitimate workspace setting rather
than an exception being stretched. It answers "which assistant is set up to work on this workspace",
it drives an artifact that lives in the workspace's own guidance files, and a second person opening
the same vault is served by the same answer. It describes the workspace's working arrangement. The
view orientation describes one person's terminal and affects nothing anyone else can see.

### What this costs, honestly

choom has no per-user state store today — the workspace's config file is its only persistence, and
`discovery.py`'s writes into the user's own profile directory are pointer files for an assistant, not
choom's own state. This feature introduces the first one. Two things keep that proportionate:

- It is not a second source of truth for anything. Principle III's rule concerns indexes, databases,
  and caches of the vault's content. A file holding one display preference holds no copy of any
  record, can be deleted at any time with no loss, and its absence is simply the default.
- It is the thing the constitution already anticipated — "such as the current workspace" names a
  per-user store choom is expected to grow. Building it here, for one setting, with one resolver
  function, is smaller than retrofitting it later around a setting that shipped in the wrong place.

### Consequences

The orientation is therefore **one preference per user, not per workspace**, and it applies to every
workspace that user opens. That matches the reason it exists: their monitor and their window habits do
not change when they switch vaults. It also keeps the store to a single value rather than a map keyed
by workspace path, which is the simpler thing (Principle III).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Make choom fit a half-width window (Priority: P1)

An ultrawide-monitor user keeps choom snapped to the left half of the screen. Three panes across leave
the record list too narrow to read titles in and the preview too narrow to read prose in. They type
`/config view vertical` and press enter. The screen rearranges immediately: the collection bar stays
across the top, the scope list and record list sit side by side in the upper half, the preview spans
the full width beneath them, and the status bar still runs across the bottom. The record they were
looking at is still highlighted and still previewed.

**Why this priority**: This is the whole problem the issue reports. With this alone the feature
delivers its value.

**Independent Test**: Open choom in a window roughly half an ultrawide screen, highlight a record, run
`/config view vertical`, and confirm the layout matches the arrangement above with the same record
still highlighted and previewed.

**Acceptance Scenarios**:

1. **Given** choom in its default layout with a record highlighted and previewed, **When** the user
   runs `/config view vertical`, **Then** the collection bar spans the top, the scope list and record
   list occupy the upper band side by side, the preview occupies the lower band across the full width,
   and the status bar spans the bottom.
2. **Given** the switch has just happened, **Then** the same collection is active, the same scope
   (month, `Unfiled`, or task category) is selected, the same record is highlighted, and the preview
   shows that same record.
3. **Given** vertical is in effect, **When** the user moves the highlight with `↑`/`↓`/`j`/`k`,
   **Then** the preview in the lower band updates to the newly highlighted record exactly as it does
   in horizontal.
4. **Given** vertical is in effect, **When** the user presses `h` and `l`, **Then** focus moves between
   the scope list and the record list as it does today, because those two panes are still left and
   right of each other.
5. **Given** vertical is in effect in a half-width window, **Then** the record list is wide enough to
   show the labelled columns that the same window drops in horizontal, and the preview renders
   markdown across the full window width.

---

### User Story 2 - The choice is remembered, and it is mine (Priority: P1)

The same user quits choom and reopens it the next morning; it opens vertical. They open a second
choom against a different workspace; that one opens vertical too, because it is their preference, not
the vault's. Their colleague, who shares one of those vaults through OneDrive, opens choom on a laptop
and gets horizontal — nothing about the shared folder changed when the first user switched.

**Why this priority**: A preference that has to be re-typed every launch is not a preference. The
cross-user half of this story is the constitutional requirement in "Decision" above, and getting it
wrong is not something a later release can quietly correct on users' behalf.

**Independent Test**: Set vertical, quit, relaunch, and confirm the layout. Then confirm nothing inside
the workspace directory changed, and that a second user account opening the same workspace gets
horizontal.

**Acceptance Scenarios**:

1. **Given** the user has run `/config view vertical`, **When** they quit choom and launch it again in
   the same workspace, **Then** it opens vertical with no command typed.
2. **Given** the user has run `/config view vertical` in one workspace, **When** they launch choom in a
   different workspace, **Then** it opens vertical there too.
3. **Given** the user has run `/config view vertical`, **When** the workspace directory is inspected,
   **Then** no file inside it has changed — `.choom/config.toml` included.
4. **Given** two users sharing a workspace through a synced folder, **When** one of them switches to
   vertical, **Then** the other's next launch is unaffected and stays at whatever that user had.
5. **Given** vertical is remembered, **When** the user runs `/config view horizontal`, **Then** the
   layout returns to three panes across immediately and the next launch opens horizontal.
6. **Given** the user has never run the command, **When** they launch choom, **Then** it opens
   horizontal, with nothing to configure and no question asked.

---

### User Story 3 - Everything still works the way it did (Priority: P1)

The user, now in vertical, works normally. `enter` opens a record full-screen exactly as before and
`esc` comes back to the vertical layout. `e` opens the editor in the lower band, in the preview's
place, with the list still visible above it; saving returns them to the same row. `b` shows backlinks.
`/` opens the command bar. The footer says the same things it always said, and no key does anything
different.

**Why this priority**: A layout setting that quietly changes behaviour is worse than no layout setting.
This is the story that makes the feature safe to ship, and it is the constitution's Principle V
requirement stated as a journey.

**Independent Test**: Run the same scripted sequence of interactions in both orientations and confirm
that every outcome except pane geometry is identical, including the footer text at every step.

**Acceptance Scenarios**:

1. **Given** vertical is in effect, **When** the user presses `enter` on a highlighted document,
   **Then** the full-screen reading view takes over the whole window as it does today, and **When**
   they press `esc`, **Then** they return to the vertical layout with the same record highlighted.
2. **Given** vertical is in effect, **When** the user presses `e` on a highlighted record, **Then** the
   editor appears in the lower band in place of the preview, the scope list and record list stay
   visible above it, and the footer swaps to the editor's bindings exactly as it does today.
3. **Given** an inline edit in vertical is saved or discarded, **Then** the preview returns to the
   lower band and the same record is still highlighted in the list.
4. **Given** vertical is in effect, **When** the user presses `e` from inside the full-screen reading
   view, **Then** a full-screen editor opens as it does today, and leaving it returns to the vertical
   layout.
5. **Given** either orientation, **When** the user reads the footer in the list state, the preview
   state, the editor state, and with the link picker open, **Then** the text is identical to the other
   orientation's in every one of those states.
6. **Given** either orientation, **Then** the set of active key bindings is identical, and no binding
   exists in one orientation that does not exist in the other.
7. **Given** vertical is in effect, **When** the user presses `b` on a record with backlinks, **Then**
   the backlinks list appears at the bottom of the lower band and both it and some of the preview
   remain visible.

---

### User Story 4 - A short terminal is still a working terminal (Priority: P2)

A user who prefers vertical opens choom in a small terminal — the standard 80x24, and later something
shorter still. At 80x24 vertical works: the list shows a useful number of rows and the preview shows a
useful number of lines. When they shrink the window until neither band can be useful, choom shows the
horizontal layout instead rather than two unusable slivers, and goes back to vertical the moment the
window is tall enough again. Their setting is never changed by any of this.

**Why this priority**: Narrow- and short-terminal regressions are a recurring failure mode in this
repo, and a feature that halves the available height is the one most likely to cause another. Second
only because it protects the P1 stories rather than adding value of its own.

**Independent Test**: Run choom in vertical at 80x24 and confirm both bands are usable; shrink the
height stepwise and confirm the fallback engages, that it reverses on growth, and that the stored
preference is unchanged throughout.

**Acceptance Scenarios**:

1. **Given** vertical is in effect at 80 columns by 24 rows, **Then** the record list shows its column
   header plus multiple record rows, the preview shows multiple lines of content, and neither band is
   reduced to a single row.
2. **Given** vertical is in effect, **When** the terminal is made too short for both bands to meet
   their minimums, **Then** the screen shows the horizontal layout, with no error dialog and no loss
   of the highlighted record.
3. **Given** the fallback is in effect, **When** the terminal is made tall enough again, **Then** the
   vertical layout returns without the user typing anything.
4. **Given** the fallback is in effect, **When** the user runs `/config view` with no value, **Then**
   the report says the setting is vertical and that horizontal is in effect because the terminal is
   too short.
5. **Given** a terminal too short for vertical, **When** the user runs `/config view vertical`, **Then**
   the setting is saved, the report says it is saved and that it will take effect when the terminal is
   taller, and the layout stays horizontal.
6. **Given** the fallback engaged and later reversed, **When** the user quits and relaunches in a tall
   terminal, **Then** choom opens vertical — the fallback never rewrote the setting.
7. **Given** a very narrow terminal, **Then** the record list's labelled columns drop, the collection
   bar compacts, and the workspace path elides exactly as they do in horizontal — width degradation is
   unchanged and is not what triggers the fallback.

---

### User Story 5 - The command tells you when you get it wrong (Priority: P2)

A user guesses `/config view sideways`. The status bar tells them `sideways` is not a value this
setting takes and names the two that it does. The layout does not change and nothing is written. They
also find the command without guessing: the help pane lists it beside `/config assistant`.

**Why this priority**: Principle V requires error messages to name what went wrong and what to do
instead, and requires the interface's affordances to be visible rather than discovered. Cheap to build,
and the alternative is a silent no-op.

**Independent Test**: Enter each malformed form of the command and confirm the message names the
problem and the accepted values, that the layout is unchanged, and that the help pane lists the
command.

**Acceptance Scenarios**:

1. **Given** any orientation, **When** the user runs `/config view sideways`, **Then** the status bar
   reports that the value is not accepted and names `horizontal` and `vertical`, the layout does not
   change, and nothing is written.
2. **Given** any orientation, **When** the user runs `/config view` with no value, **Then** the status
   bar reports the current setting and the accepted values.
3. **Given** any orientation, **When** the user runs `/config layout vertical`, **Then** the status bar
   reports that `layout` is not a known setting and names the settings that are.
4. **Given** any orientation, **When** the user opens the help pane, **Then** it lists the `/config`
   verb in a form that covers both `assistant` and `view`, including `view`'s accepted values.
5. **Given** the per-user preference cannot be written — an unwritable directory, a full disk —
   **When** the user runs `/config view vertical`, **Then** the layout still changes for this session,
   the status bar says the preference could not be saved and why, and choom keeps running.

---

### Edge Cases

- **A hand-edited or corrupt preferences file.** Unreadable, malformed, missing the key, or holding a
  value that is not one of the two: all read as horizontal and choom opens normally. A preferences
  file never stops choom from starting (Principle IV's spirit; the same treatment `get_assistant`
  already gives a broken workspace config).
- **The preferences file does not exist yet.** The overwhelmingly common case. It is the default, not
  an error, and choom does not create the file until something is set.
- **Two choom sessions open at once.** Each reads the preference at startup. Switching in one does not
  reach into the other; the other picks it up at its next launch. Nothing watches the file.
- **The terminal is resized across the fallback threshold repeatedly.** The layout follows the
  threshold each time. The decision is a pure function of the terminal's height, so it is
  deterministic and cannot end up out of step with the actual size.
- **The command bar or the link picker is open when the terminal is resized.** These occupy the bottom
  strip and shrink the bands, but they never change the orientation: the fallback is decided from the
  terminal's total height, not from what happens to be visible.
- **An inline editor is open.** The command bar cannot be opened while it is (014 FR-008), so the
  orientation cannot be changed mid-edit. Nor may a resize flip it: the orientation is fixed for as
  long as an editor pane is open.
- **A record with a very long backlinks list in vertical.** The backlinks section is bounded so that
  the preview above it stays visible; it does not swallow the lower band.
- **The user is in the middle of a filter.** The filter term, the matched rows, and the highlighted row
  survive the switch; the scope pane still reads as suspended.
- **A workspace with no records.** The empty-state message appears in the record list as it does
  today; the preview band is empty. Nothing else differs.
- **The setting is switched twice in a row.** Idempotent. Setting the value already in effect
  rearranges nothing, reports the same confirmation, and writes the same value.

---

## Requirements *(mandatory)*

### Functional Requirements

#### The setting

- **FR-001**: choom MUST support a view-orientation preference with exactly two values, `horizontal`
  and `vertical`.
- **FR-002**: The default MUST be `horizontal`. A user who has never set the preference MUST get
  today's layout, with no prompt, no question at first launch, and nothing to configure.
- **FR-003**: `/config view <value>` MUST set the preference. `/config view` with no value MUST report
  the current setting and the accepted values, matching the shape `/config assistant` already uses.
- **FR-004**: A successful set MUST take effect immediately — the screen rearranges on that keystroke.
  It MUST NOT require a restart, a reopen, or any further action.
- **FR-005**: A successful set MUST be persisted at the moment it succeeds, not deferred to exit.
  choom cannot rely on observing its own exit, and a preference lost to a killed session is a
  preference the user has to set twice.
- **FR-006**: Reading the preference, validating a value, and writing it MUST live in `choom.core` and
  MUST be callable and testable with no terminal, no TTY, and no event loop.

#### Where it is stored

- **FR-007**: The preference MUST be stored in per-user local state, outside every workspace
  directory. It MUST NOT be written to `.choom/config.toml` or to any other file inside a workspace.
  See "Decision: where the orientation is remembered" for the reasoning.
- **FR-008**: The preference MUST be a single value per user, applying to every workspace that user
  opens. It MUST NOT be keyed by workspace.
- **FR-009**: The per-user location MUST be resolved through a single function, so the whole store can
  be redirected in tests and no test can write into a developer's real profile — the arrangement
  `discovery.py`'s `profile_root()` already uses.
- **FR-010**: Setting the preference MUST create whatever per-user directory it needs. The resulting
  path MUST stay well within the Windows 260-character limit, MUST require no administrator rights,
  and MUST require no network access.
- **FR-011**: The store MUST tolerate a hand-edited file. A missing file, an unreadable file, a
  malformed file, a missing key, and a value that is not one of the two MUST all resolve to
  `horizontal` and MUST NOT prevent choom from starting.
- **FR-012**: Writing the preference MUST NOT corrupt or truncate an existing file, and MUST preserve
  any other content in it — the same guarantee the workspace config's writer gives.
- **FR-013**: A failure to write the preference MUST NOT abort the interface and MUST NOT prevent the
  requested layout from taking effect for the current session. It MUST be reported where the user is
  looking, naming what failed.

#### The vertical arrangement

- **FR-014**: In `vertical`, the collection bar MUST remain a single full-width row across the top,
  identical in content and behaviour to `horizontal`.
- **FR-015**: In `vertical`, the status bar MUST remain a single full-width row across the bottom,
  identical in content and behaviour to `horizontal`. The command bar and the link picker MUST keep
  their existing position in that same bottom strip.
- **FR-016**: In `vertical`, the body MUST be two bands: an upper band containing the scope pane and
  the record list side by side, in that left-to-right order, and a lower band containing the
  preview/edit region spanning the full width beneath both.
- **FR-017**: The scope pane MUST keep its existing fixed width in the upper band; the record list MUST
  take the remaining width of that band.
- **FR-018**: The preview/edit region in `vertical` MUST show the same content, for the same
  highlighted record, that it shows in `horizontal`, and MUST update on highlight changes on exactly
  the same terms.
- **FR-019**: The record list's labelled columns MUST be computed from the record list's own width in
  both orientations, so the wider list a vertical layout gives it is used rather than ignored.
- **FR-020**: `/config view horizontal` MUST restore the three-panes-across body exactly as it is
  today, with no residual difference from having been vertical.

#### Switching, and what survives it

- **FR-021**: Switching orientation MUST preserve the active collection, the selected scope, the active
  filter term and its matched rows, the highlighted record, and whether the backlinks section is
  expanded.
- **FR-022**: After a switch, the preview MUST show the record that is highlighted — the same one that
  was highlighted before.
- **FR-023**: After a switch, keyboard focus MUST land where it lands after any other command-bar
  command today: on the record list. The switch MUST NOT introduce a focus rule of its own.
- **FR-024**: Switching orientation MUST write nothing to the workspace, create no record, modify no
  record, and change no file the user owns. It is a display change and nothing else.
- **FR-025**: The orientation MUST NOT change while an editor pane is open, by any route — including a
  terminal resize crossing the fallback threshold.

#### What must not change

- **FR-026**: The interface MUST remain one screen. `vertical` MUST NOT add a screen, a mode, or a
  state; `list → preview → edit` are the states in both orientations.
- **FR-027**: The set of key bindings MUST be identical in both orientations. The feature MUST add no
  binding, remove none, and change the meaning of none. In particular `h`/`l` MUST continue to move
  focus between the scope pane and the record list, which remain left and right of each other in both.
- **FR-028**: The footer MUST show the same text in a given state regardless of orientation — list,
  task list, preview, backlinks-focused, editor, and link-picker states included. Orientation MUST NOT
  appear in the footer, because the user can see it.
- **FR-029**: The full-screen reading view and the full-screen editor MUST continue to take over the
  entire window in both orientations, and leaving either MUST return to the configured layout.
- **FR-030**: The feature MUST NOT change any command-line behaviour, any `--json` output, any exit
  code, any file format, or anything an AI assistant reads or writes.

#### Short terminals

- **FR-031**: At 80 columns by 24 rows, `vertical` MUST be usable: the record list MUST show its column
  header and at least three record rows, and the preview band MUST show at least four lines of content.
- **FR-032**: The upper band MUST retain a stated minimum height (the column header plus at least three
  record rows) and the lower band MUST retain a stated minimum height (at least four content lines).
- **FR-033**: When the terminal is too short for both minimums in FR-032 to be met, choom MUST render
  the horizontal layout for as long as that is true, and MUST return to vertical as soon as the
  terminal is tall enough. It MUST NOT refuse to render, MUST NOT show an error dialog, and MUST NOT
  clamp the bands into unusable slivers.
- **FR-034**: The fallback MUST NOT change the stored preference. A relaunch in a tall terminal MUST
  open vertical.
- **FR-035**: The fallback decision MUST be a function of the terminal's total height alone. It MUST
  NOT depend on the terminal's width, and MUST NOT depend on whether the command bar, link picker, or
  backlinks section happens to be visible — so opening any of those can never flip the layout.
- **FR-036**: The geometry rules — how the remaining height is divided between the bands, and the
  threshold at which the fallback engages — MUST be expressible as pure functions of the available
  size, testable without a terminal, in the manner of the existing column-width logic.
- **FR-037**: While the fallback is in effect, `/config view` with no value MUST report both facts: that
  the setting is vertical, and that horizontal is in effect because the terminal is too short.
- **FR-038**: Setting `vertical` on a terminal that is too short MUST still save the preference and MUST
  report that it is saved and will apply when the terminal is taller.
- **FR-039**: Existing width-driven degradation — dropping the lower-priority labelled columns,
  compacting the collection bar, eliding the workspace path — MUST behave identically in both
  orientations.

#### The regions that move with the preview

- **FR-040**: The inline editor MUST occupy the preview/edit region in both orientations — the third
  pane in `horizontal`, the lower band in `vertical`. Everything 014 specifies about it MUST hold
  unchanged in both: the list and scope pane stay visible, keyboard control is retained until the user
  leaves, the command bar cannot be opened, the footer swaps to the editor's bindings, the same keys
  save and discard, and the same confirmation fires.
- **FR-041**: The editor MUST wrap its content at the current edge of whichever region it occupies, and
  a change in that region's width — including one caused by a resize — MUST re-wrap without losing or
  reordering content. This is 014's existing requirement; `vertical` makes the region wider and must
  not break it.
- **FR-042**: The link picker MUST keep its existing position and behaviour in both orientations: in
  the bottom strip, above the status bar, bounded in height, with its own bindings shown in the footer
  and its existing too-small fallback unchanged. It MUST NOT overlay, hide, or horizontally displace
  the editor in either orientation.
- **FR-043**: The backlinks section MUST remain docked to the bottom of the preview/edit region in both
  orientations, and MUST be bounded so that preview content above it remains visible. In `vertical` it
  MUST NOT be allowed to consume the whole lower band.

#### Errors and discoverability

- **FR-044**: A value that is not `horizontal` or `vertical` MUST be rejected with a message that names
  the rejected value and names both accepted values. The layout MUST NOT change and nothing MUST be
  written.
- **FR-045**: A `/config` argument naming a setting that does not exist MUST be rejected with a message
  that names the unrecognised setting and names the settings that do exist. With two settings, "what
  to do instead" is a list the user can act on, which Principle V requires.
- **FR-046**: The help pane MUST list `/config` in a form covering both settings and both of `view`'s
  accepted values, so the command is discoverable without being guessed.
- **FR-047**: All of these messages MUST be delivered through the status bar, on the same terms as
  every other command-bar outcome. The feature MUST add no dialog and no prompt.

### Interface parity (constitution Principle II)

There **is** a `choom config` surface today: `choom config assistant [<value>] [--json]`. So the
question is real rather than rhetorical, and the answer is that **the CLI does not get a `config view`
equivalent**, as an inherently-interactive carve-out.

The reasoning:

- The setting's entire effect is how the interactive screen is drawn. The CLI has no panes, no
  preview, and no layout — there is no CLI behaviour that is missing, only a CLI command that would
  mutate a value it cannot itself demonstrate. Principle II's exception is written for exactly this:
  behaviour that is inherently interactive.
- `config assistant` has a CLI form because it has effects beyond the screen — it installs or removes
  a discovery file in the user's profile, which is something a setup script or an assistant has reason
  to do without opening the interface. The view orientation has no such effect. Nothing outside the
  running interface can observe it.
- The CLI serves AI assistants. An assistant has no use for the user's pane arrangement, and giving it
  a command to change one is a way for it to alter the user's workspace experience with no benefit to
  either side.
- The setting also lives in per-user state rather than in a workspace (FR-007), so a CLI form would be
  the first `choom` command that reads and writes outside a workspace and needs no workspace to run —
  a new shape for the CLI to take on, for a value with no non-interactive use.

The part that carries behaviour is shared regardless: FR-006 puts reading, validating, and writing the
preference in `choom.core`, where it is testable without a terminal. There is no logic here the CLI is
being denied — only a display arrangement it does not have.

Adding `choom config view` later would be purely additive and would break nothing, if a reason for it
ever appears. This spec records that no such reason exists today.

### Layering (constitution Principle I)

| Concern | Side | Why |
|---|---|---|
| The legal values and which is the default | `choom.core` | A rule about a setting; no terminal involved. |
| Resolving the per-user location, reading and writing the preference | `choom.core` | File logic, testable without a TTY, in the manner of `config.py`. |
| Tolerating a corrupt or absent preferences file | `choom.core` | The same never-fatal reading `get_assistant` already implements. |
| Dividing the available height between the bands; the fallback threshold | interface (pure functions) | Layout arithmetic, with no widget imports, exactly as `columns.py` is today. |
| Arranging widgets into two bands versus three panes | interface | Widget code, which core may not contain. |
| Wording the confirmation and error messages | interface | I/O formatting. |

Core's contribution is a value with two legal states and a place to keep it. It knows nothing about
panes.

---

## Success Criteria *(mandatory)*

- **SC-001**: In a window half the width of an ultrawide display, a user in `vertical` can read record
  titles in the list and prose in the preview without resizing the window, where the same window in
  `horizontal` truncates both.
- **SC-002**: Switching orientation takes one command and produces the new layout with no perceptible
  delay, with the previously highlighted record still highlighted in 100% of trials.
- **SC-003**: A user who never types the command sees no difference from today's choom, and has no
  setting to find, change, or get wrong.
- **SC-004**: The preference survives a quit and relaunch, and applies in a second, unrelated
  workspace, in 100% of trials.
- **SC-005**: Switching orientation changes zero bytes inside the workspace directory, verified across
  the whole tree.
- **SC-006**: A second user account opening the same workspace after the first switched to vertical
  gets horizontal, in 100% of trials.
- **SC-007**: The full set of key bindings and the full set of footer strings, captured state by state,
  are byte-identical between the two orientations.
- **SC-008**: At 80x24 in `vertical`, the record list shows at least three record rows plus its header
  and the preview shows at least four lines, on every target terminal verified before release.
- **SC-009**: Shrinking and regrowing the terminal across the fallback threshold produces the fallback
  and its reversal every time, with the stored preference unchanged after the sequence.
- **SC-010**: Every rejected `/config view` input produces a message naming both the rejected value and
  the accepted values, with the layout unchanged.
- **SC-011**: A corrupt, truncated, or hand-mangled preferences file never prevents choom from opening;
  it opens horizontal.

---

## Assumptions

- **Per-user, not per-workspace, is the right granularity.** Argued in "Decision" above. The preference
  follows the person and their monitor, and a map keyed by workspace would be more state for a
  distinction the user did not ask for.
- **The exact per-user path is a plan decision.** The requirement is that it is per-user, outside every
  workspace, short enough for Windows, and reachable without admin rights — the platform conventions
  (`%LOCALAPPDATA%` on Windows, a per-user config directory on macOS and Linux) satisfy that, and
  choosing between the reasonable candidates is research, not specification. A local (non-roaming)
  location is preferred on Windows, since the preference is shaped by a specific monitor.
- **TOML, and a file of its own.** choom already reads TOML for the workspace config, so the format
  costs nothing new. Whether the file also becomes home to future per-user state is left open; this
  spec adds one key to it.
- **No automatic orientation based on window shape.** It is tempting to read "a setting that could be a
  sensible default MUST be a sensible default" as an argument for detecting an ultrawide-half window
  and flipping automatically. It is not: an automatic flip rearranges the screen underneath the user
  every time they resize a window, which is churn rather than help — the same argument that kept the
  terminal title fixed for a session in 016 — and a preference at a given window shape is not
  deducible from the shape, since plenty of users want horizontal at half width. Horizontal is the
  sensible default; the setting is the override. The short-terminal fallback (FR-033) is not a
  counter-example: it is a usability floor below which one layout cannot be drawn at all, not a guess
  at what the user prefers.
- **No aliases and no abbreviations for the values.** `horizontal` and `vertical`, as the issue writes
  them. Two words, typed rarely, and the error message names both.
- **The command is only reachable from the list screen.** The command bar is a list-screen surface; the
  editor's own `/` commands are a separate set. So the orientation cannot be changed from inside an
  editor or a full-screen view, and FR-025 records that as a guarantee rather than an accident.
- **Nothing watches the preferences file.** A running session reads it once at startup and thereafter
  holds the value it was told. Live cross-session propagation is not something the user asked for and
  would mean a watcher for a value that changes twice a year.
- **Verification on the target terminals is manual**, as it is for every interface change — Windows
  Terminal, iTerm2, macOS Terminal, PuTTY, and inside tmux — and includes a half-width ultrawide
  window, an 80x24 window, and a window short enough to trigger the fallback.

---

## Out of Scope

- **A CLI `config view` command.** See "Interface parity" — an explicit carve-out, not an omission.
- **Automatic orientation from terminal size or aspect ratio.** See Assumptions.
- **Any orientation other than the two.** No user-defined pane arrangement, no reordering of the panes,
  no swapping which side the scope pane is on.
- **User-adjustable pane sizes.** No drag, no keyboard resize, no configurable split ratio or pane
  width, in either orientation. The bands' proportions are fixed by the spec.
- **Hiding a pane.** Collapsing the scope pane or the preview is a different feature and is not implied
  by this one.
- **Per-workspace orientation.** FR-008 settles it as one value per user.
- **Remembering any other display state** — the last collection, the last scope, the last highlighted
  record, window geometry. This feature adds one preference and no others.
- **A settings screen or an interactive configuration flow.** `/config` is the surface.
- **Changing `/config assistant` or where the assistant setting is stored.** It stays in the workspace
  config; "Decision" explains why that remains correct.
- **Migrating any existing setting into the new per-user store.**
- **Live propagation of a preference change to other running sessions.**
- **Changing the full-screen reading view or the full-screen editor.** They already take the whole
  window; orientation does not apply to them.
- **README changes.** Per CLAUDE.md, the feature list describes the released version; this lands with
  the release, not with the feature.

---

## Dependencies

- Depends on the constitution amendment for issue #82 (v2.1.0) having merged, which it has — it is the
  version this spec is written against.
- Depends on the existing `/config` command-bar verb and its status-bar reporting, which this extends
  with a second setting rather than replaces.
- Depends on `014-inline-editor-pane`: the inline editor occupies the preview region, so it moves with
  that region. FR-040 and FR-041 restate what must continue to hold; nothing in 014 is contradicted or
  reopened. In particular, 014 FR-008 (no command bar while the editor is open) is what makes FR-025
  achievable rather than merely required.
- Depends on `015-link-picker`: the picker renders in the bottom strip, which this feature does not
  move. FR-042 restates that its position, its bounds, and its too-small fallback are unchanged, and
  FR-035 ensures opening it can never flip the orientation.
- Depends on the existing column-width logic (`011-ui-refinements`), which is already a pure function
  of the record list's width and therefore needs no change to benefit from a wider list — FR-019 makes
  that explicit.
- Depends on the existing atomic-write facility for not corrupting a file on a write.
- Adds no third-party dependency. TOML reading is in the standard library and is already in use.
- Related to `019-completed-tasks-partition` (issue #43), in flight in parallel, which changes what the
  scope pane offers for Tasks. The two touch different things — that one changes the scope pane's
  contents, this one changes where the panes sit — and neither blocks the other.
