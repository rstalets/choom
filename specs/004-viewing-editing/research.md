# Phase 0 Research: Viewing and Editing

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-07-28

Ten decisions. R1 is the one the rest hang off: because a save may change only the `updated` line, the
save path is forbidden from parsing the buffer, and that single constraint determines the module
boundary, the data model, and most of the test surface.

Textual API facts below were checked against the current Textual documentation, not recalled.

---

## R1: The `updated` stamp is surgical, not a re-render

**Decision.** `core/editing.py` gets `stamp_updated(text: str, timestamp: str) -> tuple[str, bool]`.
It locates the frontmatter block by exactly the rules `_parse_document` already uses — the text starts
with `---\n`, and the block ends at the first `\n---` after index 3 — then finds the first line inside
that block matching `^updated:` and replaces **only the portion after the colon**. Every other byte of
the file, inside the block and out, is passed through untouched. It returns `(new_text, True)` when it
stamped and `(text, False)` when it could not, and it never raises.

Not stampable, all returning `(text, False)`: no leading `---\n`; no terminator; no `updated:` line
inside the block. In each case the caller writes the buffer as typed and surfaces a warning (FR-018).

**Rationale.** FR-016 says a save writes the buffer exactly, changing only `updated`, and the spec's
Assumptions say the buffer wins on frontmatter — whatever fields the user typed are what gets written.
Any implementation that goes `text → Document → render_frontmatter → text` violates both. The existing
`render_frontmatter()` (`core/frontmatter.py:75`) emits a fixed `_KEY_ORDER` with `json.dumps` quoting,
so a user who reordered their fields, used single quotes, or added a field would have that silently
undone by the act of saving. That is the exact failure Principle IV exists to prevent.

**Alternatives considered.**

- *Round-trip through `Document` and `render_frontmatter`.* Rejected: reorders keys, requotes values,
  and drops any field outside the fixed six. Breaks FR-016 outright.
- *Parse the block with PyYAML, mutate `updated`, re-dump.* Rejected for the same reason feature 001
  hand-wrote its emitter: `yaml.safe_dump` sorts keys, rewraps at 80 columns, and re-styles scalars.
  It would reformat a user's hand-written block on every save.
- *Refuse to save when the frontmatter does not parse.* Rejected: FR-018 requires the content be
  written anyway, and refusing to save is the one outcome that can actually lose the user's work.
- *Insert an `updated:` line when the block parses but lacks one.* Rejected: inserting a key into a
  hand-edited block changes more than `updated` and has no obviously correct position. Treated as
  not-stampable instead, which is the conservative reading of FR-017 plus FR-018.

---

## R2: Line endings and the trailing newline

**Decision.** `load_for_edit` reads the file with `newline=""` so Python performs no translation,
records `newline: "\r\n" | "\n"` from the **first** line ending present (defaulting to `os.linesep`'s
convention only for a file with no line ending at all), records `trailing_newline: bool`, then hands
the widget a copy normalised to `\n`. `save_buffer` reverses both: it translates `\n` back to the
recorded convention and restores the recorded trailing-newline state, writing with `newline=""`.

A file with **mixed** line endings is normalised to its first-seen convention. This is recorded as a
known, accepted deviation rather than hidden — see [data-model.md](./data-model.md).

**Rationale.** FR-019 requires both conventions to survive a save, and Windows is a first-class
target. Textual's `TextArea` holds its document in `\n` form regardless of what was loaded, so without
an explicit capture-and-restore every save from a Windows user silently converts their file to LF —
a whole-file diff on a one-character edit, which is exactly the kind of churn that makes a tool
untrustworthy inside a synced folder.

**Alternatives considered.**

- *Let the widget's normalisation stand and always write `\n`.* Rejected: fails FR-019 and produces a
  whole-file diff for a one-character change.
- *Preserve mixed endings exactly, line by line.* Rejected as disproportionate: it means carrying a
  per-line ending map through the buffer, and a mixed-ending markdown file is already the product of
  something upstream being careless. Normalising to the dominant convention is the honest, documented
  trade — and it is stated in the data model rather than left as a surprise.

---

## R3: Dirty state is a comparison, not a flag

**Decision.** `EditScreen` holds `original_text` — the `\n`-normalised text as loaded — and computes
`is_dirty` as `text_area.text != original_text`. A successful save sets `original_text` to what was
just saved.

