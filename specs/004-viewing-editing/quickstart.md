# Quickstart: Validating Viewing and Editing

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

How to prove this feature works. Every acceptance scenario in the spec maps to a check below. This is
a validation guide, not an implementation guide — the code belongs in `tasks.md`.

## Prerequisites

```bash
uv sync --extra dev
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest
```

All four must pass before this feature is considered done (Principle VI, and the repo's existing
gates).

---

## 1. The core save path, with no terminal

The whole of FR-016 through FR-023 is testable without an event loop. Start here — if this is wrong,
nothing above it can be right.

```bash
uv run pytest tests/unit/test_stamp_updated.py tests/unit/test_line_endings.py -v
```

**The stamp table** — build each input as a string, call `stamp_updated`, assert on the output. The
full matrix is in [data-model.md](./data-model.md#stamp_updated--the-matching-rules). The cases that
matter most:

| Input | Expect |
|---|---|
| Normal six-field block | only the `updated:` line differs; `created:` byte-identical |
| A seventh, user-added field | preserved; still stamped |
| Fields hand-reordered | order preserved; still stamped |
| No frontmatter | `(text, False)` — unchanged text |
| Unterminated block | `(text, False)` |
| Block with no `updated:` line | `(text, False)` |
| `updated:` in the body, below the block | untouched |
| `""` | `("", False)`, no exception |

The sharpest single assertion: **diff the before and after text and confirm exactly one line changed.**

**Line endings** — round-trip a CRLF file and an LF file, each with and without a trailing newline,
through `load_for_edit` → `save_buffer` with the text unchanged. The bytes on disk must be identical
to what went in, apart from the `updated:` line.

---

## 2. Edit and save (US1)

```bash
uv run pytest tests/integration/test_edit_save_tui.py -v
```

Headless through `Pilot`, matching the existing `tests/integration/test_list_tui.py` pattern:

```
create a meeting → run_test() → press "enter" → press "e"
  → assert isinstance(app.screen, EditScreen)
  → assert the TextArea text starts with "---"        # frontmatter is in the buffer (FR-009)
  → type → press "ctrl+o"
  → assert path.read_text() == buffer, apart from `updated`
  → press "ctrl+s" → assert identical behaviour
  → press "ctrl+x" → assert isinstance(app.screen, PreviewScreen) and it shows the new text
```

| Scenario | Check |
|---|---|
| US1-1 | `e` opens the raw markdown including frontmatter |
| US1-2 | `ctrl+o` writes; cursor position survives |
| US1-3 | `ctrl+s` is indistinguishable from `ctrl+o` |
| US1-4 | `ctrl+x` saves and lands in preview showing the new content |
| US1-5 | a title change in the buffer shows in the list row on return; no other row moves |
| US1-6 | `updated` advances, `created` does not |
| US1-7 | `esc` from preview without editing leaves bytes **and mtime** untouched |

---

## 3. Discard (US2)

```bash
uv run pytest tests/integration/test_discard_tui.py -v
```

The dirty rule is the thing under test. Four entries to the edit state, four different `esc`
outcomes:

| Path | Expect |
|---|---|
| type, then `esc` | `DiscardDialog` appears; nothing written |
| ...then Cancel | back in `EditScreen`, buffer and cursor intact |
| ...then Discard | back in preview; **file byte-identical to before editing** |
| enter, change nothing, `esc` | no dialog |
| type, `ctrl+o`, then `esc` | **no dialog** — the save cleared the baseline |
| type, then retype the original text, then `esc` | **no dialog** — this is the one an "edited" flag gets wrong |

The last row is the reason dirty state is a comparison and not a boolean
([R3](./research.md#r3-dirty-state-is-a-comparison-not-a-flag)).

---

## 4. Presentation (US3)

```bash
uv run pytest tests/integration/test_edit_presentation.py -v
```

```python
editor = app.screen.query_one("#editor", TextArea)
assert editor.show_line_numbers is True     # FR-010
assert editor.soft_wrap is True             # FR-011
assert editor.tab_behavior == "focus"       # FR-012 -- tab must not insert a tab
```

Then, with a document whose first line is `---` and which contains a paragraph far wider than the
pane:

- line 1 in the gutter is the opening `---` (FR-010)
- the pane never scrolls horizontally (FR-011)
- pressing `tab` leaves `editor.text` unchanged (FR-012)

**Footer/binding agreement** — assert mechanically, not by eye: every `EditScreen` binding with
`show=True` appears in `EDIT_HELP`, and `EDIT_HELP` names no key the screen does not bind (FR-030,
FR-031). Same check for `PREVIEW_HELP`, which now must include `e` (FR-032).

---

## 5. Guidance files (US4)

```bash
uv run pytest tests/integration/test_init_guidance.py tests/contract/test_guidance_files.py -v
```

```bash
# by hand, the case that matters most
mkdir /tmp/repo && cd /tmp/repo
printf 'my own project instructions\n' > CLAUDE.md
uv run endpaper init
cat CLAUDE.md          # unchanged -- still one line
echo $?                # 0
```

| Scenario | Check |
|---|---|
| US4-1 | `CLAUDE.md` created in an empty directory, and it names `AGENTS.md` |
| US4-2 | pre-existing `CLAUDE.md` byte-identical; exit 0; notice on **stderr** |
| US4-3 | pre-existing `AGENTS.md` byte-identical; exit 0 — closes the current clobber |
| US4-4 | `CLAUDE.md` ≤ 12 lines and contains none of `meetings/`, `notes/`, `tasks.md`, `frontmatter`, `endpaper meeting`, `endpaper note`, `endpaper task` (SC-013) |
| US4-5 | judgement, not automated — see below |

**US4-5 / SC-011 is a trial, not an assertion.** Point a fresh assistant session at a newly
initialised workspace, ask it to record a meeting, and observe whether it runs `endpaper meeting new`
or hand-writes a file into `meetings/`. Record the result in the PR. One trial is weak evidence; the
point is to notice a regression to hand-writing, which is what this story exists to prevent.

---

## 6. Hardening

```bash
uv run pytest tests/integration/test_save_failure.py tests/integration/test_external_edits.py -v
```

| Case | Expect | Requirement |
|---|---|---|
| Save to a read-only file | error shown; **still in edit; buffer intact**; file unchanged | FR-020, SC-011 |
| Write fails mid-way (inject an `OSError` at `os.replace`) | file byte-identical, never truncated; temp file cleaned up | FR-020 |
| Document rewritten externally, then edited | opens, edits, saves normally; stale `updated` left as found until this save | FR-041, SC-010 |
| Frontmatter deleted in the buffer, then saved | bytes written as typed; **warning shown**; file not repaired; drops out of the list on rescan with a warning, never rewritten | FR-018, FR-050 |
| Buffer emptied and saved | file becomes empty; no crash | Edge Cases |
| Non-ASCII, emoji, RTL text | written back intact; gutter still numbers real lines | FR-013 |
| Terminal resized while editing | buffer, cursor, and dirty state survive | Edge Cases |

---

## Cross-platform

Per Principle V and REQUIREMENTS.md §4.5, before release verify on **Windows Terminal, iTerm2, macOS
Terminal, PuTTY, and inside tmux**:

- `ctrl+o` saves in all five.
- `ctrl+s` saves where flow control permits; where it does not, `ctrl+o` still works and the footer
  never promised `ctrl+s` (FR-015, FR-035).
- `ctrl+q` still quits and `ctrl+c` still interrupts from all three states (FR-033).
- A CRLF file edited on Windows is still CRLF afterwards (FR-019, SC-007).

Document `stty -ixon` as the fallback for a terminal that swallows `ctrl+s` (FR-035).

---

## Definition of done

- [ ] `ruff`, `mypy --strict`, and `pytest` all clean
- [ ] Every acceptance scenario above has a test, per Principle VI
- [ ] CHANGELOG records 0.0.3: the new bindings, `CLAUDE.md` at init, and the **breaking**
      `init_workspace` return-type change
- [ ] Constitution Check in [plan.md](./plan.md#constitution-check) re-confirmed against the built code
- [ ] Cross-platform matrix above walked on at least Windows Terminal and one Unix terminal
