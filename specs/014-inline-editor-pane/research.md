# Research: Editor Replaces the Preview Pane

**Feature**: `014-inline-editor-pane` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

All findings are against the code as it stands on this branch and Textual 8.2.8, the pinned version.
Where a finding was verified by reading the installed library rather than the docs, that is said.

---

## R1: How does an editor live in the preview pane and full-screen at once?

**Decision**: Extract everything `EditScreen` does into an `EditorPane` widget that holds the
`EditorTextArea` and all editing behaviour. `EditScreen` keeps its name and becomes a thin `Screen` that
composes an `EditorPane` plus its own `StatusBar`. `ListScreen` mounts the same `EditorPane` inside
`#preview-pane`.

**Rationale**: The spec requires identical capability in both presentations (FR-019). One implementation
mounted in two places is the only arrangement where that is true by construction rather than by
vigilance. The alternative — a second editor implementation for the pane — would need every future
change made twice, and the AI-request path alone is 120 lines of state that must not fork.

**Alternatives considered**:

- *Leave `EditScreen` a screen and dock it over the pane's region.* Textual can do it, but a screen is
  the unit that suspends the screen beneath it, which is exactly the behaviour this feature exists to
  remove. It would also re-raise the `on_screen_suspend` question (R6) with no upside.
- *Move only the `TextArea` and leave save/discard/AI logic on the host screens.* Splits one state
  machine across two hosts; the mirror baseline and the in-flight request would have to be duplicated.

**Consequence for the host**: closing is host-specific — `EditScreen` pops itself, `ListScreen` unmounts
the pane. `EditorPane` therefore posts a `Closed` message rather than calling `pop_screen` itself, and
each host handles it. This is the only place the two presentations differ.

---

## R2: Which list keys would leak into an inline editor, and which are already safe?

**Decision**: Only `tab` and `shift+tab` need explicit handling. Everything else is already stopped by
`TextArea`.

**Verified by reading `textual.widgets.TextArea.BINDINGS` at 8.2.8**:

| Key | Bound in `TextArea`? | What happens with the editor focused |
|---|---|---|
| `j`, `k`, `e`, `b`, `space`, `/` | printable | Inserted as text; never reaches `ListScreen` |
| `up`, `down`, `left`, `right`, `pageup`, `pagedown` | yes | Cursor movement in the buffer |
| `ctrl+d` | yes (`delete_right`) | Deletes a character — never reaches `ListScreen.action_delete` |
| `ctrl+c` | yes (`copy`) | Copy, except while a request is in flight (R7) |
| `escape` | **no** | Bubbles to the editor's own discard binding |
| `tab` / `shift+tab` | **no** — `tab_behavior="focus"` deliberately lets it through | Bubbles past the editor |

**The `tab` problem**: full-screen, `tab` runs the base `Screen`'s `focus_next`, which finds nothing else
focusable on `EditScreen`, so focus stays put and the key looks inert. Inline, the same key would either
switch collection (`ListScreen` binds `tab` to `next_collection`) or move focus into the list — both
violate FR-006 and FR-007.

**Resolution**: `EditorPane` binds `tab` and `shift+tab` to a no-op. No `priority` needed: `TextArea`
does not consume them, so they bubble to the pane — an ancestor of the focused widget — before reaching
the screen. This also makes full-screen `tab` inert by intent rather than by the accident of there being
nothing else to focus.

**Belt and braces**: `ListScreen.check_action` additionally returns `False` for every list action while
the pane is mounted. Two of its actions (`delete`, `next_collection`) already consult it, so the hook
exists; this widens the condition. It costs one branch and means a future `ListScreen` binding on a
non-printable key cannot silently become reachable mid-edit.

---

## R3: Do the editor's `priority=True` bindings still win from a widget?

**Decision**: Keep `ctrl+o`, `ctrl+s`, `ctrl+x`, and `ctrl+c` as `priority=True` bindings on
`EditorPane`, and cover `ctrl+x` with a test.

