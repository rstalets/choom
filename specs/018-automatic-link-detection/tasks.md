---

description: "Task list for 018-automatic-link-detection"
---

# Tasks: Bare URLs Become Markdown Links on Save

**Input**: Design documents from `/specs/018-automatic-link-detection/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included, and **not** as a trailing phase. Every behaviour change lands with the tests that
cover it, in the same task — Constitution Principle VI and the Development Workflow gate. There is no
"write the tests afterwards" step in this list, deliberately.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different file, no dependency on an incomplete task
- **[Story]**: which user story the task serves (US1–US4); Setup, Foundational, and Polish carry none
- Every task names the file it touches and the command that verifies it

## Path Conventions

Single project: `src/choom/{core,cli,tui}` over `tests/{unit,contract,integration}`. Tests run through
`scripts/dev-tests.sh`, never a hand-rolled `pytest` invocation.

---

## The one mistake that would sink this feature

**Do not reuse `_LINK_RE` as the exclusion mask.** It is the existing pattern, it is right there in
`links.py`, and reaching for it is the single most likely way this ships broken — because it would look
correct on the common case and corrupt files on four uncommon ones. Probed directly:

| Form | `_LINK_RE` matches? |
|---|---|
| `[a](https://x.com/plain)` — control | **yes** |
| `[a](https://x.com/Foo_(bar))` — balanced parens, legal CommonMark | **NO** |
| `![alt](https://x.com/a.png)` — image | **NO** |
| `[spec]: https://example.com/spec` — reference definition | **NO** |
| `<https://example.com>` — autolink | **NO** |

The rule, which belongs in the code comment and not only here: **a scanner and a mask fail in opposite
directions.** `_LINK_RE` exists to find record links choom will act on, so being narrow is safe — a link
it misses is simply not healed. A mask exists to find what must not be touched, so being narrow is
unsafe — a link it misses gets a second `[…](…)` wrapped around its destination. **A mask must be a
superset of the grammar, never a subset.**

---

## Phase 1: Setup

**Purpose**: establish the baseline and put the trap in front of the implementer before they can fall
into it.

- [x] T001 Confirm the baseline is green before changing anything: run `scripts/dev-tests.sh` from the
      repository root and record that it passes (1105 tests at time of writing). Also run
      `uv run ruff format --check . && uv run ruff check . && uv run mypy src`. Do not start T002 on a
      red tree — a pre-existing failure attributed to this feature wastes the whole gate
- [x] T002 Reproduce the `_LINK_RE` probe from the table above in a throwaway snippet against
      `src/choom/core/links.py`, and confirm all four forms miss while the plain-link control matches.
      This is not busywork: it is the evidence for why Phase 2 writes a new mask instead of reusing the
      pattern that already exists, and an implementer who has seen it fail will not "simplify" Phase 2
      later. Verify: the snippet prints one MATCHED and four MISSED. Delete the snippet afterwards —
      it is not a test, it is a briefing
- [x] T003 Add the `UrlConversion` frozen slotted dataclass to `src/choom/core/models.py` per
      [data-model.md](./data-model.md) §1 (`start`, `end`, `url`, `replacement`), and add the additive
      defaulted field `conversions: tuple[UrlConversion, ...] = ()` to the existing `SaveResult`.
      Defaulted so every existing construction site and test keeps working untouched. Verify:
      `scripts/dev-tests.sh` still green and `uv run mypy src` clean, with no other file changed

**Checkpoint**: tree green, value types in place, nothing behavioural has moved yet.

---

## Phase 2: Foundational — the exclusion masks (BLOCKING)

**Purpose**: the safety substrate. Every Principle IV guarantee in this feature is a property of these
masks. No user story can begin until they are done and individually tested.

**⚠️ CRITICAL**: all seven masks are length-preserving — they blank their spans to spaces and leave
`\n` and `\r` in place. That is what makes an offset found in the masked text valid in the original,
and it is the idiom `_mask_fences` and `_mask_code_spans` already use. A mask that changes length is a
bug that will present as mangled output far from its cause.

- [x] T004 **Reuse `_mask_fences` and `_mask_code_spans` verbatim — write no new code for either**
      (FR-031). They already handle tilde fences, unclosed fences, fence info strings, and CommonMark's
      equal-length-backtick-run rule for code spans. A second notion of "what counts as code" in one
      codebase is how a byte-preservation guarantee gets quietly broken, which is exactly why
      `links.py` holds its grammar in one file. This task is a decision to record, not code to write:
      add a comment at the new pipeline's definition naming both as reused. Verify: the diff adds no
      fence-parsing or backtick-parsing logic anywhere
- [x] T005 [P] Add `_mask_frontmatter` to `src/choom/core/links.py` — blank from a leading `---\n` to
      the closing `\n---` inclusive; leave text unchanged when either delimiter is absent. Cover it in
      `tests/unit/test_bare_url_format.py` including a file with no frontmatter and one with an
      unterminated block. **Why this is stricter than `heal_text`, which does not mask frontmatter**:
      `title: [https://x](https://x)` makes `_parse_document` return `malformed_yaml` with `doc=None`,
      because an unquoted YAML scalar opening with `[` is a flow sequence — the note then drops out of
      every list choom draws. Verify:
      `scripts/dev-tests.sh tests/unit/test_bare_url_format.py -k frontmatter`
- [x] T006 [P] Add `_mask_comments` to `src/choom/core/links.py` — blank `<!--` through the next
      `-->`, across line boundaries, and to end-of-file when unterminated. Masking to EOF is the
      correct failure direction: it converts *less*. Cover the task line's metadata comment
      (`<!-- id:task_a1b2 links:… created:… -->`), a multi-line comment, and an unterminated one in
      `tests/unit/test_bare_url_format.py`. Verify:
      `scripts/dev-tests.sh tests/unit/test_bare_url_format.py -k comment`
- [x] T007 **Add `_mask_links` to `src/choom/core/links.py` — the task where this feature is most
      likely to go wrong.** Mask `[text](dest)` **and** `![alt](dest)`, scanning the destination with
      **paren-depth counting** so a destination carrying balanced parentheses is fully covered. **Do
      not use `_LINK_RE`**; see the table at the top of this file for the four forms it misses and why
      a mask must be a superset rather than a subset. Put that reasoning in a code comment at the
      function, not only in the spec. Mask **the whole span, both halves** — link text and destination
      together; the link-text half is what makes the transform idempotent (T019), and a mask covering
      only the destination produces `[[U](U)](U)` on the second save. Cover in
      `tests/unit/test_bare_url_format.py`: plain link, image, balanced-paren destination,
      angle-wrapped destination, choom's own `[a](<notes/Q3 (draft).md#note_1>)`, and a link whose text
      is already a URL. Verify: `scripts/dev-tests.sh tests/unit/test_bare_url_format.py -k mask_links`
- [x] T008 [P] Add `_mask_angle` to `src/choom/core/links.py` — blank `<…>` runs containing no
      newline, which covers CommonMark autolinks and raw HTML tags in one rule. This is also the
      **backstop for T007**: an angle-bracketed destination with *unbalanced* parens inside it defeats
      the depth counter, and this mask catches the `<…>` anyway. Cover `<https://example.com>`,
      `<a href="https://example.com">`, and `[a](<https://x.com/Q3 (draft>)` in
      `tests/unit/test_bare_url_format.py`. Verify:
      `scripts/dev-tests.sh tests/unit/test_bare_url_format.py -k angle`
- [x] T009 [P] Add `_mask_refdefs` to `src/choom/core/links.py` — blank a link reference definition,
      `^ {0,3}\[…\]:[ \t]*\S+`. Wrapping its destination would break the definition and silently kill
      every `[label]` reference in the file. Cover in `tests/unit/test_bare_url_format.py`. Verify:
      `scripts/dev-tests.sh tests/unit/test_bare_url_format.py -k refdef`
- [x] T010 Compose the seven masks into one private pipeline in `src/choom/core/links.py`, in this
      order: **frontmatter → fences → code spans → comments → links/images → angle spans → refdefs**.
      Code and comments come first because their contents are opaque — a fenced block containing
      `[a](b)` must not be read as link syntax by T007, and a commented-out link must not be either.
      Angle spans come after links so T008 can backstop T007. Add a unit test asserting the pipeline is
      **length-preserving for every corpus input** (`len(masked) == len(original)`) and that `\n`/`\r`
      counts are unchanged — this single property is what makes every offset in the feature valid.
      Verify: `scripts/dev-tests.sh tests/unit/test_bare_url_format.py -k mask_pipeline`

**Checkpoint**: every exclusion is individually proven. Nothing converts yet, so the tree is green and
behaviour is unchanged.

---

## Phase 3: User Story 1 — the pasted URL becomes followable (Priority: P1) 🎯 MVP

**Goal**: a bare `http://`/`https://` URL in a saved document becomes `[url](url)` on disk and in the
buffer.

**Independent Test**: open a note in the editor, type a line with a bare URL, save, read the file back.

- [x] T011 [US1] Add the candidate scanner to `src/choom/core/links.py`: the pattern
      `(?<![^\s([{"'*_~|>])(?P<u>https?://[^\s<>\[\]]*)`, case-insensitive on the scheme. Two details
      are load-bearing and belong in a code comment. **`<` is deliberately absent from the leading
      set** — that single omission is what makes a CommonMark autolink non-convertible before any mask
      is consulted. **The character class excludes exactly the characters that would make the output
      unsafe**: whitespace and `<`/`>` would break the angle-wrapped destination, `[`/`]` would break
      the link-text slot. Cover `xhttps://example.com/a` (fails the leading boundary),
      `https://[::1]/status` (contains brackets), and `text https:// more` (no host) in
      `tests/unit/test_bare_url_format.py`. Verify:
      `scripts/dev-tests.sh tests/unit/test_bare_url_format.py -k candidate`
- [x] T012 [US1] Add the emitter to `src/choom/core/links.py`: build `[{url}]({destination})` where
      `destination` comes from the **existing** `_render_destination`, reused unmodified so the healer,
      `/link` insertion, and this feature can never disagree about escaping. Because T011's character
      class already guarantees no `<` or `>` is present, the angle-wrapped form can never itself fail.
      Assert the only-ever-wraps invariant in `tests/unit/test_bare_url_format.py`: the URL appears
      byte-for-byte in both slots, and `len(replacement) > len(url)` always. Assert the **inverse**
      too, once over the whole of Corpus A — deleting the four added characters and the duplicated URL
      reproduces the input exactly, with nothing percent-encoded, case-folded, or given or denied a
      trailing slash. That is the mechanical form of FR-001's core promise. Verify:
      `scripts/dev-tests.sh tests/unit/test_bare_url_format.py -k emit`
- [x] T013 [US1] Assemble the public `format_bare_urls(text) -> tuple[str, tuple[UrlConversion, ...]]`
      in `src/choom/core/links.py` per [contracts/core-api.md](./contracts/core-api.md) C1: mask, scan,
      trim (T020 supplies the trim; stub it as identity until then and finish this task after T020 if
      working strictly in order), build `UrlConversion` records, splice into the **original** text in
      reverse offset order. Full type hints and a docstring stating what it does and that it **never
      raises** — "never raises" is a load-bearing contract (FR-032), not a courtesy. Must take no
      `Workspace` and no `Path`. Verify: `scripts/dev-tests.sh tests/unit/test_bare_url_format.py` and
      `uv run mypy src`
- [x] T014 [US1] Export `format_bare_urls` and `UrlConversion` from `src/choom/core/__init__.py`'s
      `__all__`, and add both to the name list in
      `tests/unit/test_core_imports.py::test_links_public_surface_is_exported`. Verify:
      `scripts/dev-tests.sh tests/unit/test_core_imports.py`
- [x] T015 [US1] Wire the conversion into `save_buffer` in `src/choom/core/editing.py`. **The order is
      `heal_text` → `format_bare_urls` → `stamp_updated` → `_apply_line_ending_policy` →
      `write_text_atomic`, and it is one atomic write, not two** (FR-023, FR-024). Two reasons to state
      in a comment: **convert must precede the stamp**, or `SaveResult.saved_text` and the bytes on
      disk diverge; and heal and convert act on **provably disjoint spans** — a healed record link's
      destination carries no scheme and this feature masks that whole span, while a converted link's
      destination *does* carry a scheme and `_link_from_match` returns `None` for it. The conversion is
      **unconditional** — unlike healing it does not depend on `workspace` being passed, because it
      needs nothing from the workspace. Populate `SaveResult.conversions`. Cover in a new
      `tests/integration/test_bare_url_save.py`: a save converts, stamps, and produces exactly one
      write; and a document with both a stale record link and a bare URL gets both fixed in that one
      write with neither disturbing the other. Verify:
      `scripts/dev-tests.sh tests/integration/test_bare_url_save.py`
- [x] T016 [US1] Add `map_cursor_offset(conversions, offset) -> int` to `src/choom/core/links.py` per
      [contracts/core-api.md](./contracts/core-api.md) C2 — pure integer arithmetic over the
      conversions, reading no text. An offset before every conversion is unchanged; after one it
      shifts by what earlier conversions added; **strictly inside a converted span it lands at the end
      of that span's replacement**, because there is no meaningful position between the two copies of
      the URL. Cover all three cases plus the empty-conversions case in a new
      `tests/unit/test_url_cursor_map.py`. Verify: `scripts/dev-tests.sh tests/unit/test_url_cursor_map.py`
- [x] T017 [US1] Use the mapping in `EditorPane._save` in `src/choom/tui/edit_screen.py`. The buffer
      re-sync already exists for the `updated:` stamp; the stamp is length-neutral so restoring
      `(row, col)` verbatim has always been correct, and a conversion is not. Keep the row as-is — no
      conversion inserts a newline, so the cursor never changes line — and map the column via
      `map_cursor_offset`, using Textual's `Document.get_index_from_location` /
      `get_location_from_index` (both confirmed present on `textual==8.2.8`) to move between
      coordinates and offsets. Cover in `tests/integration/test_bare_url_save.py`: the cursor does not
      land inside a URL that was just wrapped. Verify:
      `scripts/dev-tests.sh tests/integration/test_bare_url_save.py -k cursor`
- [x] T018 [US1] Add the status message in `src/choom/tui/edit_screen.py` per
      [contracts/tui.md](./contracts/tui.md) T3: `formatted 1 link` / `formatted {n} links`, and
      **nothing at all when the count is zero** (FR-025). Silence at zero is the requirement, not an
      optimisation — a message on every save is a message nobody reads. Compose it into the existing
      `"; ".join(...)` chain so it never replaces a warning. Cover both the non-zero and the zero case
      in `tests/integration/test_bare_url_save.py`. Verify:
      `scripts/dev-tests.sh tests/integration/test_bare_url_save.py -k status`
- [x] T019 [US1] Add the second save site: `open_task_editor._save` in `src/choom/tui/edit_screen.py`
      calls `format_bare_urls` **before** `set_task_body`, and returns a `SaveResult` carrying the
      converted text and the conversions so the pane's existing re-sync handles both editors
      identically. **The conversion must not go inside `set_task_body`** — it has two callers and the
      other is reconcile-on-open, so putting it there would convert on *open* and violate FR-016. Cover
      a task-body save converting in `tests/integration/test_bare_url_save.py`. Verify:
      `scripts/dev-tests.sh tests/integration/test_bare_url_save.py -k task_body`

**Checkpoint**: bare URLs convert on both save paths, the buffer and cursor behave, the status line
reports. US1 is demonstrable on its own.

---

## Phase 4: User Story 2 — nothing else in the file moves (Priority: P1)

**Goal**: prove the exclusions hold as a composed whole, not just mask by mask.

**Independent Test**: one document carrying a URL in every excluded context, saved once, differs only
in `updated:`.

**Note on independence**: US1–US3 are independently *testable* but not independently *shippable* — they
are three properties of one transform, and it is not safe to ship with any of them missing. Recorded
here rather than implied.

- [x] T020 [US2] Add the trailing-boundary trim to `src/choom/core/links.py`: repeatedly drop a final
      character in `. , : ; ! ? ' " * _ ~`, and drop a final `)` **while the candidate contains more
      `)` than `(`**. The paren rule is what separates "the URL owns this parenthesis" from "the
      sentence does", and counting is exact in both directions. This aligns with the GFM autolink
      extension, which matters because markdown-it's linkify is already running in choom's preview — a
      boundary that disagreed would underline a different span before and after a save. Verify:
      `scripts/dev-tests.sh tests/unit/test_bare_url_format.py -k trim`
- [x] T021 [US2] Encode **all 25 rows** of Corpus A from
      [contracts/text-format.md](./contracts/text-format.md) as a table-driven test in
      `tests/unit/test_bare_url_format.py`, asserting the **exact expected output string** for each.
      Not a representative handful — the corpus is the evidence this feature is safe, and it was run to
      0 failures against a prototype before the plan was written. Includes the boundary cases US3
      owns: trailing `.` `,` `:` `;` `!` `?`, quotes, `**` emphasis, wrapping parentheses, balanced
      parentheses inside the URL, `...`, `).`, a trailing slash that must be kept, table cells, and
      blockquotes. Verify: `scripts/dev-tests.sh tests/unit/test_bare_url_format.py -k corpus_a`
- [x] T022 [US2] Encode **all 18 rows** of Corpus B from
      [contracts/text-format.md](./contracts/text-format.md) as a table-driven test in
      `tests/unit/test_bare_url_format.py`, asserting each input is returned **byte-identical**. Do not
      reduce it to a sample; each row is a distinct mask, and the four `_LINK_RE` gaps from the top of
      this file are in here. Verify: `scripts/dev-tests.sh tests/unit/test_bare_url_format.py -k corpus_b`
- [x] T023 [US2] Encode **all 15 rows** of Corpus C (adversarial) from
      [contracts/text-format.md](./contracts/text-format.md) in `tests/unit/test_bare_url_format.py`,
      asserting the exact result for each. These are built to break the masks rather than exercise the
      happy path: angle-wrapped destinations containing parens and spaces, an unbalanced paren inside
      an angle destination (mask 6 backstopping mask 5), `[[wiki]]` followed by a URL, an unclosed `[`
      that must not swallow the rest of the file, a stray `]` or `(` in prose before a URL, a code span
      containing a bracket followed by a real URL, two links on one line with a URL between them, an
      image followed by a URL, a URL sharing a line with a task metadata comment, a URL in a fence info
      string, and a four-space-indented line (which **does** convert — the accepted limitation in
      research R8, pinned here so it is deliberate rather than accidental). Verify:
      `scripts/dev-tests.sh tests/unit/test_bare_url_format.py -k adversarial`
- [x] T024 [US2] **The most important test in this feature.** Assert three-pass idempotency in
      `tests/unit/test_bare_url_format.py`: for **every** input in Corpus A,
      `f(x) == f(f(x)) == f(f(f(x)))`, byte for byte. **Three passes, not two, and do not let anyone
      later "simplify" it to two** — a defect that is stable at pass 2 but not pass 3 is exactly the
      compounding shape this guards against. Put the failure mode in the test's docstring: had the link
      mask covered only the destination and not the link text, pass 2 would yield `[[U](U)](U)` and
      pass 3 `[[[U](U)](U)](U)` — the user's file degrading a little on every save, silently, forever.
      Every subsequent save re-runs this transform over already-converted text, which is why
      idempotency is the safety property and not a nicety. Verify:
      `scripts/dev-tests.sh tests/unit/test_bare_url_format.py -k idempotent`
- [x] T025 [US2] **Pin the newline-count invariant** in `tests/unit/test_bare_url_format.py`: for a
      whole document containing frontmatter, a bare URL, a record link, a task mirror, a fenced code
      block, and a URL with balanced parens, assert `original.count("\n") == converted.count("\n")` and
      the same for `\r`. The probe behind the plan measured 19 before and 19 after. This is not
      cosmetic: it is what keeps `heal_text`'s warning line numbers, `parse_tasks`'s task line numbers,
      and the editor's cursor row valid across a conversion, and every one of those would break subtly
      and far from the cause if a mask or an edit ever inserted a line. Verify:
      `scripts/dev-tests.sh tests/unit/test_bare_url_format.py -k newline_count`
- [x] T026 [US2] Add the whole-document integration assertions to
      `tests/integration/test_bare_url_save.py`: after saving a document like T025's, the frontmatter
      still parses with an unchanged title, `find_links` returns an identical set (same lines, ids,
      paths), `find_mirrors` returns an identical set, and a second save reports zero conversions.
      Verify: `scripts/dev-tests.sh tests/integration/test_bare_url_save.py -k whole_document`

**Checkpoint**: the exclusions hold composed, the transform is provably idempotent, and no line number
in any document has moved.

---

## Phase 5: User Story 3 — punctuation stays out of the link (Priority: P1)

**Goal**: the boundary is exactly right on the most common line shape there is.

**Independent Test**: the boundary corpus, asserting exact output strings.

- [x] T027 [US3] Confirm the boundary rows of Corpus A are all present and passing from T021 — a URL
      ending a sentence, one followed by a comma, one in parentheses, one whose own path contains
      balanced parens, one in quotes, one followed by `**`, `https://example.com/a).`,
      `https://example.com/a...`, and `(see https://example.com/a).` — and that
      `https://example.com/a?q=1&r=2#frag` keeps its query and fragment, since `?`, `&`, and `#` are
      part of a URL rather than punctuation trailing it. If any is missing from T021, add it there
      rather than starting a second corpus. Verify:
      `scripts/dev-tests.sh tests/unit/test_bare_url_format.py -k corpus_a`
- [x] T028 [US3] Add a regression case that would have caught the bug the prototype actually hit:
      `**https://example.com/a**` must convert with both asterisk pairs outside the link. The first
      corpus run failed this because `*` was missing from the leading-boundary set. Keep it named so
      the reason survives. Verify:
      `scripts/dev-tests.sh tests/unit/test_bare_url_format.py -k emphasis`

**Checkpoint**: the classic failure mode of this feature is covered by named tests.

---

## Phase 6: User Story 4 — only a human save converts (Priority: P2)

**Goal**: prove that nothing choom does on the user's behalf converts anything.

**Independent Test**: write a bare URL to a file outside choom; confirm every non-save path leaves it
alone and the next editor save converts it.

- [x] T029 [US4] Add to `tests/integration/test_bare_url_save.py`: **opening** a document whose body
      contains a bare URL, with no save, leaves the file byte-identical — `reconcile_on_open` and
      `mirrors.write_document` must not convert. Then **opening a task** whose body contains a bare
      URL, with no save, likewise leaves `tasks.md` byte-identical. This second case is the test that
      keeps T019's placement honest: if someone later moves the conversion into `set_task_body`, this
      is what fails. Verify: `scripts/dev-tests.sh tests/integration/test_bare_url_save.py -k on_open`
- [x] T030 [US4] [P] Add to `tests/integration/test_bare_url_save.py`: `choom links heal` and
      `choom links check` over a workspace full of bare URLs convert zero of them and write zero files
      that had no stale record link. A pass that rewrote prose workspace-wide would show a colleague on
      a synced folder a wave of modifications nobody made — the outcome the 008 link contract records
      as rejected outright. Verify:
      `scripts/dev-tests.sh tests/integration/test_bare_url_save.py -k heal_check`
- [x] T031 [US4] [P] Add to `tests/integration/test_bare_url_save.py`: `check_links` reports an
      identical set of stale and dead links before and after every document in a workspace has been
      opened and saved once (SC-005). A converted link carries a URL scheme, so `_link_from_match`
      declines it and it never becomes a record link, a Links-pane row, or a mirror. Verify:
      `scripts/dev-tests.sh tests/integration/test_bare_url_save.py -k links_unchanged`
- [x] T032 [US4] [P] Add to `tests/integration/test_bare_url_save.py`: a task description containing a
      bare URL is **not** converted, via `choom task add` **and** via `/task` in the editor — the same
      result from both surfaces (FR-018). The reason belongs in the test's docstring: `/task` turns the
      description into the *link text* of a mirror, and a link nested inside link text is not valid
      CommonMark, so the TUI physically cannot honour a converted description and the CLI must not
      either. A task's indented **body** does convert (already covered by T019). Verify:
      `scripts/dev-tests.sh tests/integration/test_bare_url_save.py -k task_description`
- [x] T033 [US4] [P] Add to `tests/integration/test_bare_url_save.py`: `choom note new` and
      `choom meeting new` convert nothing, because `create_document` writes frontmatter and no body
      (FR-017). Verify: `scripts/dev-tests.sh tests/integration/test_bare_url_save.py -k create`

**Checkpoint**: the write-path boundary from FR-015–FR-019 is enforced by tests rather than by the call
graph.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T034 [P] Confirm the preview pane is unaffected: a converted link still opens in the browser,
      because `resolve_href` returns `None` for a scheme-carrying href and the handler falls through to
      `app.open_url` (FR-022). A bare URL was already clickable there via markdown-it's linkify; this
      feature changes the file, not the click. Verify by inspection of
      `src/choom/tui/preview_screen.py` and `src/choom/tui/list_screen.py` — neither should appear in
      the diff
- [x] T035 [P] Confirm no other documentation needs amending: `docs/REQUIREMENTS.md` is unchanged
      because this feature adds no exit code, no frontmatter key, no id-scheme change, and no layout
      change; `AGENTS.md.tmpl` is unchanged per FR-029, because an assistant does not need to be told
      about a repair that happens after it has finished writing, and the file's content rule bites well
      before its ~100-line backstop does
- [x] T036 **Leave README.md alone — this is a deliberate skip, not an oversight.** Per CLAUDE.md the
      README feature list describes the *released* version and closes with "Everything above has landed
      on `main` as of vX.Y.Z"; `/release` folds a version's user-visible changes in when it cuts that
      version. Adding or extending a bullet for this unreleased work — including appending a sentence
      to an existing editor or links bullet, which is the same error in a harder-to-spot form — would
      promise behaviour a reader installing from PyPI does not get. The feature is recorded in this
      feature's own `specs/018-automatic-link-detection/` artifacts instead, which is what a
      "document it" task is actually for at implementation time. Verify: no `README.md` edit appears in
      `git diff`
- [x] T037 Verify cross-platform behaviour: a workspace path with spaces and non-ASCII characters, and
      a URL containing non-ASCII characters, both survive a save verbatim. Offsets are character
      offsets into a Python `str`, so a multi-byte URL cannot be split mid-character; add a case that
      would catch it if the implementation ever moved to byte offsets. Also confirm a CRLF document
      round-trips — `load_for_edit` normalises to LF and `_apply_line_ending_policy` restores the
      convention, so **no new source should be required**; if this needs production code, the
      conversion is doing something it should not. Extend
      `tests/integration/test_unicode_paths.py` rather than creating a new file. Verify:
      `scripts/dev-tests.sh tests/integration/test_unicode_paths.py`
- [ ] T038 Run [quickstart.md](./quickstart.md) end to end by hand against a scratch workspace under
      `/tmp`, particularly §2 (idempotency — "if this fails, stop"), §4 (frontmatter survives), §5 (a
      real save showing the buffer update, the status line, and a second save printing nothing), and §6
      (the paths that must not convert)
  - **Partially run, left unticked.** §1–4, §6, and §7 were run against a real scratch workspace
    with the actual `choom` binary and confirmed to match every documented expectation verbatim
    (the frontmatter probe reported zero conversions and a parsing document; `links check`/`heal`
    changed nothing; `links check --json` was byte-identical before and after a workspace-wide
    save). §5's assertions (buffer updates immediately, the status line names the count, a second
    save prints nothing, the cursor does not land inside a just-wrapped URL) are covered by the
    automated `pilot`-driven tests in `tests/integration/test_bare_url_save.py`
    (`test_cursor_does_not_land_inside_a_url_that_was_just_wrapped`,
    `test_status_line_reports_the_conversion_count_only_when_nonzero`,
    `test_status_line_uses_singular_for_exactly_one_conversion`), which drive the real
    `EditorPane` through `ctrl+o` exactly as a keystroke would. What remains undone is §8 —
    clicking a converted link in the preview pane and watching a browser open — which needs a
    real pointing device and a real browser and cannot be performed headlessly. Left unticked
    rather than fabricated.
