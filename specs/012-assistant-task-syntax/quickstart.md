# Quickstart: Validating Linked Task Syntax for AI Assistant

**Feature**: 012-assistant-task-syntax | **Date**: 2026-08-01

How to prove each story works, by hand and by test. Shapes and rules are in
[data-model.md](./data-model.md) and [contracts/reply-capture.md](./contracts/reply-capture.md) — not
repeated here.

## Prerequisites

- A working tree with the feature branch checked out and `uv sync` run.
- For the by-hand paths: one of the supported assistant CLIs installed (`claude` or `copilot`) and
  reachable on `PATH`, or `choom config assistant <name>` set explicitly.
- A scratch workspace, so nothing lands in your real notes:

```bash
uv run choom init /tmp/choom-012 && cd /tmp/choom-012
uv run choom meeting add "Q3 renewal" --type standup
uv run choom
```

Open the meeting with `e`, type a few lines of notes, and use `/ai` from inside the editor.

## Run the tests

```bash
scripts/dev-tests.sh                                        # everything
scripts/dev-tests.sh tests/unit/test_reply_lines.py         # eligibility and fences
scripts/dev-tests.sh tests/unit/test_capture_reply_tasks.py # the walk, ordering, partial failure
scripts/dev-tests.sh tests/unit/test_compose_prompt.py      # the prompt clause
scripts/dev-tests.sh tests/integration/test_ai_command_tui.py  # the three end-to-end paths
```

`scripts/dev-tests.sh` is the entry point per the repo's `CLAUDE.md` — it runs the suite in parallel and
takes pytest arguments straight through.

No test in this feature reads the wall clock, and none needs an assistant installed — the integration
paths use the `stub_assistant` fixture, a real executable on a temporary `PATH` whose reply is chosen by
`CHOOM_STUB_MODE`.

---

## US1 — Ask for my commitments and get real tasks

**By hand**: in the editor, on its own line, type

```text
/ai summarise what I committed to above and capture each one as a followup
```

Expect: the `⋯` placeholder while it works, then a reply where each commitment the assistant wrote as a
task line has become `- [ ] [<description>](../../../tasks.md#task_xxxx)`, the surrounding prose is
unchanged, the status bar reads `N tasks captured` with no `⚠`, and the editor has not moved. Then:

```bash
uv run choom task list --json | head -40      # the tasks exist, with tags, type, and a link back
```

**By test**: `test_ai_command_tui.py`, the `reply_with_tasks` stub mode — asserts the mirrors are in the
buffer, the prose survived in order, the tasks are in `tasks.md` with the right description, type, and
tags, and the status line carries the count.

## US2 — The same instruction for every assistant

**By hand**: not observable without reading a prompt. Verify by test.

**By test**: `test_compose_prompt.py` — the clause is present with `task_capture=True`, absent with
`False`, and identical across every profile in `PROFILES`, asserted by composing once per profile and
comparing.

## US3 — Nothing is captured by surprise

**By hand**: ask a question that makes the assistant explain the syntax:

```text
/ai how do I capture a task from inside this note? show me an example
```

Expect: the explanation lands as text, any fenced example is inserted verbatim, no task is created, and
the status bar shows no capture count. Confirm with `uv run choom task list` — unchanged.

**By test**: `test_reply_lines.py` carries the rules (fenced, indented, inline, other verbs, unclosed
fence, tilde fences); `test_ai_command_tui.py`'s `reply_explaining` mode proves the wiring agrees, and the
existing `test_reply_containing_a_slash_ai_line_is_inserted_as_literal_text` still passes unchanged.

## US4 — The captured tasks behave like every other task

**By hand**: after US1, press `escape` to leave the editor, `tab` to the tasks collection, highlight one
of the new tasks, and press `space`. Reopen the meeting: the checklist item is ticked. Tick a different
one in the note and save (`ctrl+o`): `uv run choom task list --all` shows it done. Highlight a task and
check the preview pane names the meeting it came from.

**By test**: covered by 009's existing mirror suite — this feature adds no mirror behaviour. The US1
integration test asserts the created task carries the source link, which is the only part specific to
here.

## US5 — A failed capture never costs the reply

**By hand**, on macOS or Linux:

```bash
chmod 444 /tmp/choom-012/tasks.md      # then run an /ai request that emits task lines
chmod 644 /tmp/choom-012/tasks.md      # restore afterwards
```

Expect: the whole reply in the buffer, the task lines present as the assistant wrote them, and a status
line naming the failure with `⚠`. Nothing is truncated.

**By test**: `test_ai_command_tui.py` makes `tasks.md` unwritable and asserts every reply line reached the
buffer; `test_capture_reply_tasks.py` covers one failure among several, all failing, and the empty
description case at the unit layer where the branches live.

---

## What "done" looks like

- `scripts/dev-tests.sh` green on 3.11 and 3.13, including format, lint, and type checks.
- A reply with no task lines produces exactly the document text it produced before this feature — the
  clearest single check that nothing regressed.
- `README.md`'s `/ai` bullet and inline task capture bullet describe the new behaviour.
