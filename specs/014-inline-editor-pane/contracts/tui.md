# TUI Contract: Inline Edit Mode

**Feature**: `014-inline-editor-pane` | **Date**: 2026-08-01

The TUI is choom's second interface, so its observable behaviour is a contract in the same sense the
CLI's `--json` schema is. This document states what inline edit mode guarantees. Anything not stated
here is unchanged from `004-viewing-editing`'s contract.

## C1 — Where an editor opens

| Entered from | Presentation |
|---|---|
| `e` on a highlighted document in the list | Inline, in `#preview-pane` |
| `e` on a highlighted task in the list | Inline, in `#preview-pane` |
| `/note`, `/meeting` create from the list | Inline, in `#preview-pane` |
| `/daily` from the list | Inline, in `#preview-pane` |
| A link in the preview that resolves to a task | Inline, in `#preview-pane` |
| `e` inside the full-screen reading view | Full-screen, as today |

The rule behind the table: an editor opened while the list screen is the active screen renders in the
pane; an editor opened from any other screen pushes a full-screen editor.

## C2 — What stays on screen

While an inline editor is open, all of the following remain mounted and visible: the collection bar, the
scope pane, the list header, and the list rows. The record that was highlighted when the editor opened
is still the highlighted record when it closes.

Hidden for the duration: `#preview` and `#preview-links-section`.

## C3 — Keys

| Key | While an inline editor is open |
|---|---|
| `ctrl+o` | Save |
| `ctrl+s` | Save (alias) |
| `ctrl+x` | Save and close |
| `escape` | Discard — confirmation first if dirty |
| `ctrl+c` | Cancel, and only while an `/ai` request is in flight; otherwise `TextArea`'s copy |
| `ctrl+q` | Quit — confirmation first if the buffer is dirty |
| `tab`, `shift+tab` | Nothing. Focus does not leave the editor and the collection does not change |
| `j`, `k`, `e`, `b`, `space`, `/`, any printable key | Inserted into the buffer |
| `ctrl+d` | Deletes a character in the buffer; never deletes a record |
| `enter` | Newline, or runs an in-editor command (`/ai`, `/link`, `/task`) as today |

No list action runs while an inline editor is open. This holds whether the key reaches the list by
binding or by focus.

## C4 — The bottom bar

- The status bar shows `EDIT_HELP` for the duration, replacing the list's help text.
- The status bar carries the editor's own messages (save failures, `/ai` outcomes, capture notes) in the
  same form and position they take full-screen.
- The command bar cannot be opened. `/` types a slash.
- On close, the status bar returns to the list's own text: collection indicator, list help, warning count
  if any.

## C5 — The list does not move

While an inline editor is open, the list does not re-render: no row is added, removed, reordered, or
re-selected, and the periodic refresh does not fire. On close, the list refreshes once — the same
refresh that follows a full-screen edit today — and the record that was being edited is selected.

## C6 — Wrapping

Content wraps at the pane's current edge. No horizontal scrolling is required to read any line, at any
terminal width the tool supports. A width change re-wraps in place: no character is added, lost, or
reordered, and the cursor stays on the character it was on.

## C7 — Dirty state is visible to the app, not just the screen

`ctrl+q` raises the unsaved-changes confirmation when *any* editor is dirty, inline or full-screen.
Toggling a task skips propagating that change into any document whose editor is open and dirty, inline
or full-screen.

## C8 — Unchanged by this feature

- `enter` on a highlighted document opens the full-screen reading view.
- `e` inside that view opens a full-screen editor, and leaving it returns there.
- What a save writes, for a document or a task body.
- Every CLI command, exit code, and `--json` schema.
