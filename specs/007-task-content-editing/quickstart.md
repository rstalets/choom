# Quickstart: validating Task Content Editing

Runnable checks that prove the feature works end to end. Details of the format live in
[contracts/task-file-format.md](./contracts/task-file-format.md); the data model is in
[data-model.md](./data-model.md).

## Prerequisites

```bash
uv sync
uv run endpaper --version
```

Set up a scratch workspace:

```bash
mkdir -p /tmp/ep-007 && cd /tmp/ep-007
uv run endpaper init
uv run endpaper task add "call the vendor #procurement" --type followup
```

## 1. A hand-written body renders (User Story 1)

Append a body to `tasks.md` by hand — indented two spaces under the task line, with a blank line
between:

```markdown
- [ ] call the vendor <!-- id:t_… type:followup tags:procurement created:… -->

  Need the Q3 comparison before the renewal meeting.

  - 07-28 called, left voicemail
```

```bash
uv run endpaper
```

**Expect**: the task list opens on To-Do; highlighting the task shows its heading, metadata line, and
body in the right-hand pane. Moving to a task without a body clears the body — no stale content.

## 2. Editing round-trips (User Story 2)

With the task highlighted, press `e`, add a line, then `ctrl+x`.

**Expect**: the list returns with the same task highlighted and the new line in the pane; `tasks.md`
shows the new body with the checkbox line untouched.

Then the no-op check — the one that catches an over-eager writer:

```bash
cp tasks.md /tmp/ep-007-before.md
# in the TUI: highlight the task, press e, change nothing, press ctrl+x
diff tasks.md /tmp/ep-007-before.md && echo "byte-identical"
```

**Expect**: `byte-identical` (SC-003).

Emptying the body and saving leaves a lone checkbox line with no trailing blank or indented lines.

## 3. The CLI reads it (User Story 3)

```bash
uv run endpaper task list --json | python3 -m json.tool
uv run endpaper task show <id>
uv run endpaper task show <id> --json
uv run endpaper task show nope_1234; echo "exit=$?"
```

**Expect**: every listing entry carries `body`; `task show` prints the body; a missing id prints to
stderr and exits 1. Nothing prompts, and nothing opens an editor.

## 4. Nothing is lost

```bash
uv run endpaper task done <id>
uv run endpaper task show <id>
```

**Expect**: the body is unchanged after completing the task.

Then check the tolerance cases by hand-editing `tasks.md`: a tab-indented body, a body containing a
fenced code block, a nested `- [ ]` line (which becomes its own task and ends the body there), and
non-ASCII text. Re-open the TUI.

**Expect**: every task still lists, every line is still in the file, and warnings — not errors —
report anything malformed.

## 5. Renders elsewhere

Open `tasks.md` in any markdown viewer.

**Expect**: a checklist whose items carry their nested content (SC-008).

## Test suite

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

**Expect**: green. The new coverage lives in `tests/unit/` (span boundaries, dedent, the splice
writer), `tests/contract/` (`task show` exit codes and JSON schema), and `tests/integration/` (one
path per user story) — see `research.md` R6.
