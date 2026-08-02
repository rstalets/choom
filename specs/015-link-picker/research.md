# Phase 0 Research: A Picker for Ambiguous `/link`

**Feature**: `015-link-picker` | **Date**: 2026-08-01 | **Plan**: [plan.md](./plan.md)

Every unknown in the plan's Technical Context is resolved below. Nothing is left as
NEEDS CLARIFICATION.

---

## R1 — Where the picker lives, and who owns it

**Decision**: A `LinkPicker` widget composed into each host screen's `#bottom-bar`, above the
`StatusBar`, with `display = False` until a choice is pending. `EditorPane` reaches it with
`self.screen.query_one(LinkPicker)`.

**Rationale**: `#bottom-bar` is already a docked, `height: auto` `Vertical` that stacks widgets above
the status bar — `ListScreen` puts a `CommandBar` there and hides it until `/` is pressed. A second
hidden occupant is the pattern, not an extension of it. Reaching it through `self.screen` is exactly
how `EditorPane._render_status()` already reaches the `StatusBar`, which matters because the pane has
two hosts: whichever screen mounted the pane also owns the bottom bar, and the same line of pane code
finds the right picker in both. That is FR-004 (parity) satisfied by construction rather than by
remembering to keep two paths in step.

**Alternatives considered**:

- *Mount the picker inside `EditorPane`*. Rejected: inline, the pane is the preview pane, so the list
  would appear mid-screen inside the editor's footprint and would resize the editor — FR-005 forbids
  exactly that.
- *Have the pane mount a picker into the bottom bar on demand*. Rejected: same result, more moving
  parts, and a mount/unmount race on every invocation for something that costs nothing to keep hidden.
- *A Textual `ModalScreen`*. Rejected outright by the spec — it is the modal picker the issue exists
  to avoid.

---

## R2 — Keys, focus, and stopping the editor acting underneath

**Decision**: The picker's `ListView` takes focus while a choice is pending; `↑`/`↓` and `enter` are
`ListView`'s own, `esc` is bound on the picker. On dismissal focus returns to `#editor`. While the
picker is open, `EditorPane.check_action()` returns `False` for `save`, `save_and_close`, `close`, and
`cancel_request`.

**Rationale**: The Links section already does this — `action_toggle_links` calls `.focus()` on its
`ListView`, `esc` closes, and the footer string swaps. Focus is what makes `↑`/`↓` and `enter` land on
the list without the pane parsing raw keys. The `check_action` gate is needed because `EditorPane`
binds `ctrl+o`, `ctrl+x`, and `ctrl+c` with `priority=True`, which are checked from the app down and so
would still fire while another widget holds focus; the pane already uses `check_action` to gate
`cancel_request` on `self._request is not None`, so gating on "a choice is pending" is the same idiom.
`escape` on the pane is not `priority`, so it will not reach the pane while the picker has focus — but
it is included in the gate anyway, because relying on a binding's non-priority status to prevent a
discard is a fragile thing to leave implicit.

Moving focus does not move the text cursor: `TextArea.cursor_location` is unchanged by focus, which is
what FR-003 requires. The visible cursor stops blinking while the list is open, which is honest — it
signals where the keys are going.

**Alternatives considered**:

- *Keep focus in the editor and intercept keys in `EditorTextArea._on_key`*. Rejected: it reimplements
  list navigation, and it puts `↑`/`↓` in the same handler as ordinary cursor movement, where a missed
  branch silently moves the cursor through the document — the one thing FR-003 forbids.
- *A Textual `OptionList`*. Workable, but `ListView` is what the Links section uses and what
  `tui/rendering.py` already renders rows for; matching it keeps one row-building idiom in the file.

---

## R3 — Wrapping at both ends

**Decision**: `LinkPicker` subclasses `ListView` and overrides `action_cursor_down` / `action_cursor_up`
to call Textual's own `loop_from_index(..., wrap=True)`.