**Rationale.** FR-025 has two clauses that look separate and are not: no prompt after a save, and no
prompt when the user has manually undone their own changes (US2 scenario 6). A comparison satisfies
both with one rule and no state machine. An "edited" boolean satisfies neither cleanly — it needs an
explicit reset on save, and it cannot detect an undo at all.

**Alternatives considered.**

- *A boolean set by `TextArea.Changed`.* Rejected: fires on every keystroke including one that
  restores the original text, so US2 scenario 6 would wrongly prompt.
- *`TextArea.history` / checkpoint depth.* Rejected: same defect — history depth is non-zero after a
  typed-then-deleted character — and it couples us to a widget internal.

---

## R4: The edit state is its own screen

**Decision.** A new `EditScreen(Screen[None])` is pushed on top of `PreviewScreen`, which is itself
pushed over `ListScreen`. The screen stack becomes the state machine. `PreviewScreen` gains an
`on_screen_resume` that re-reads the file, so returning from a save shows the saved content (FR-007).

**Rationale.** Principle V names three states; three screens make that structural rather than
conventional, and each screen's `BINDINGS` and footer string are then correct by construction rather
than by an `if` in a shared handler. `ListScreen` already uses exactly this `on_screen_resume`
re-read pattern (`list_screen.py:92`), so FR-007 costs one method that matches existing code.

**Alternatives considered.**

- *Swap the `Markdown` widget for a `TextArea` inside `PreviewScreen`.* Rejected: every binding and
  the footer become conditional on a mode variable, which is the improvisation Principle V forbids,
  and `esc` would need to mean two different things in one handler.
- *One screen with a mode reactive.* Same objection, plus it makes the discard prompt's "return to
  the buffer intact" harder, since the widget would have to survive a mode change.

---

## R5: `TextArea` configuration — one option, not the convenience constructor

**Decision.** `TextArea(text, show_line_numbers=True, id="editor")`. Nothing else is set.

Checked against current Textual documentation, the constructor defaults are:

| Option | Default | Wanted | Action |
|---|---|---|---|
| `soft_wrap` | `True` | `True` (FR-011) | none — already correct |
| `tab_behavior` | `"focus"` | not inserting a tab (FR-012) | none — already correct |
| `show_line_numbers` | `False` | `True` (FR-010) | **set explicitly** |
| `line_number_start` | `1` | `1`, so line 1 is the opening `---` | none — already correct |
| `read_only` | `False` | `False` | none |

`TextArea.code_editor()` sets `soft_wrap=False`, `show_line_numbers=True`, and
`tab_behavior="indent"` — two of those three are wrong for prose, which is precisely what
REQUIREMENTS.md §4.5 warns about. Confirmed against the docs rather than assumed.

**Rationale.** The requirement §4.5 spells out is satisfied by the plain constructor plus one keyword.
Writing it that way makes the §4.5 hazard unreachable rather than merely avoided by discipline.

**Alternatives considered.**

- *`TextArea.code_editor()` with `soft_wrap` and `tab_behavior` set back.* Rejected: three options to
  undo two, and the next person to read it has to check what the convenience constructor did.
- *A custom subclass.* Rejected: nothing to add. Gutter numbering of real lines only, with wrapped
  rows unnumbered (FR-011), is already how the widget renders.

---

## R6: The discard prompt is a `ModalScreen[bool]` with a callback

**Decision.** `DiscardDialog(ModalScreen[bool])` with Discard and Cancel buttons, dismissing `True`
and `False`. `EditScreen` pushes it with a callback — `self.app.push_screen(DiscardDialog(), handler)`
— not `push_screen_wait`.

**Rationale.** `ModalScreen` blocks the parent screen's bindings while it is up, which is what a
confirmation needs. `push_screen_wait` requires running inside a `@work` worker and raises
`NoActiveWorker` otherwise; the callback form has no such constraint and keeps the action method
synchronous. FR-027 ("Cancel returns with the buffer and cursor intact") then costs nothing: the
`TextArea` is never unmounted, so there is no state to restore.

**Alternatives considered.**

- *`push_screen_wait` inside a worker.* Rejected: a worker for a two-button dialog, and it makes the
  `esc` action async for no gain.
- *An inline confirmation row in the footer.* Rejected: FR-026 says modal, and a footer prompt does
  not block the underlying bindings.

---

## R7: Atomic write

**Decision.** `save_buffer` writes to a temporary file **in the target's own directory**, then
`os.replace()`s it over the target. On any exception the temporary file is removed and the original is
left untouched. `OSError` — including Windows sharing violations on OneDrive-synced files — is caught
and returned as a failed `SaveResult`, never raised at the screen.