- [ ] T039 Verify the TUI on the target terminals in `docs/REQUIREMENTS.md` — confirm the status
      message renders without breaking the status bar at 80 columns, and that the cursor lands sensibly
      after a save that converted a URL on the cursor's own line
  - **Deferred.** This needs each target terminal (Windows Terminal, iTerm2, macOS Terminal, PuTTY,
    tmux) running interactively — a visual, terminal-hosted check this session cannot perform
    headlessly, on the same terms features 016 and 017 deferred their own equivalents. Left
    unticked rather than fabricated. Deferred to the pre-release verification gate the
    constitution's Development Workflow section already requires ("TUI changes MUST be verified
    before release on the target terminals listed in `docs/REQUIREMENTS.md`") — a release-time
    activity, not a per-PR one.
- [x] T040 Run the full gate from the repository root: `scripts/dev-tests.sh` plus
      `uv run ruff format --check . && uv run ruff check . && uv run mypy src`. Confirm green; confirm
      ruff's TID251 ban still passes for `core` (the new code imports only `re` and its own module's
      helpers); confirm `tests/unit/test_core_imports.py` passes including the new exports; confirm
      `tests/integration/test_link_heal.py` and `tests/integration/test_delete_mirrors.py` still pass
      unchanged, since both exercise `save_buffer` and are the existing tests most likely to notice an
      unintended change to the save path; and confirm **`src/choom/cli/` has no diff at all**, which is
      the structural form of the plan's Principle II claim

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — **blocks every user story**
- **US1 (Phase 3)**: depends on Phase 2. T013 also depends on T020 (the trim), which sits in Phase 4;
  either do T020 early or stub the trim as identity and finish T013 after it. This is the one
  cross-phase edge in the list and it is called out in T013 rather than left to be discovered