**Rationale**: Verified against the installed Textual (8.2.8): `ListView.action_cursor_down` calls
`loop_from_index(self._nodes, self.index, wrap=False)` and stops at the end of the list. FR-006 requires
wrapping, so the two actions are overridden. The helper the base class already uses takes `wrap` as a
parameter, so wrapping is a one-argument change rather than a hand-rolled index loop.

**Alternatives considered**:

- *Leave it non-wrapping*. Rejected: FR-006 is explicit, and with a bounded, scrolling list, "keep
  pressing `↑` and nothing happens" is the wrong feedback for a list of three.

---

## R4 — Ordering, dates, and where that logic lives

**Decision**: New core function `link_candidates(workspace, query) -> tuple[LinkCandidate, ...]` in
`core/links.py`, returning matches newest first with ties broken by title, undated records last.
`find_link_targets()` becomes `tuple(c.target for c in link_candidates(...))`.

**Rationale**: Principle I — the scan, the match rule, the date normalisation, and the sort are all
logic, and logic lives in core where it is testable without a terminal. A widget that sorted its own
rows would be the exact "assembly done in an adapter" the gate asks about. Re-expressing
`find_link_targets()` as a projection means one scan implementation and one definition of "matches",
so the single-match fast path (FR-013) cannot drift from what the picker offers (FR-016).

The sort itself follows `core/documents.py`, which already orders records newest-first the same way:
sort by title ascending, then sort by date descending. Python's sort is stable and `reverse=True`
preserves the original order of equal keys, so the title order survives as the tie-break — the same
two-pass idiom the collection listings use, not a new one.

**Alternatives considered**:

- *Add `created` to `LinkTarget` and sort in the widget*. Rejected on both halves: `LinkTarget` is
  constructed in 13 places for purposes that have nothing to do with picking, and the sort would be
  adapter-side.
- *A second core function that scans again for dates*. Rejected: two scans for one command, and two
  chances for the picker and `/link` to disagree.

---

## R5 — Normalising two different date types

**Decision**: `LinkCandidate.date` is `str | None`, holding an ISO `YYYY-MM-DD` date. Documents supply
`Document.created` (already an ISO string) verbatim; tasks supply `Task.created.isoformat()` when set
and `None` when not.

**Rationale**: The two record types genuinely differ — `Document.created: str`, `Task.created: date | None`
— and the picker needs one comparable, displayable value. ISO strings sort lexicographically in date
order, so no parsing is needed to order them, and no `date` object needs formatting at render time. A
task with no `created` is a real case (a checkbox typed by hand), so `None` is a value the row renderer
and the sort both handle rather than an error.

**Alternatives considered**:

- *Parse everything to `datetime.date`*. Rejected: it makes a malformed hand-edited `created:` string
  raise or silently vanish inside a search, when Principle IV wants it skipped and shown.

---

## R6 — Row content and truncation

**Decision**: `render_candidate_row(candidate, width)` in `tui/rendering.py` produces
`title · collection · date`, truncating the title (with an ellipsis) so the collection and date always
survive. Undated rows show `—` where the date goes.

**Rationale**: FR-010 names all three fields, and the point of the row is to disambiguate: the two
fields that do the disambiguating when titles collide are the two that must not be the ones dropped.
Width-aware text belongs in the adapter — `in_flight_status(breadcrumb, width)` in `status_bar.py` is
the same call shape, and `render_link_row` already lives in `rendering.py`. Passing `width` in (rather
than reading it off a widget) keeps the function a pure string function that unit tests can drive
without a terminal.

**Alternatives considered**:

- *Truncate from the right, dropping the date*. Rejected: it removes the disambiguator precisely when
  space is tight, which is when the list is hardest to read.
- *Wrap onto two lines*. Rejected: it halves how many candidates fit and makes the highlight ambiguous.

---

## R7 — Bounded height and the too-short-terminal fallback

