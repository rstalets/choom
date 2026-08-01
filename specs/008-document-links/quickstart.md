# Quickstart: validating Document Links

**Feature**: `008-document-links` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

How to prove this feature works, by hand and in CI. Scenarios are ordered by the spec's story
priorities, so each block is runnable as soon as its story lands rather than only at the end.

---

## Prerequisites

```bash
uv sync --extra dev            # textual, PyYAML, pytest, ruff, mypy
uv run pytest -q               # baseline: 407 passing before this feature
```

Set up a scratch workspace for the manual scenarios:

```bash
mkdir -p /tmp/ep && cd /tmp/ep && uv run endpaper init
uv run endpaper meeting new "Q3 planning" --type standup --tag platform
uv run endpaper note new "vendor landscape" --type research
uv run endpaper task add "call Terry about the renewal" --type followup
```

---

## Scenario 1 — Ids name their collection (US1, SC-007)

```bash
head -2 meetings/*/*/*.md          # id: meeting_20260731_…
head -2 notes/*/*/*.md             # id: note_20260731_…
grep -o 'id:task_[a-f0-9]*' tasks.md
```

**Expect**: prefixes are `meeting_`, `note_`, `task_`.

Then prove FR-013 — old ids still resolve, nothing is migrated:

```bash
cp -r . /tmp/ep-old && cd /tmp/ep-old
sed -i '' 's/id: meeting_/id: m_/' meetings/*/*/*.md      # simulate a pre-change workspace
uv run endpaper meeting list --json | grep m_             # still listed
md5 -q tasks.md && uv run endpaper task list >/dev/null && md5 -q tasks.md
```

**Expect**: the meeting still lists under its old id, and `tasks.md` is byte-identical before and
after a read. No migration, no rewrite.

---

## Scenario 2 — A link resolves and repairs itself (US2, SC-001…SC-003, SC-005)

Write a link by hand with **no path at all**, the way a person actually would:

```bash
MEETING_ID=$(grep -h '^id:' meetings/*/*/*.md | cut -d' ' -f2)
printf '\nSee [Q3 planning](#%s) for context.\n' "$MEETING_ID" >> notes/*/*/*-research-*.md
uv run endpaper links "$MEETING_ID" --direction in --json
```

**Expect**: the note is listed as an inbound link immediately — before any save.

Now save the note (open it in the TUI, `e`, `ctrl+o`, `esc`, `ctrl+q`) and re-read it:

**Expect**: the link now reads
`[Q3 planning](../../../meetings/2026/07/…md#meeting_…)`, the link text is unchanged, and the
sentence around it is untouched.

Move the target and confirm the id still carries it:

```bash
mkdir -p meetings/2026/06 && mv meetings/2026/07/*.md meetings/2026/06/
uv run endpaper links "$MEETING_ID" --direction in    # still resolves — the id never changed
uv run endpaper links heal --dry-run --json           # reports the now-stale path
uv run endpaper links heal --json                     # rewrites it
```

**Expect**: `--dry-run` reports exactly what `heal` then changes, and writes nothing in between
(diff the workspace to confirm).

**Depth coverage (SC-005)** — repeat the link-and-save cycle from each of: a document under
`meetings/YYYY/MM/`, a daily note under `notes/daily/YYYY/MM/`, `tasks.md` at the root, and a
document placed by hand outside the dated layout (`notes/stray.md`). Each must produce a path that
resolves; the prefix ranges from nothing to `../../../../`.

**Code is not touched** — add this to a note and save it:

````markdown
```
[example](#meeting_deadbeef)
```
Inline: `[example](#meeting_deadbeef)`
````

**Expect**: both are byte-identical after the save. This is the case that would silently corrupt a
note explaining link syntax.

---

## Scenario 3 — Backlinks (US3, SC-006)

```bash
uv run endpaper links "$MEETING_ID" --json                     # both directions
uv run endpaper links "$MEETING_ID" --direction in --json
uv run endpaper links "$MEETING_ID" --direction out --json
NEW=$(uv run endpaper meeting new "nothing points here" | head -1)
uv run endpaper links "$(grep '^id:' "$NEW" | cut -d' ' -f2)" --direction in; echo "exit=$?"
```

**Expect**: an empty result exits **0**, not 1 — a record nothing points at is a normal record.

**Not a link** — paste the meeting's id into another note as plain prose, not inside a link.

**Expect**: it does not appear as an inbound link. Nor does the target's own frontmatter `id:` line.

**Nothing persisted**:

```bash
find . -name '*.json' -o -name '.endpaper/*links*'    # nothing beyond config.toml
```

---

## Scenario 4 — Audit and repair (US4, SC-004, SC-008)

```bash
rm meetings/2026/06/*.md                     # create a dead link
uv run endpaper links check --json; echo "exit=$?"
```

**Expect**: `status: "dead"`, `new_path: null`, exit **1**, and the report carries the file, line,
link text, and the unresolvable id — everything needed to choose a fix.

```bash
uv run endpaper links heal --json; echo "exit=$?"
```

**Expect**: the dead link is byte-identical afterwards, exit **1** because it remains unresolved.

**No gratuitous writes (SC-008)** — on a workspace with nothing stale:

```bash
find . -name '*.md' -newer /tmp/marker      # after: touch /tmp/marker; endpaper links heal
```

**Expect**: no file listed. A repair pass with nothing to repair writes nothing and moves no
`updated` timestamp.

---

## Scenario 5 — Task links (US5, SC-010)

