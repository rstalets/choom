# Phase 0 Research: Document Links

**Feature**: `008-document-links` | **Date**: 2026-07-31 | **Spec**: [spec.md](spec.md)

Every decision below was taken against the code as it stands on `main`, and the three that carried
real risk — link scanning without a new dependency, the inbound-scan performance budget, and the
`AGENTS.md` line budget — were settled by measurement rather than by argument. The probe script and
its output are reproduced under [Measurements](#measurements).

Baseline before any change: **407 tests pass** (`pytest -q`, 74s).

---

## R1. Finding links in markdown without adding a dependency

**Decision**: A stdlib `re` scanner for CommonMark inline links, run over text with fenced code
blocks and inline code spans masked out. No new dependency.

**Rationale**:

The requirement that drives this is FR-026 — repair must preserve link text, surrounding prose, and
line endings. That means the scanner has to return *exact source offsets* so a rewrite can splice a
new destination into the original string and change nothing else. Repair is a byte-level edit, not a
re-render.

Three options were considered:

| Option | Verdict |
|---|---|
| Stdlib `re` + code mask | **Chosen.** Returns offsets natively; no dependency; 15/15 probe cases pass |
| `markdown-it-py` | Rejected — see below |
| Re-render from an AST | Rejected outright: round-tripping markdown through any parser reformats prose, which violates FR-026 and Principle IV |

`markdown-it-py` is present in the environment as a transitive dependency of `textual`, so it is
tempting to treat it as free. It is not:

- It is not a declared dependency. Relying on a transitive one means a `textual` release that drops
  or swaps its markdown engine silently breaks link repair. Declaring it instead means a new
  third-party dependency, which Principle III requires be justified by what it would cost to do
  without — and the probe shows that cost is about 40 lines of scanner.
- `core` may not import `textual` (enforced by a ruff banned-api rule), and importing a library
  *because* textual happens to vendor it is the same coupling with the lint check looking the other
  way.
- Its token stream gives `map` (line spans) for block tokens but not reliable character offsets for
  inline children, so the offsets FR-026 needs would have to be recovered by re-scanning the source
  anyway.

The scanner is deliberately narrower than CommonMark: it recognises **inline links only**
(`[text](dest)`), skips images via a negative lookbehind on `!`, and does not attempt reference-style
links (`[text][ref]`), which endpaper never writes. A reference-style link is therefore ordinary
prose to this feature — it is not resolved, not repaired, and not reported. That is a deliberate
scope boundary, recorded here so it is not mistaken for a bug.

**Masking is the load-bearing part.** Without it, the link-syntax examples in a note about link
syntax would be rewritten, which is exactly the "never lose the user's words" failure Principle IV
exists to prevent. The mask covers fenced blocks (``` and `~~~`, including unclosed fences to end of
file, and correctly ignoring a fence line whose info string contains the fence character) and inline
code spans with CommonMark's equal-length-backtick-run rule, so ``` ``a ` b`` ``` masks correctly.

**Alternatives considered**: parsing with `markdown-it-py` (above); a naive regex with no mask
(rejected — rewrites code examples); requiring links to sit on their own line (rejected — the whole
point is a link inside a sentence).

---

## R2. The inbound scan, and whether it is fast enough

**Decision**: Read each candidate file's bytes, test for the target id as a raw substring, and run
the full link scanner only on files that hit. No index, no cache, nothing persisted.

**Rationale**: Measured on a synthetic 6,000-document workspace (50.3 MB, ~5 years of heavy use):

| Operation | Measured |
|---|---|
| Inbound links for one id, candidate-filter scan | **155 ms** (median of 5; min 155 ms) |
| Parsing the frontmatter of the same corpus | 832 ms |
| Ratio | candidate filter is **5.4× cheaper** than merely parsing frontmatter |

SC-006 budgets half a second. The measurement leaves **3.2× headroom**, so the scan ships without an
index and Principle III is satisfied by measurement rather than by assertion.

**On the number in issue #27**: the issue cites ~84 ms for the scan and ~823 ms for the frontmatter
parse. The frontmatter figure reproduces almost exactly (832 ms), which says the corpus is
comparable; the scan figure did not (155 ms vs 84 ms), which is most likely machine and
storage differences. The plan commits to the number this project actually measured, not the one the
issue quoted. Either number clears the budget.

The cost is dominated by reading 50 MB off disk, not by CPU — which is precisely why User Story 8
(pin the workspace to local disk) is part of this feature and not a footnote. On a cloud folder with
on-demand placeholders this same scan becomes N network round trips.

**Two correctness rules the substring filter needs**, both from the spec:

- A hit is a *candidate*, not a result. Only a link found by the R1 scanner whose destination
  fragment equals the target id counts (FR/US3 AC6 — an id mentioned in prose is not a link).
- The target's own file hits its own id via the frontmatter `id:` line. That occurrence is not a
  link, so the scanner rejects it naturally; no special-casing is required, but there is a test for
  it (US3 AC7).

**Alternatives considered**: a stored index (`.endpaper/links.json`) — rejected by Principle III and
by the measurement, which shows there is nothing to optimise; reciprocal back-reference blocks
written into targets — rejected in the spec's Out of Scope on failure modes, and the measurement
removes the performance argument for them.

---

## R3. Computing the relative path

**Decision**: `os.path.relpath(target, source.parent)`, then `.replace(os.sep, "/")` to force POSIX
separators in the link destination.

**Rationale**: `Path.relative_to` cannot walk upwards, so it is unusable here — the common case is a
link that ascends out of `notes/daily/2026/07/` and back down into `meetings/2026/07/`.
`os.path.relpath` is pure string arithmetic on the two paths and touches no filesystem.

Forcing forward slashes is not cosmetic. A link written on Windows with backslashes is not a valid
relative URL and will not resolve on macOS or Linux, breaking the shared-workspace premise. Link
destinations are URLs, and URLs use `/` on every platform.

Verified round-trip (resolve the generated relative path back and compare to the target) from every
depth the layout produces:

| From | To | Generated |
|---|---|---|
| `meetings/2026/07/a.md` | `notes/2026/07/b.md` | `../../../notes/2026/07/b.md` |
| `notes/daily/2026/07/d.md` | `meetings/2026/07/a.md` | `../../../../meetings/2026/07/a.md` |
| `tasks.md` | `meetings/2026/07/a.md` | `meetings/2026/07/a.md` |
| `meetings/2026/07/a.md` | `tasks.md` | `../../../tasks.md` |
| `notes/stray.md` (outside the dated layout) | `notes/daily/2026/07/d.md` | `daily/2026/07/d.md` |
| `meetings/2026/07/a.md` | `meetings/2026/07/b.md` | `b.md` |

All six round-trip. The prefix ranges from nothing at all to `../../../../`, which confirms the
spec's insistence that depth is not a constant and paths cannot be authored by hand.

**Path length**: the worst case measured is a 117-character *link destination* — a daily note
pointing at a maximally-long meeting filename. This is text inside a file, not a filesystem path, so
it does not consume the Windows 260-character budget. The filesystem paths themselves are unchanged
by this feature.

---

## R4. Destinations that need escaping

**Decision**: Wrap the destination in angle brackets (`[text](<path with space.md#id>)`) when it
contains a space, a parenthesis, or a `<`/`>`. Otherwise write it bare. Never percent-encode.

**Rationale**: endpaper's own filenames are slugified to `[a-z0-9-]`, so a generated path never needs
escaping. But links point at files a user may have placed by hand, and the workspace is documented as
hand-editable — `notes/Q3 (draft).md` is a legal file.

CommonMark's angle-bracket destination form handles spaces and parentheses in one rule, stays
readable, and round-trips exactly. Percent-encoding was rejected because it makes the destination
unreadable in the raw file, and the raw file is what an assistant reads.

The R1 probe confirms `[a](<has space.md#note_1>)` parses to the destination `has space.md#note_1`.

---

## R5. Where repair hooks into the write path

**Decision**: Add a keyword-only `workspace: Workspace | None = None` to
`core.editing.save_buffer`, and a `warnings` field to `SaveResult`. When a workspace is passed,
`save_buffer` heals the text before stamping `updated`.

**Rationale**: `save_buffer` is the single write path for documents, and putting repair inside it is
what makes FR-022 ("when the system writes a file") true for both adapters at once rather than being
re-implemented per adapter — Principle II.

The blast radius is small, which is what makes this the right seam: `save_buffer` has exactly **one**
production caller (`tui/edit_screen.py:140`) and four test call sites. A keyword argument defaulting
to `None` leaves all five test calls compiling unchanged, and `None` means "no workspace resolved, so
nothing to resolve against" rather than a feature flag.

`EditScreen._save()` already handles `result.saved_text != editor.text` by reassigning the buffer —
that path exists because stamping `updated` already changes the text under the user. Healing lands in
exactly the same situation and reuses the mechanism, so no new editor state is introduced.

**Ordering inside `save_buffer`**: heal the body, then stamp `updated`, then apply the line-ending
policy. Healing only ever touches link destinations in the body and stamping only ever touches the
frontmatter `updated:` line, so the two cannot interfere; this order is chosen because it keeps the
existing line-ending policy as the last step that sees the text.

**A distinction the plan must not blur**: saving stamps `updated` because the user saved — that is
existing behaviour and is not what "a repair pass does not invent modifications" means. That rule
(spec Edge Cases → Repair) governs `endpaper links heal`, which must not touch a file with nothing
stale in it. Two different write paths, two different rules.

`tasks.md` has its own write path (`_atomic_write`), but a task's `links` field holds bare ids with
no paths (FR-018), so there is nothing in `tasks.md` that can go stale and nothing to heal there.

---

## R6. The id prefix change

**Decision**: Change the four literals; do not migrate, do not accept the old prefixes specially.

**Rationale**: The change is genuinely small in production code, which is the whole argument for
doing it pre-release:

| Site | Change |
|---|---|
| `core/meetings.py:24` | `Collection("m_", ...)` → `Collection("meeting_", ...)` |
| `core/notes.py:26` | `Collection("n_", ...)` → `Collection("note_", ...)` |
| `core/text.py:41` | `new_meeting_id` returns `new_document_id(when, "meeting_")` |
| `core/text.py:46` | `new_task_id` builds `f"task_{...}"` |

Nothing else in production needs touching, and this was verified rather than assumed:

- `_IDVAL = ^[A-Za-z0-9_-]+$` (`core/tasks.py:19`) already accepts `meeting_20260728_a1b2c3d4`.
- No code splits an id on `_` or reads it by fixed offset, so the extra segment breaks no resolution
  path (FR-014 codifies that this stays true).
- `_TOKEN_PATTERN`'s 40-character cap applies to `type` and `tag` values, not to ids.
- `new_meeting_id` (`core/text.py:40`) is exported from `core/__init__` but has **no production
  caller** — `create_document` goes through `collection.id_prefix`. It is updated for consistency,
  and its deadness is noted here so a future cleanup has the finding.

FR-013 (existing ids keep resolving) needs no code: resolution matches an id as a whole opaque token,
so `m_20260728_a1b2c3d4` and `meeting_20260728_a1b2c3d4` coexist without ambiguity and without a
compatibility branch.

The real work is the surrounding material — literal example ids appear in `AGENTS.md.tmpl`,
`REQUIREMENTS.md`, `CHANGELOG.md`, and **16 test modules** (enumerated in `tasks.md` T010):
one contract, five integration, one performance, and nine unit. An initial narrower grep found 11
and this document previously said 10; the corrected sweep covers fixture ids such as `id: m_1` and
generated ones such as `f"id:t_{i:04x}"`, which the first pass missed. The deliberately-malformed
`<!-- id:` fixture in `tests/integration/test_malformed.py` carries no prefix and is unaffected.

**Alternatives considered**: accepting both prefixes at creation time behind a setting — rejected,
Principle III forbids a knob that could be a default; a migration command that rewrites ids in place
— rejected, it is exactly the file-moving-and-rewriting endpaper promises never to do, and
pre-release there is nothing to migrate.

---

## R7. `links:` on the task line

**Decision**: Add `"links"` to `_RECOGNIZED_KEYS`, validate its values with `_IDVAL`, add a
`links: tuple[str, ...]` field to `Task`, and emit it between `tags` and `created` in
`_render_comment`.

**Rationale**: The parser's existing `_classify_body` (`core/tasks.py:49`) buckets a comment as
`bare` / `malformed` / `task`, and **any unrecognised key makes the whole line `malformed`, which
drops the task from the list entirely**. That has a consequence worth stating plainly: *today*, a
user who hand-writes `links:` on a task line loses that task from every listing. Adding the key is
therefore not merely additive — it fixes a live data-visibility trap.

The same mechanism gives FR-016 for free. A line with no `links:` field takes the identical code
path it takes now, `_render_comment` omits empty fields, and no existing `tasks.md` is rewritten.

Validation mirrors `tags`: split on `,`, reject empty, and require each value to match `_IDVAL`
(the pattern already used for the `id` field, and the right one here because the values *are* ids).
A malformed value returns `malformed`, which produces a warning and skips that one line while every
other task still parses — the tolerance FR-020 asks for is the tolerance the parser already has.

FR-019 (an id that resolves to nothing is preserved and reported, never dropped) is a resolution-time
concern, not a parse-time one: a syntactically valid id that names nothing parses fine and is
reported dead by `links check`.

---

## R8. Command surface and exit codes

**Decision**: One new top-level `links` subparser with three forms, following the existing
`meeting` / `note` / `task` nesting pattern in `cli/main.py`.

```
endpaper links <id> [--json] [--direction out|in|both]
endpaper links check [<path>...] [--json]
endpaper links heal  [<path>...] [--json] [--dry-run]
```

**Rationale**: `argparse` sub-subparsers are already the house style. The one wrinkle is that
`links <id>` and `links check` occupy the same slot — `check` and `heal` are reserved words in that
position. This is resolved by declaring the reserved words rather than by heuristics: since ids are
prefixed (`meeting_`, `note_`, `task_`), no real id can ever collide with `check` or `heal`, so the
ambiguity is theoretical and the reservation is safe. R6's prefix change is what makes it safe.

**Exit codes** follow the constitution's contract, with the one mapping decision the spec's
Assumptions already fixed: `1` is "not found", and an unresolved link is a target not found, so both
stale and dead links exit `1`. Usage errors are `2`, workspace errors `3`.

| Command | 0 | 1 |
|---|---|---|
| `links <id>` | always, including no links found (US3 AC4) | id itself does not resolve |
| `links check` | nothing stale and nothing dead | anything stale or dead |
| `links heal` | nothing stale remains and nothing was dead | any dead link remains |
| `links heal --dry-run` | same as `check` | same as `check` |

**JSON schema** is fixed by FR-039 at `file`, `line`, `text`, `target_id`, `old_path`, `new_path`,
`status`. `old_path`/`new_path` are `null` where they do not apply (a fragment-only link has no old
path; a dead link gets no new one). Full schema in [contracts/cli.md](contracts/cli.md).

**Note on scope**: `endpaper read` / `write` / `append` / `find` are described in REQUIREMENTS §4.2
but do not exist in `cli/main.py` yet. `links` does not depend on them and does not add them.

---

## R9. The `AGENTS.md` line budget

**Decision**: Add link syntax, the `links:` field, and the three commands, and pay for them by
tightening what is already there. Target ≤ 60 lines.

**Rationale**: This is a genuine constraint collision and was nearly missed. `AGENTS.md.tmpl` is
**already 63 lines**, and the constitution requires it stay "under roughly 60". FR-052 adds three
things to it. Left alone, the file would land near 75 lines and quietly violate a platform
constraint.

Verified achievable — the room exists in four places, and the arithmetic clears the target:

| Change | Lines |
|---|---|
| Frontmatter YAML example: drop the 3 blank/fence lines by folding into the layout block | −3 |
| The two-line `--tag` shell caveat: one line, keeping the warning | −1 |
| Layout block: fold `AGENTS.md this file` (self-evident) | −1 |
| Exit-code section: 4 lines → 2 | −2 |
| **Reclaimed** | **−7** |
| Link syntax + example | +4 |
| `links:` in the task example (existing line, edited) | 0 |
| Three `endpaper links` command lines | +3 |
| **Added** | **+7** |

Net zero against a 63-line file, leaving it at 63 — over the target. The remaining 3+ lines come from
the commands block, where `meeting list` and `note list` demonstrate the same four flags twice; one
of them collapses to a comment. Confirming the final file is ≤ 60 lines is an explicit task
acceptance check, not an aspiration, because a template that silently grows past the limit is exactly
the "bloated context file" the constitution's rationale warns about.

---

## R10. TUI surface

**Decision**: The Links section is a collapsible region inside the existing `PreviewScreen`, not a
new screen. `l` toggles it; `enter` opens the selected link. Outbound links render on open; inbound
links are fetched the first time the section is expanded.

**Rationale**: Principle V fixes the state model at list → preview → edit, so a fourth screen is out.
A region inside `PreviewScreen` keeps `esc` meaning "back to the list" and `e` meaning "edit".

Key choice, against the constraints in Principle V and REQUIREMENTS §4.5:

- `l` is free in preview state (`PREVIEW_HELP` is `e edit   esc back   ↑↓/pgup/pgdn scroll   ctrl+q
  quit`). In the *list* screen `h`/`l` move between panes, so `l` already reads as "move rightward
  into a pane" in this app; reusing it for "open the links pane" is consistent rather than colliding.
- `o` is offered as an alias for opening a selected link, per the issue, with `enter` canonical.
- No new modifier. `ctrl+c`, `ctrl+q` untouched.

**Footer budget is a real constraint, not a formality.** `PREVIEW_HELP` is currently 53 characters
and the footer must show every active binding (Principle V, and `tests/unit/test_footer_bindings.py`
enforces it). Adding `l links` takes it to 63, which still fits an 80-column terminal. When the
section is expanded the help text swaps to a links-specific string rather than concatenating, so the
footer never overflows — the same approach `EDIT_HELP` already takes.

**The load rule is behavioural, not an optimisation** (FR-048/FR-049): outbound links come from the
document already in memory and cost nothing, so they show on open; inbound links cost the R2 scan, so
they wait for the user to ask. This is why the section is expandable at all.

---

## R11. Resolution, ambiguity, and `/link`

**Decision on duplicate ids**: resolve deterministically to the first match in workspace path sort
order, and emit a warning naming every path that carries the id.

**Rationale**: The existing code already faced this question for tasks and answered it —
`set_task_state` raises `UsageError` naming the line numbers when an id appears twice
(`core/tasks.py:419`). Link resolution cannot raise, because one duplicated id elsewhere in the
workspace must not make an unrelated file unreadable (Principle IV). Deterministic-plus-warning is
the same spirit with the non-fatal requirement honoured.

**Decision on `/link`**: reuse `core.editor_commands`, matching against title and id with the same
case-insensitive substring rule `match_document` already implements.

**Rationale**: The plumbing exists — `EDITOR_COMMANDS` and `parse_line` (`core/editor_commands.py`)
already back `/ai`, and `EditorTextArea` already intercepts Enter and posts
`EditorCommandSubmitted`. Adding `/link` is a table entry plus a handler, which is precisely the
reuse the spec claims. Registering it in `EDITOR_COMMANDS` also puts it in `/help` automatically.

Matching reuses `match_document` so `/link` and the list filter agree on what "matches" means; two
different notions of matching in one app would be a bug waiting to be reported. Zero matches and two
or more matches both leave the line untouched and report in the status bar (FR-044) — the ambiguity
message names candidates so the user can retype, which is the spec's stated alternative to a picker.

---

## Measurements

Probe script: `probe_links.py` (run once during Phase 0; not committed, as it tests a prototype
rather than shipped code — the shipped equivalents become the tests named in `tasks.md`).

```
=== 1. link scanner ===
  -> 15/15 pass
     covers: fragment-only, full relative path, image (skipped), inline code span,
     double-backtick span containing a tick, ``` fence, ~~~ fence, text after a fence,
     external URL, angle-bracket destination with a space, two links on one line,
     unclosed link, no links, reference-style link (skipped), fence with an info string

=== 3. relative path round-trip ===
  6/6 round-trip, prefixes from `` to `../../../../`
  worst-case link destination: 117 chars (text in a file, not a filesystem path)

=== 2. inbound scan on synthetic corpus ===
  corpus: 6000 files, 50.3 MB
  candidate-filter scan: min 155 ms  median 156 ms
  full frontmatter parse of same corpus: 832 ms
  ratio: candidate filter is 5.4x cheaper
```

---

## Resolved unknowns

The spec carried no `[NEEDS CLARIFICATION]` markers. Everything the Technical Context could have
flagged is settled above:

| Question | Resolved by |
|---|---|
| Markdown parsing without a new dependency | R1 — measured, 15/15 |
| Is a scan fast enough to ship with no index? | R2 — measured, 155 ms vs a 500 ms budget |
| Relative paths from every layout depth | R3 — measured, 6/6 |
| Paths containing spaces | R4 — angle-bracket destinations |
| Where healing attaches to writes | R5 — `save_buffer`, one production caller |
| Cost of the id prefix change | R6 — 4 production literals, 10 test modules |
| Does `links:` break existing task lines? | R7 — no; and it fixes a live trap |
| Command shape and exit codes | R8 — reserved words made safe by R6 |
| Does `AGENTS.md` still fit the budget? | R9 — yes, but only with deliberate cuts |
| TUI binding and footer budget | R10 — `l`, later rebound to `b`; 67 chars |
| Duplicate ids; `/link` ambiguity | R11 — deterministic + warning; report, don't pick |