**Decision**: `#link-picker` gets `max-height: 8` in `app.tcss`, mirroring `#links-section`
(`max-height: 12`, inner list `max-height: 10`). The picker requires a screen at least
`MIN_PICKER_SCREEN_HEIGHT = 12` rows tall; below that, `/link` falls back to today's
`link_ambiguous_status()` message and shows no list.

**Rationale**: FR-012 wants a bounded list that scrolls internally, which is what a `max-height` on a
`ListView` gives for free. FR-017 wants an honest fallback rather than a degraded list, and the honest
fallback already exists and is already tested — `link_ambiguous_status()` stays rather than being
deleted, which is why the behaviour it describes is not being removed from the codebase, only from the
common path. Twelve rows leaves the editor a usable buffer above an eight-row picker plus the status
line; below that the picker would own more of the screen than the document, which is the modal
experience in all but name.

**Alternatives considered**:

- *Shrink the list to whatever fits*. Rejected by FR-017: a one-row "list" is a worse version of both
  options.
- *Compute the budget from the editor's height instead of the screen's*. Rejected: inline, the editor
  occupies the preview pane while the bottom bar spans the screen, so the screen is the honest
  measure — and it is the same measure in both hosts, which parity needs.

---

## R8 — Re-resolving the chosen record at insertion

**Decision**: On `enter`, call `resolve_id(workspace, candidate.target.id)`. If it returns `None`,
report and leave the line as typed; otherwise format the link from the freshly resolved target.

**Rationale**: FR-015. The workspace is a folder another program can change, and the gap between
listing and choosing is real (an assistant writing files, a sync client, another terminal). Formatting
the link from the re-resolved target rather than the remembered one also repairs the case where the
file moved but the id survived — which is the whole premise of `008`'s id-is-identity rule.

**Alternatives considered**:

- *Trust the listed candidate*. Rejected: it writes a link to a path that no longer exists, and a link
  that resolves to nothing is harder to notice than a report.

---

## R9 — Surviving a terminal resize with a choice pending

**Decision**: `LinkPicker` holds its `LinkCandidate` tuple and its highlighted index, and rebuilds row
labels from them in `on_resize`, restoring the index afterwards. If the resize drops the screen below
`MIN_PICKER_SCREEN_HEIGHT`, the picker closes and the fallback message is shown.

**Rationale**: FR-018. Rows are truncated at build time against a width, so a width change has to
rebuild them or the text is wrong. Keeping the candidates on the widget (rather than re-running the
search) means the pending choice is a decision, not a query result that could come back different
mid-decision. `EditorPane.on_resize` already re-renders the in-flight `/ai` status for the same reason,
so a resize handler that repairs width-dependent text is established practice here.

**Alternatives considered**:

- *Re-run `link_candidates()` on resize*. Rejected: the workspace may have changed, so the list could
  silently gain or lose rows under the user's highlight.

---

## R10 — Test layers, and the two clock traps

**Decision**: Unit tests for `link_candidates()` ordering and for `render_candidate_row()` truncation;
integration tests for the picker flow (open, move, insert, cancel), for both fast paths staying
unchanged, and for host parity. The existing
`test_link_several_matches_leaves_the_line_and_names_candidates` is rewritten — it asserts the old
behaviour deliberately, and this feature replaces it. Fixture dates are derived from `date.today()`.

**Rationale**: Principle VI asks for risk-based coverage in the right layer, not one test per
acceptance scenario. What can actually break: the sort (unit — pure, cheap, many cases), the
truncation arithmetic (unit), the key wiring and focus dance (integration, which is the only layer
where focus exists), and parity between the two hosts (integration, by running the same flow from both
entry points). Two clock traps to avoid: hard-coding `created:` dates that fall out of a month-scoped
view, and assuming today's date orders two fixtures — both are avoided by writing dates as
`date.today() - timedelta(days=n)`.

**Alternatives considered**:

- *Keep the old ambiguity test and add new ones*. Rejected: it asserts that ambiguity reports and
  stops, which is now only true below the fallback threshold — it is rewritten into exactly that case,
  so the fallback keeps its coverage.
