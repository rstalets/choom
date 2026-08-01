# Quickstart: validating Inline Task Capture

**Feature**: `009-inline-task-capture`

Runnable checks that prove the feature works end to end. Each scenario names the user story it covers and
what specifically would be wrong if it failed. Details of formats and outcomes live in
[contracts/](contracts/) and [data-model.md](data-model.md); this is the run guide.

---

## Prerequisites

- `008-document-links` merged. Without it there is no `links` field, no `find_links`, and no
  `relative_destination`, and nothing here runs.
- Python 3.11+, `uv sync`.
- A throwaway workspace:

```bash
mkdir -p /tmp/ep-009 && cd /tmp/ep-009
uv run endpaper init
uv run endpaper meeting create "Q3 planning"     # note the id it prints
```

---

## Automated

```bash
uv run pytest                                    # everything
uv run pytest tests/unit/test_mirror_recognition.py tests/unit/test_mirror_reconcile.py
uv run pytest tests/integration -k mirror
uv run pytest tests/contract -k task_link
uv run pytest tests/performance/test_reconcile_open.py
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

The performance test asserts two things, and the second is the one that catches a regression a fast machine
would hide: reconcile-on-open stays under 50 ms on a synthetic multi-year workspace (SC-008), **and** a
document with no mirrors triggers no read of `tasks.md` at all (SC-007).

---

## Manual — capture (US1, US2)

```bash
uv run endpaper            # TUI; open the Q3 planning meeting for editing
```

1. On a blank line type `/task.followup call Terry about the renewal #procurement`, press enter.

   **Expect**: the line becomes `- [ ] [call Terry about the renewal](../../../tasks.md#task_XXXX)`, the
   cursor sits at its end, focus stays in the editor, and nothing on screen moved. *If the screen jumped to
   the tasks collection, the editor path is reusing the command bar's handler.*

2. Check the task:

```bash
uv run endpaper task list --json | jq '.[-1]'
```

   **Expect**: `text` is `call Terry about the renewal` with the `#tag` extracted into `tags`, `type` is
   `followup`, and `links` names the meeting's id. *If `text` still contains `#procurement`, capture is not
   going through `add_task`.*

3. Undo (`ctrl+z`) in the editor.

   **Expect**: the mirror line disappears; `task list` still shows the task. *The mirror is a buffer edit,
   not a coupled write.*

4. Type a plain line `chase the security review with Priya`, go to its start, type `/task.followup ` in
   front of it, press enter.

   **Expect**: a second task whose description is the pre-existing text, and the line rewritten as a mirror.

5. Type a line that is only `/task` and press enter.

   **Expect**: `/task needs a description`, the line untouched, no task created.

6. Type `Did you know you can type /task here?` and press enter.

   **Expect**: an ordinary newline. Nothing created.

---

## Manual — provenance (US3)

```bash
uv run endpaper links <meeting-id> --direction in --json
```

**Expect**: the captured tasks listed as inbound links. *This is 008's scan finding a link this feature
wrote; if it is empty, the `links` field is not being populated.*

Open the task in the TUI preview: the originating meeting is named, and the open key reaches it.

---

## Manual — completion, both directions (US4, US5)

**From the tasks list:**

1. Switch to Tasks, select `call Terry about the renewal`, press `space`.
2. Open the meeting note.

   **Expect**: its mirror now reads `- [x]`. **And** the meeting's `updated` frontmatter is unchanged —
   check it before and after. *A changed `updated` means the sync path is going through `save_buffer`
   instead of the non-stamping writer, and every recency-sorted list will now reorder on unrelated
   toggles.*

**From the document:**

3. In the meeting note, change that mirror's `[x]` back to `[ ]` and save (`ctrl+o`).
4. `uv run endpaper task list --json | jq '.[] | select(.id=="task_XXXX") | .done'`

   **Expect**: `false`.

**Reword and move, then toggle again:**

5. Edit the mirror's link text to `ring Terry` and indent it under a bullet. Save.
6. Toggle the task from the tasks list.

   **Expect**: the reworded, indented line's checkbox flips. *Anything else means the mirror is being
   located by text or by line number rather than by id (FR-015).*

---

## Manual — the backstop (US6)

**Hand-edit outside the app:**

```bash
# with the TUI closed
sed -i '' 's/^- \[ \] call Terry/- [x] call Terry/' tasks.md   # macOS
uv run endpaper                                                 # open the meeting note
```

**Expect**: the mirror reads `- [x]` on open, with no prompt and no repair command.

**Copy-paste a mirror into a second note:**

```bash
uv run endpaper note create "scratch"
```

Paste the mirror line into the scratch note and save. Toggle the task from the tasks list — the scratch
note is *not* updated at that moment, because the task does not link to it. Now open the scratch note.

**Expect**: its checkbox is now correct. *This is the design: propagation follows the task's links, and
reconcile-on-open catches everything else (research R3).*

**Nothing to do means nothing written:**

```bash
ls -l --time-style=full-iso meetings/2026/*/*.md   # note mtime
# open the meeting in the TUI, change nothing, close
```

**Expect**: mtime unchanged. *A document that needed no correction must not be opened for writing (FR-030).*

---

## Manual — conflict reporting (FR-024, FR-025)

1. Open the meeting note in the editor and tick its mirror, but **do not save**.
2. In another terminal: `uv run endpaper task done task_XXXX`.
3. Back in the editor, save.

**Expect**: the save wins, `tasks.md` holds the ticked state, and a warning in the status bar names the
task. *A silent resolution here is the failure this design exists to prevent.*

Then: paste a second copy of the mirror into the same document, set the two to different states, and save.

**Expect**: `tasks.md` unchanged for that task, and a warning naming it. *No arbitrary winner between two
of the user's own edits.*

---

## Manual — CLI parity (US7)

```bash
uv run endpaper task add "review the SOW" --type followup --link <meeting-id> --json
uv run endpaper task add "bad link" --link meeting_20260101_deadbeef; echo "exit=$?"
uv run endpaper task done task_XXXX --json
```

**Expect**, in order: a JSON object whose `links` names the meeting; then exit **1** with the id named on
stderr and no task created (`task list` unchanged); then a JSON object listing `documents_updated`.

**Stream separation** — make a linked document read-only, then:

```bash
chmod a-w meetings/2026/07/*.md
uv run endpaper task undone task_XXXX --json > out.json 2> err.txt; echo "exit=$?"
chmod u+w meetings/2026/07/*.md
```

**Expect**: exit **0**, `out.json` parses cleanly with the warning in its `warnings` array, and `err.txt`
carries the human-readable warning. *A non-zero exit here would make an assistant retry a completion that
already succeeded (research R11).*

---

## Cleanup

```bash
cd / && rm -rf /tmp/ep-009
```