**Rationale**: Textual checks priority bindings before the focused widget's own bindings, walking the
binding chain from the focused widget up through its ancestors to the app. `EditorPane` is an ancestor
of the focused `EditorTextArea`, so it is in that chain. This matters for exactly one key: `TextArea`
binds `ctrl+x` to `cut` and `ctrl+s` is nothing to it, so without priority the save-and-close key would
cut the current line instead of saving.

**Risk and mitigation**: this is inference from documented behaviour ("checked prior to the bindings of
the focused widget"), and the docs' examples are all app- or screen-level. The mitigation is a test that
presses `ctrl+x` in the inline editor and asserts the file was written and the pane closed — if the
inference is wrong, that test fails loudly rather than the behaviour degrading quietly. **Fallback if it
fails**: move those four bindings to the two host screens (`ListScreen` and `EditScreen`), gated by
`check_action` on whether an editor is open, and have their actions delegate to the mounted pane.

---

## R4: What happens to the status bar?

**Decision**: `EditorPane` writes to `self.screen.query_one(StatusBar)` rather than to a bar it owns.
`ListScreen` restores its own status text when the pane closes.

**Rationale**: Both hosts already have exactly one `StatusBar`, and the pane needs no knowledge of which
one it is writing to. `EditScreen` today does `self.query_one(StatusBar)`; from a widget the same lookup
through `self.screen` resolves to the host's bar in both presentations.

**FR-009** falls out of this: the pane writes `EDIT_HELP` on mount and the host rewrites its own help on
close. `ListScreen._render_status` already rebuilds the collection indicator, help text, and warning
count, so the restore is a call to a method that exists.

---

## R5: Where does the discard confirmation go, and what does its dismissal disturb?

**Decision**: Unchanged — `ConfirmDialog` is pushed as a screen over whatever is below. Declining
refocuses the pane's `#editor`.

**The catch**: pushing and popping a screen over `ListScreen` fires `on_screen_suspend` and
`on_screen_resume` on it. Today `on_screen_resume` rebuilds the scope pane and calls `refresh_rows`,
which calls `_update_preview` — which would overwrite the pane the editor is sitting in, mid-edit, the
moment the user chose "Continue Editing".

**Resolution**: `on_screen_resume` returns early while the pane is mounted, restoring focus to the
editor instead of refreshing. This is the same rule R6 arrives at from the other direction.

---

## R6: The list keeps ticking behind an editor that no longer covers it (FR-021)

**Decision**: While the inline editor is mounted, the list does not re-render at all. The refresh timer
is paused when the pane opens and resumed when it closes, and the close path runs the full refresh that
`on_screen_resume` runs today.

**Rationale**: This reproduces exactly what happens now — a full-screen editor suspends `ListScreen`,
which pauses the timer (`on_screen_suspend`) and refreshes on the way back (`on_screen_resume`). Keeping
that shape means no new interleaving to reason about, and FR-021 is satisfied structurally rather than
by auditing every field a refresh touches. The spec's Assumptions explicitly permit pausing.

**What a live refresh would have cost**: `refresh_rows` clears and rebuilds the `ListView` and then calls
`_update_preview`, which writes to `#preview`. Both would have needed conditional paths, and a rebuild
under a focused-elsewhere `ListView` is a focus hazard for no user-visible gain — nothing in the list is
being read while the user is typing in the pane.

**Guards, in three places, because three paths reach a render**:

1. `_refresh_tick` — returns early while the pane is mounted (timer is paused too; this is the belt).
2. `_update_preview` — returns early while the pane is mounted (R5's dialog case reaches it).
3. `on_screen_resume` — returns early while the pane is mounted.

**FR-022** follows: with the list frozen, the row for a record deleted on disk mid-edit stays put, and
the save reports its own failure through the existing path (`SaveResult.ok == False`).

---

## R7: The `/ai` request and its `ctrl+c`

**Decision**: Moves into `EditorPane` unchanged, including the `check_action` gate that makes `ctrl+c`
live only while a request is in flight.

**Rationale**: The deviation from Principle V's `ctrl+c` reservation was justified in `006`'s plan and is
inherited, not introduced, here. `TextArea` binds `ctrl+c` to `copy`; when `check_action` returns
`False` the binding is skipped and copy runs, which is today's behaviour and stays it.

**One inline-specific check**: the request's completion calls `editor.focus()` from
`call_from_thread`. Inline, that must not fight the list for focus — it will not, because the list is
frozen (R6) and nothing else is claiming focus during the wait.

---

## R8: How does an inline editor open for a record the list has not shown yet? (FR-016)

**Decision**: The create paths refresh the scope pane and rows, selecting the new record, *before*
mounting the editor. The `_pending_select_id` mechanism stays for the close path.

**Rationale**: Today `_on_create_requested` sets `_pending_select_id` and pushes the editor; the list
catches up on resume, which the user never sees because the list is hidden. Inline, the list is in
plain view beside an editor for a record it does not list — FR-016 exists to rule that out. Refreshing
first costs one scan that the close path would have run anyway.

**Affected entry points**: `_on_create_requested` (note, meeting), `_on_daily_requested`. Task creation
does not open an editor and is untouched.

---

## R9: Two places outside the TUI ask "is an editor dirty?"

**Decision**: Replace both `isinstance(screen, EditScreen)` scans with one helper that finds every
mounted `EditorPane` across the screen stack.

**Where**:

- `ChoomApp.action_quit` (bug #64 / constitution 2.0.0) — `ctrl+q` must raise the confirmation when an
  inline editor is dirty, exactly as it does for a full-screen one.
- `ChoomApp.toggle_task_and_track` — skips propagating a task's state into documents whose editor is
  open and dirty, so the buffer is not fought over.

**Rationale**: after R1 the dirty state lives on the pane, not the screen. A single
`open_editors(app) -> list[EditorPane]` helper (iterate `app.screen_stack`, query each for
`EditorPane`) covers both presentations and leaves both call sites one line long. Missing either one is
a silent data-loss bug, which is why they are listed here rather than left to be found.

---

## R10: What breaks in the existing test suite, and what is the smallest fix?

**Decision**: Fix `tests/helpers.py:open_edit` to assert an editor is *open* rather than that the
current screen is an `EditScreen`, and let most callers ride on that.

**Rationale**: 15 test files reference `EditScreen`, but the majority reach the editor through
`open_edit` and then query `#editor` on `app.screen`. That query keeps working inline, because the
`EditorTextArea` still carries `id="editor"` and is now a descendant of `ListScreen`. The assertion
inside the helper is what actually breaks.

**Expected genuine breakage** (to be confirmed by running the suite, not assumed):

- `tests/integration/test_edit_from_list_tui.py`, `test_create_opens_editor_tui.py`,
  `test_daily_note_tui.py` — assert a screen push after `e` or a create.
- `tests/integration/test_ctrl_q_confirm.py` — reaches the dirty check of R9.
- `tests/unit/test_footer_bindings.py` — asserts which bindings show in which state.
- `tests/integration/test_discard_tui.py` — the confirmation's host changes (R5).

**`tests/integration/test_edit_presentation.py` is the one to keep untouched if possible**: it already
asserts `show_line_numbers`, `soft_wrap is True`, `tab_behavior == "focus"`, and that a wide paragraph
does not scroll horizontally at 40 columns. Those are FR-004 and FR-019 for the full-screen editor; the
inline versions of the same assertions are new tests beside them, not edits to these.

---

## R11: Does wrapping need any work at all? (FR-004)

**Decision**: No new behaviour. `soft_wrap` is already `True` and is already asserted at 40 columns.

**Rationale**: `TextArea.soft_wrap` defaults to `True`, the editor never sets it `False`, and
`test_edit_presentation.py` pins it. Wrapping to the *pane's* edge is then automatic — the widget wraps
to its own width, and its width is the pane's.

**What does need a test**: the pane is narrower than the full screen and carries a line-number gutter,
so the new assertion is that the same no-horizontal-scroll property holds for the inline editor at a
narrow terminal size. `tests/integration/test_narrow_terminal_tui.py` is the established home for that
size of check.
