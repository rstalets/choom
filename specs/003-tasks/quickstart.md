# Quickstart: validating 003-tasks

How to prove this feature works, by hand, once it is built. Scenario numbers map to the user stories
in [spec.md](./spec.md). Details of the line format live in [data-model.md](./data-model.md); command
shapes live in [contracts/cli.md](./contracts/cli.md).

## Prerequisites

The development environment from [001's quickstart](../001-meeting-notes/quickstart.md) — `uv sync`,
an editable install, and a workspace created with `endpaper init`. No new tooling.

```bash
uv sync --extra dev
uv run ruff format --check . && uv run ruff check . && uv run mypy src && uv run pytest
```

Work in a scratch workspace so nothing here touches real notes:

```bash
mkdir -p /tmp/ep-tasks && cd /tmp/ep-tasks && endpaper init
```

---

## Scenario 1 — capture a task (spec US1)

```bash
endpaper task add "send the vendor comparison" --type followup --tag procurement
cat tasks.md
```

Expect the identifier on stdout, and one line in `tasks.md`:

```markdown
- [ ] send the vendor comparison <!-- id:t_a1b2 type:followup tags:procurement created:2026-07-28 -->
```

Check the three things that are easy to get wrong:

```bash
endpaper task add "quoted #inline tag works"     # tag parsed out, text is "quoted tag works"
endpaper task add "   "                          # exit 2, tasks.md unchanged
rm tasks.md && endpaper task add "recreates the file" && cat tasks.md
```

Then confirm the file is still ordinary markdown: open `tasks.md` in any markdown previewer and
confirm it renders as a checklist with **no visible metadata** (SC-004).

---

## Scenario 2 — list and complete (spec US2)

```bash
endpaper task add "book the room"
endpaper task list                       # open only, oldest first
endpaper task done t_a1b2                # silent, exit 0
endpaper task list                       # the completed one is gone
endpaper task list --all                 # it is back, marked done
endpaper task undone t_a1b2              # reversed
```

Error paths, checking exit codes as well as messages:

```bash
endpaper task done t_zzzz; echo $?       # 1, message on stderr
endpaper task list --json | python -c "import json,sys; print(sorted(json.load(sys.stdin)[0]))"
# -> ['created', 'done', 'id', 'line', 'tags', 'text', 'type']
```

Duplicate identifiers — paste a task line twice in `tasks.md`, then:

```bash
endpaper task done t_a1b2; echo $?       # 2, message naming both line numbers, file unchanged
```

---

## Scenario 3 — hand-edit and lose nothing (spec US3)

This is the scenario worth doing slowly. Build a deliberately awkward `tasks.md`:

```markdown
# My tasks

Some prose endpaper has never seen.

- [ ] buy milk
- [ ] thing <!-- id:
- [x] already done <!-- id:t_9f0e created:2026-07-27 -->
- [ ] fix the <!-- hack --> path
  - [ ] an indented subtask
* [ ] a star bullet
```

Snapshot it, then list:

```bash
cp tasks.md /tmp/before.md
endpaper task list --all
diff /tmp/before.md tasks.md
```

Expect:

- `buy milk`, the indented subtask, and the star bullet all listed, each having gained
  `<!-- id:t_xxxx -->` **and nothing else** — no invented `created` date.
- `fix the <!-- hack --> path` listed with its text intact, its own comment untouched, and a new
  metadata comment appended after it.
- `- [ ] thing <!-- id:` absent from the list, byte-identical in the diff, and reported as a warning
  on stderr.
- The heading, the prose, and every blank line unchanged.

Line endings and the final newline:

```bash
printf -- '- [ ] alpha <!-- id:t_1111 -->\r\n- [ ] beta <!-- id:t_2222 -->' > tasks.md   # CRLF, no final newline
endpaper task done t_1111
xxd tasks.md | tail -2      # still CRLF; still no trailing newline
```

Then confirm append behaves as the plan specifies — the previously-final line gains its terminator:

```bash
endpaper task add "gamma" && xxd tasks.md | tail -2
```

Read-only degradation (FR-038):

```bash
chmod a-w tasks.md
endpaper task list --json   # still lists; bare tasks show "id": null; warning on stderr; exit 0
endpaper task done t_1111   # exit 3, file unchanged
chmod u+w tasks.md
```

---

## Scenario 4 — the AI-facing contract (spec US4)

```bash
endpaper task list --json < /dev/null > out.json 2> err.txt; echo $?
python -c "import json; json.load(open('out.json'))"     # parses
grep -c $'\x1b' out.json                                  # 0 — no ANSI
cat err.txt                                               # warnings only, never data
grep -A5 'tasks.md' AGENTS.md                             # task line format documented
wc -l AGENTS.md                                           # <= 60
```

Every command must return without reading stdin — run each with stdin closed and confirm none hangs.

---

## Scenario 5 — the terminal interface (spec US2 scenarios 3–4)

```bash
endpaper          # opens on the meetings collection
```

- The menu pane lists three collections: Meetings, Notes, **Tasks**. Reach tasks either way —
  `h` to the menu then `j`/`k` to Tasks, or `/` then `tasks`.
- `↑`/`↓`/`j`/`k` move in the list; `h`/`l` cross panes; the footer lists every active binding and
  shows `[tasks]`.
- **The preview pane is empty and still there.** Confirm it does not collapse and the list pane does
  not change width as you move between Meetings and Tasks (FR-044b).
- `space` on a row flips its checkbox; check `tasks.md` in another shell within a second (SC-002) and
  confirm the metadata comment is untouched.
- `a` reveals completed tasks, struck through; `a` again hides them. Cross to Notes and back — the
  `a` state survives.
- On the Meetings and Notes collections, `space` and `a` do nothing, raise nothing, and are absent
  from the footer.
- `/` then `task.followup call the vendor #procurement` → switches to Tasks with the new task
  selected, not in a preview.
- `/` then `meetings` returns to the meetings collection, and the preview repopulates.

---

## Performance (SC-007)

```bash
python -c "
from pathlib import Path
Path('tasks.md').write_text(''.join(
    f'- [ ] task number {i} <!-- id:t_{i:04x} created:2026-07-{(i%28)+1:02d} -->\n'
    for i in range(1000)))
"
time endpaper task list --all > /dev/null      # < 1s
```

The TUI's task list must open and respond to navigation on the same file with no perceptible delay.

---

## Cross-platform (SC-003, Windows first-class)

Run scenarios 1–3 on Windows Terminal, and the CRLF checks in particular — `tasks.md` is the first
file endpaper rewrites, so line-ending preservation is a correctness property, not a nicety. Also run
the suite from a workspace whose path contains a space and a non-ASCII character.