```bash
sed -i '' "s|type:followup|type:followup links:$MEETING_ID|" tasks.md
uv run endpaper task list --json                       # the task still lists, now with links
uv run endpaper links "$MEETING_ID" --direction in     # the task is listed
```

**Expect**: the task appears in both. Note this also demonstrates the trap being fixed — before this
feature, that hand-edit would have made the task vanish from every listing.

**No migration (FR-016)**: on a `tasks.md` with no `links:` anywhere, run `task list`, `task done`,
and `task undone`, and confirm every untouched line is byte-identical.

**Still CommonMark (SC-010)**: render `tasks.md` in any markdown viewer — it is a checklist, and the
metadata comment is invisible.

---

## Scenario 6 — `/link` in the editor (US6, SC-009)

In the TUI, open a note, press `e`, and type `/link q3 planning` on its own line, then `enter`.

| Input | Expect |
|---|---|
| Terms matching exactly one record | Line becomes a correct markdown link |
| Terms matching nothing | Line left exactly as typed; status bar names the failure |
| Terms matching several | Line left exactly as typed; status bar names candidates |
| `note: /link foo` (not the whole line) | Ordinary text; nothing happens |

**Expect in every case**: still in the document. No dialog, no picker, no state change.

---

## Scenario 7 — The preview Links section (US7)

Open a document in preview and press `l`.

**Expect**: outbound links were already listed on open; inbound links appear when the section
expands. `↑↓` moves, `enter` or `o` opens the target in whichever collection it lives in, `esc`
collapses. Every one of those keys is visible in the footer. A record nothing points at says so
rather than showing an empty box.

---

## Scenario 8 — Documentation (US8, SC-011)

```bash
wc -l src/endpaper/core/templates/AGENTS.md.tmpl      # MUST be <= 60
```

**This is an acceptance check, not a formality.** The template is at 63 lines today and this feature
adds three things to it; the plan requires tightening it back under the limit (research R9). A
template that quietly grows past 60 is the bloated-context-file failure the constitution warns about.

Then confirm the content is actually there:

```bash
grep -c 'endpaper links' src/endpaper/core/templates/AGENTS.md.tmpl   # the three commands
grep 'meeting_\|note_\|task_' src/endpaper/core/templates/AGENTS.md.tmpl
grep -A5 'Create a workspace' README.md | grep -i 'OneDrive\|offline'
```

**Expect**: AGENTS.md documents the link syntax, the `links:` field, the current prefixes, and the
commands; README warns about cloud placeholders in the workspace-creation section, naming OneDrive,
Dropbox, Google Drive, and iCloud Drive, and says why.

**SC-011** is the real test: hand a fresh assistant only the generated `AGENTS.md` and ask it to
write a link, ask what points at a record, and repair stale paths. It should need nothing else.

---

## Automated coverage

Risk-based per Principle VI — chosen for what could plausibly break, not generated one-per-acceptance-
scenario. A behaviour is verified at one layer, not at every layer it touches.

| Layer | What it covers | Why here |
|---|---|---|
| `tests/unit/test_link_scan.py` | The scanner and its mask: fences (``` and `~~~`, unclosed, info strings), inline code spans including multi-backtick runs, images, URL schemes, reference-style links, two links on one line, unclosed links | **The highest-risk code in the feature.** Subtle masking bugs corrupt user prose silently, and this is cheap to test exhaustively without a workspace |
| `tests/unit/test_link_paths.py` | `relative_destination` from every layout depth; forward slashes; angle-bracket escaping | Pure arithmetic with a wide input space — table-driven, no I/O |
| `tests/unit/test_link_resolve.py` | Id-before-path ordering; old-prefix ids; duplicate ids resolving deterministically with a warning; dead is not an exception | Ordering and the never-raise guarantee are easy to regress |
| `tests/unit/test_task_parse.py`, `test_task_render.py` | `links:` parse, render, field order, malformed values, and the no-`links:` line being unchanged | Extends existing modules rather than adding new ones |
| `tests/integration/test_links.py` | One end-to-end path per user story, parametrized across CLI and TUI where both apply | Constitution VI asks for parametrized adapters, not duplicated files |
| `tests/integration/test_link_heal.py` | Save-time repair; `heal` vs `dry-run` producing the same set; dead links untouched beside repaired ones; no write when nothing is stale | The write path is where data loss would happen |
| `tests/contract/test_links_cli.py` | JSON schema keys, exit codes per command, stdout/stderr separation, non-blocking | The AI-facing surface; Principle II |
| `tests/performance/test_link_scan.py` | SC-006: inbound links under 500 ms at 6,000 documents, marked `@pytest.mark.performance` | A real budget exists, and it is the justification for having no index |
| `tests/unit/test_footer_bindings.py` | Extended for the new preview bindings | Existing guard, existing file |

**Not** separately tested: every acceptance scenario in the spec. Ten scenarios describing one
behaviour get one test (Principle VI). The scenarios remain the specification of intent; the tests
cover the ways the implementation could break.

---

## Gates before merge

```bash
uv run ruff format --check . && uv run ruff check .
uv run mypy
uv run pytest -q                                     # 407 baseline + this feature's tests
wc -l src/endpaper/core/templates/AGENTS.md.tmpl     # <= 60
```

Plus, per the constitution's workflow section: TUI changes verified on Windows Terminal, iTerm2,
macOS Terminal, PuTTY, and inside tmux before release; and the changelog updated with the id prefix
change, the task line format change, the new commands, and the new JSON schema (FR-054).
