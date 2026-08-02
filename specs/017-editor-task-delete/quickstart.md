# Quickstart: Delete a Task From the Line It Lives On

**Feature**: `017-editor-task-delete` | **Plan**: [plan.md](./plan.md)

How to prove the feature works, by hand and by suite. Details live in
[contracts/core-api.md](./contracts/core-api.md) and [contracts/tui.md](./contracts/tui.md); this is the
run guide.

---

## Prerequisites

```bash
uv sync
```

A scratch workspace, so nothing real is at risk:

```bash
cd "$(mktemp -d)"
uv run choom init
uv run choom meeting new "Q3 planning" --type standup
```

---

## The suite

```bash
scripts/dev-tests.sh                                   # everything
scripts/dev-tests.sh tests/unit/test_mirror_deletion.py
scripts/dev-tests.sh tests/integration/test_editor_task_delete_tui.py
```

Regression surfaces this feature touches, worth running together:

```bash
scripts/dev-tests.sh \
  tests/unit/test_mirror_recognition.py \
  tests/unit/test_footer_bindings.py \
  tests/integration/test_delete_mirrors.py \
  tests/integration/test_inline_capture.py \
  tests/integration/test_edit_save_tui.py
```

`test_delete_mirrors.py` is the one to watch: it pins the *existing* behaviour that deleting a task
leaves mirroring documents byte-identical. This feature must not change it — that asymmetry is
deliberate (spec.md §"Interface parity").

---

## Manual walkthrough

Launch the TUI with no arguments:

```bash
uv run choom
```

### 1. The happy path (US1, US2)

1. Move to the Meetings collection, highlight *Q3 planning*, press `e`.
2. Type `/task call Terry` and press Enter. The line becomes a checklist item.
3. Confirm the footer now reads `… ctrl+t delete task …`.
4. Put the cursor on that line and press `ctrl+t`.
5. **Expect**: a dialog quoting `call Terry`, saying it goes from both places and that the document is
   saved.
6. Press Enter.
7. **Expect**: the line is gone, the status reads `deleted "call Terry"`, and the Tasks collection no
   longer lists it.

Verify on disk, from the workspace root:

```bash
grep -c "call Terry" tasks.md          # 0
grep -rc "call Terry" meetings/        # 0
```

### 2. Cancel is a complete no-op (SC-005)

Capture another task, type an unrelated half-sentence somewhere else in the buffer, then `ctrl+t` on the
task line and press **Esc**.

**Expect**: no change to either file — including no save of the half-sentence — and the buffer still
marked unsaved. This is the property that makes the dialog's "the document is saved" clause safe to
state.

### 3. No dialog off a task line (US3, SC-003)

Press `ctrl+t` with the cursor on prose, on a heading, on a blank line, on `- [ ] buy milk` (a checklist
item with no link), and on a task line pasted inside a ``` fence.

**Expect**: every time, no dialog, no write, and the status note `no task on this line`.

### 4. The task is already gone (US4)

Capture a task, note its id from the link, leave the editor, delete it from the Tasks collection with
`ctrl+d`, then reopen the meeting and press `ctrl+t` on the stale line.

**Expect**: the dialog says the task is no longer in the task list and only the line will go. On confirm,
the line goes and `tasks.md` is byte-identical:

```bash
md5sum tasks.md   # before and after — same
```

### 5. An unreadable task list refuses (US5)

Break one metadata comment by hand — turn a `<!-- id:task_… -->` into `<!-- id:task_…` — then press
`ctrl+t` on a task line whose id does not resolve.

**Expect**: no dialog, nothing written to either file, and a message naming the line number and telling
you to fix it.

Then press `ctrl+t` on a task line whose id *does* resolve. **Expect**: it deletes normally. One broken
line never blocks the rest of the file (FR-022).

### 6. Undo (research R2)

Delete a task line, then press the editor's undo.

**Expect**: the line comes back in the buffer; the task stays deleted; saving reports the restored line
as pointing at a task that no longer exists. This is the decided behaviour, not an accident.

### 7. Nothing else moves (SC-001, SC-002)

Build a document with a task line that has a blank line above it, a blank line below it, an indented note
beneath it, and trailing prose on the line itself. Snapshot, delete, diff:

```bash
cp meetings/2026/08/*.md /tmp/before.md
# ...delete the task line in the TUI...
diff /tmp/before.md meetings/2026/08/*.md
```

**Expect**: exactly two hunks — the removed line, and the `updated:` frontmatter stamp. Both blank lines
survive. The indented note survives. Nothing is reindented or reflowed.

Repeat with a CRLF file (`unix2dos` the note first) and confirm the file is still CRLF afterwards.

### 8. Both hosts (FR-001)

Repeat step 1 twice — once with the editor opened inline from the list (`e` on a highlighted row) and
once full-screen. The behaviour must be identical; `EditorPane` is the same widget in both.

---

## Verifying the layering claim (Principle I)

The whole of what-gets-removed is decidable without a terminal:

```bash
uv run python -c "
from pathlib import Path
from choom.core.mirrors import plan_mirror_deletion
from choom.core.workspace import find_workspace

ws = find_workspace(Path('.'))
text = Path('meetings/2026/08/some-note.md').read_text()
plan = plan_mirror_deletion(ws, text, LINE, source=Path('meetings/2026/08/some-note.md'))
print(plan.outcome, plan.span, plan.extra_text)
assert plan.text == text[:plan.span[0]] + text[plan.span[1]:]
"
```

That assertion is the same one the unit tests and the TUI integration test both make. If it holds in all
three, core and the adapter cannot have drifted apart about what a deletion means.