- **US2 (Phase 4)**: depends on US1
- **US3 (Phase 5)**: depends on T020 and T021 from US2
- **US4 (Phase 6)**: depends on US1
- **Polish (Phase 7)**: depends on all of the above

### Within Phase 2

T005, T006, T008, and T009 are `[P]` — four different mask functions, four different test blocks.
**T007 is not parallel**: it is the one to do carefully and alone, and T008 backstops it, so T008 lands
after it in review order even though the files do not conflict.

### Parallel opportunities

- Phase 2: T005, T006, T008, T009 together
- Phase 6: T030, T031, T032, T033 together — four independent cases in one new test file
- Phase 7: T034, T035 together

### Suggested MVP

Phases 1–4. US1 alone converts URLs but is **not safe to ship without US2** — the exclusions and the
idempotency proof are what make the rewrite permissible at all. US3 is a subset of US2's corpus. US4 is
a boundary proof rather than new behaviour and can follow.

---

## Notes

- **No README task exists, deliberately.** The tasks template would generate one; it is omitted per
  CLAUDE.md and the reason is recorded as T036 so a reviewer sees the decision rather than a gap.
  `/release` owns the README.
- **No trailing test phase, deliberately.** Every behaviour task above carries its own tests, per
  Principle VI and the Development Workflow gate. There is nothing to "add tests for" at the end.
- **No `contract/` test task.** This feature adds no CLI command, flag, `--json` key, or exit code.
  T040 checks that `src/choom/cli/` has no diff at all.
- **No `performance/` test task.** No budget to protect: the pass is one scan of a string already in
  memory with no file read. Note also that `tests/performance/` is being split into its own CI job
  under issue #84, so this feature adds nothing to it.
- **Three mistakes to watch for, each called out in the task text where it would be made**:
  reusing `_LINK_RE` as the mask (T007 — it misses four forms and would corrupt files); masking only a
  link's destination instead of both halves (T007/T024 — it breaks idempotency and compounds per save);
  and putting the conversion inside `set_task_body` (T019/T029 — it has a reconcile-on-open caller and
  would convert on open).
- **One accepted limitation, already argued in the plan's Principle IV gate**: a top-level four-space
  indented code block is not masked, so a URL in one converts. Masking four-space indents would break
  task bodies — indented prose beneath a checkbox, the dominant indentation in a choom vault — and
  telling the two apart needs a real block parser. `heal_text` has the identical gap today. T023
  includes the case so the behaviour is pinned rather than accidental.