**Rationale.** FR-020 requires that a failed save leave the file exactly as it was, never truncated.
Opening the real file for writing makes truncation the default failure mode: the file is emptied
before the first byte of new content is written, so a crash or a full disk destroys the document. A
same-directory temp keeps the rename on one filesystem, which is what makes `os.replace` atomic.

The screen keeps the user in the edit state with the buffer intact on failure (FR-020's second half),
so a document on a read-only file can still be copied out.

**Alternatives considered.**

- *`Path.write_text` in place.* Rejected: truncates on failure. This is the whole point of FR-020.
- *A temp file in the system temp directory.* Rejected: usually a different filesystem, so
  `os.replace` degrades to a copy and stops being atomic — and on Windows it can fail outright.
- *Write a `.bak` first.* Rejected: leaves litter in the user's vault, which then shows up in their
  scans and their synced folder.

---

## R8: `endpaper init` never clobbers guidance files

**Decision.** `init_workspace` writes both `AGENTS.md` and the new `CLAUDE.md` through
`os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)`, catching `FileExistsError` to mean "skipped".
It returns `InitResult(workspace, written, skipped)`. The CLI prints a line to **stderr** naming any
skipped file and what to add to it, and still exits 0 (FR-051).

**Rationale.** FR-049 and FR-050 require an existing file be left byte-identical. `O_EXCL` is the
same primitive `create_document` already uses for collision handling (`documents.py:75`), so the
guarantee is enforced by the operating system rather than by a check-then-write that can race.

This also closes a live hole rather than only adding one: `workspace.py:52` currently does
`(target / "AGENTS.md").write_text(template)` unconditionally. The `.endpaper` guard prevents
*re-init*, but initialising a workspace inside a directory that already has its own `AGENTS.md`
destroys it today.

**Alternatives considered.**

- *`if not path.exists(): write`.* Rejected: a TOCTOU race, and needless when `O_EXCL` says the same
  thing atomically.
- *Append a pointer line to an existing `CLAUDE.md`.* Rejected by the spec's Assumptions — it means
  parsing and rewriting a file endpaper does not own. Report and leave alone.
- *Fail init when a guidance file exists.* Rejected: initialising a vault inside an existing
  repository is the common case, not an error (FR-051).

---

## R9: What goes in `CLAUDE.md`

**Decision.** A pointer of no more than 12 lines that states this directory is an endpaper workspace,
tells the reader to read `AGENTS.md` before creating or changing anything, and says the one thing that
is genuinely non-obvious: **create through the commands, modify the markdown directly.** It restates
no layout, no schema, no command syntax.

SC-013 is enforced mechanically by `tests/contract/test_guidance_files.py`: `CLAUDE.md` must be ≤ 12
lines, must contain the literal `AGENTS.md`, and must **not** contain any of `meetings/`, `notes/`,
`tasks.md`, `frontmatter`, `endpaper meeting`, `endpaper note`, or `endpaper task`. Any of those
appearing means a convention has been duplicated and now has two places to drift.

**Rationale.** §4.3's line budget exists because bloated context files measurably raise exploration
cost. A second file that repeats the first doubles the maintenance and guarantees that one of them
goes stale, after which an assistant reads whichever it found first and gets the wrong answer.

**Alternatives considered.**

- *Copy `AGENTS.md`'s content into `CLAUDE.md`.* Rejected: two sources of truth for one set of
  conventions, and no mechanism to keep them in step.
- *Make `CLAUDE.md` a symlink to `AGENTS.md`.* Rejected: symlinks are unreliable on Windows without
  developer mode or admin rights, and OneDrive does not sync them predictably.
- *Write convention files for every assistant.* Rejected by the spec's Out of Scope — one observed
  failure, one file.

---

## R10: What this feature deliberately does not touch

**Decision.** The edit path addresses a document by the `Path` the scan already produced. It adds no
knowledge of where documents live.

**Rationale.** `scan_documents` currently globs one directory level (`documents.py:154`) and
`create_document` writes into the collection root, so the `YYYY/MM/` partitioning that
REQUIREMENTS.md §4.6 mandates is not implemented anywhere yet. Building editing against paths rather
than against a layout means the partition work, when it lands, changes nothing here. Recorded as a
follow-up in [plan.md](./plan.md#follow-ups-outside-this-plan), not fixed in passing.
