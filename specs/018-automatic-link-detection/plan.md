# Implementation Plan: Bare URLs Become Markdown Links on Save

**Branch**: `018-automatic-link-detection` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/018-automatic-link-detection/spec.md`

## Summary

When the user saves in choom's editor, a bare `http://` or `https://` URL in the document body
becomes `[<url>](<url>)`.

The feature is **one pure function in `choom.core.links`** plus two call sites on the user-save path.
Core decides what a bare URL is and what it becomes; the adapter decides only when to ask and how to
keep the cursor sensible afterwards.

```python
def format_bare_urls(text: str) -> tuple[str, tuple[UrlConversion, ...]]: ...
```

No `Workspace`, no `Path`, no filesystem, no network, no terminal. A string goes in and a string
comes out, alongside the edits that produced it.

Four decisions carry the design:

1. **The exclusion mask is new and deliberately wider than `_LINK_RE`.** The existing scanner misses
   four link forms — an unescaped-paren destination, an image, a reference definition, an autolink
   (R1, probed directly). Reusing it as a mask would wrap a second `[…](…)` around a destination it
   failed to see. `_mask_fences` and `_mask_code_spans` are reused verbatim (FR-031); links, images,
   autolinks, HTML tags, comments, and frontmatter get a purpose-built mask. The two patterns fail in
   opposite directions — a scanner that misses a link heals nothing, a mask that misses a link
   corrupts a file — and that is why one regex cannot serve both.
2. **Idempotency is structural and is the property the suite leans on hardest.** Mask 5 blanks the
   *whole* `[text](dest)` span, both halves. Both copies of the URL in the output are therefore
   invisible on the next pass, zero candidates are found, and the text is returned unchanged. Had the
   mask covered only the destination, the second save would produce `[[U](U)](U)` and the third
   `[[[U](U)](U)](U)` — silent corruption compounding once per save. Every corpus case is asserted
   through **three** passes (R6).
3. **Frontmatter is masked, and the evidence is a note that disappears.** `title: [https://x](https://x)`
   makes `_parse_document` return `malformed_yaml` with `doc=None` — an unquoted YAML scalar opening
   with `[` is a flow sequence — and the note drops out of every list choom draws. Reproduced (R3).
   This is stricter than `heal_text`, deliberately.
4. **Nothing converts except a save the user performed.** `save_buffer` has exactly one `src/` caller
   and *is* the user-save primitive, so the hook lives inside it. `set_task_body` has two callers, one
   of which is reconcile-on-open, so its hook lives at the adapter's save site instead (R9). An
   integration test pins that opening a task converts nothing.

**No new dependency, no new module, no new setting, no new CLI surface, no new binding.**
`linkify-it-py` is installed transitively via Textual and is explicitly rejected (R11).

Verification before writing this plan: a faithful prototype of the algorithm passed a 25-case
conversion corpus, an 18-case must-not-change corpus, a 15-case adversarial corpus, and a
whole-document probe — **0 failures, all idempotent through three passes**, with record links,
mirrors, line count, and frontmatter parsing identical before and after.

## Technical Context

**Language/Version**: Python 3.11+ (CI runs 3.11 and 3.13)

**Primary Dependencies**: `textual==8.2.8`, `PyYAML==6.0.3`, unchanged. **No new dependency.** The
detection uses `re` from the standard library. The adapter's cursor mapping calls
`textual.document._document.Document.get_index_from_location` / `get_location_from_index`, both
confirmed present on the pinned version.

**Storage**: Markdown files only. One file is written per save, through the existing
`write_text_atomic`. No index, no cache, no per-user state, nothing persisted about a conversion.

**Testing**: `pytest` via `scripts/dev-tests.sh`. Two new `tests/unit/` files (the three corpora; the
cursor arithmetic) and one new `tests/integration/` file (save paths, and the paths that must not
convert). No `contract/` or `performance/` change — see research R13.

**Target Platform**: macOS, Linux, Windows. Verified before release on the terminals in
`docs/REQUIREMENTS.md`.

**Project Type**: Single project — `src/choom/{core,cli,tui}` over `tests/{unit,contract,integration}`.

**Performance Goals**: seven length-preserving passes plus one regex scan over a string already in
memory, once per save. No file read, nothing per-keystroke, nothing per-frame. No budget to protect,
so no performance test (SC-007).

**Constraints**: The transform may only ever *wrap* — never edit, reorder, re-encode, or drop a
character of a URL, and never insert a newline. Every excluded context in FR-005–FR-012a must survive
byte-identical. The operation must be exactly idempotent.

**Scale/Scope**: roughly 110 lines of new source in `src/choom/core/links.py`, one frozen dataclass in
`core/models.py`, one field on `SaveResult`, three lines in `core/editing.py`, and roughly 25 lines
across `tui/edit_screen.py` for the second call site, the cursor mapping, and the status message.

No NEEDS CLARIFICATION remain; every open question was resolved in [research.md](./research.md)
against the installed source.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution v2.1.0. **Result: all gates PASS. Complexity Tracking is empty because
no gate failed** — not because the table was skipped.

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `choom.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. **List the `core` functions this feature's reads and writes go through**, and justify any assembly done in an adapter that an existing `core` function already performs. | **PASS.** *New in core*: `format_bare_urls(text: str) -> tuple[str, tuple[UrlConversion, ...]]` and `map_cursor_offset(conversions, offset) -> int` in `src/choom/core/links.py`, plus the frozen `UrlConversion` dataclass in `core/models.py`. `format_bare_urls` takes **no `Workspace` and no `Path`** — unlike `heal_text`, it resolves nothing, because a URL is self-describing — and imports only `re` plus two private helpers from its own module. Neither function touches a stream, a widget, or an event loop, so Ruff's TID251 ban on `argparse`/`textual`/`rich` inside `core` and `tests/unit/test_core_imports.py`'s `sys.stdout` check both still hold. *Reads*: none — the function is closed over its argument. *Writes*: `editing.save_buffer` (unchanged primitive, one new line in its body) and `tasks.set_task_body` (entirely unchanged), both existing. **No new write primitive, no new module.** *Reuse*: `_mask_fences`, `_mask_code_spans`, and `_render_destination` are reused verbatim from `links.py`; a second notion of "what counts as code" or of how a destination is escaped is exactly what FR-031 exists to prevent, and is why this lands in `links.py` rather than a new file — the module's own docstring already argues that splitting this grammar across files is how a byte-preservation guarantee gets quietly broken. **Answering the second half of the gate — is logic being left in an adapter?** Four candidate decisions were audited. *What counts as a bare URL*, *where it ends*, *what it becomes*, and *how a cursor offset maps across the edits* are all in core. What remains in `EditorPane` is genuinely adapter work: reading `cursor_location`, converting row/column to an offset with Textual's own API, and rendering a status string. The adapter computes nothing about what to convert; the assertion `editor.text == result.saved_text` already in `_save` fails the suite if it ever starts to. One deliberate exception is argued in R9 and re-stated under gate II: the *sequencing* of the task-body call site sits in the adapter because the alternative would convert on open. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS, and the parity question is answered rather than waived.** The behaviour is "saving an edited markdown body converts bare URLs in it". **The CLI has no peer for it by constitutional design**: Principle II's first bullet forbids the CLI from opening an editor, so there is no CLI gesture that saves an edited body. That is not a gap this feature introduces. The CLI's two write surfaces were both checked and both are consistent: `create_document` writes frontmatter and **no body**, so there is nothing to convert (FR-017, verified in `core/documents.py`); and `choom task add "<description>"` is excluded — **identically to the TUI's `/task`**, which is what closes the divergence. The reason is a hard one rather than a preference: `/task` turns the description into the *link text* of a mirror, `- [ ] [description](../tasks.md#task_a1b2)`, and a link nested inside link text is not valid CommonMark. The TUI physically cannot honour a converted description, so the CLI must not either, or the same words typed in two places would produce two different files. A task's indented **body** does convert on both counts, because it is prose in an editor buffer and there is no CLI path that edits one. **No CLI change at all**: no command, no flag, no `--json` key, no exit code. Nothing added here prompts, blocks, colorizes, or writes to a stream. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. Any new setting has a sensible default. Date stays the only axis the directory tree encodes; `type` never becomes a directory. | **PASS.** No index, database, or cache: a `UrlConversion` lives for the length of one save and is never persisted, serialised, or written anywhere. No new external binary. **No new third-party dependency, and one was actively refused**: `linkify-it-py==2.1.0` is already importable because `textual==8.2.8` requires `markdown-it-py[linkify]`, which makes taking it the path of least resistance. Rejected on three independent grounds (R11) — it would be an *undeclared* dependency that breaks silently the day Textual drops the extra; its matching rules are the wrong rules (`www.` hosts, bare emails, fuzzy TLDs — all out of scope, and it would put choom's scope boundary in a third party's release notes); and it solves a different problem, since it has no notion of a code fence, an HTML comment, or frontmatter, so every Principle IV guarantee here would still have to be built around it. The cost of doing without is one 30-line function. **No new setting**, so the sensible-default rule is satisfied by there being nothing to configure — and spec.md §"Why there is no setting" argues that positively rather than by omission: the rewrite has no losing side, choom already rewrites on save twice with no opt-out (`updated:` stamping and link healing, both of which change *more*), and a setting could only be found after the surprise it would have prevented. Directory layout untouched — no file is created, moved, or renamed. |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. No user file is moved to match its partition, and no tag can be silently dropped. | **PASS — the dominant gate, so every mechanism is named and each was verified, not asserted.** *Never lose a character*: the transform only ever wraps. Its output is `original[:start] + "[U](D)" + original[end:]` where `U` is the matched slice reproduced byte-for-byte and `D` is `U` optionally angle-wrapped. Nothing is deleted, re-encoded, case-folded, or normalised, so the edit has an exact inverse. *Never lose a line*: no mask and no edit inserts or removes a newline — masks blank to spaces and preserve `\n`/`\r`, the idiom `_mask_fences` already uses. Verified on the whole-document probe (19 newlines before, 19 after), which is also what keeps `heal_text`'s warning line numbers, `parse_tasks`'s line numbers, and the cursor's row valid across a conversion. *Never corrupt frontmatter*: masked first and unconditionally, on evidence — `title: [https://x](https://x)` yields `doc=None, malformed_yaml` and the note vanishes from every list (R3). *Never break an existing link*: the mask is a deliberate **superset** of the link grammar, because `_LINK_RE` provably misses four forms (R1); a mask must never be a subset of what it guards. *Never compound*: idempotency is structural — mask 5 covers both halves of a link, so the output is inert on every subsequent pass — and is asserted through three passes, not two (R6). *Skips malformed input without raising*: `format_bare_urls` never raises (FR-032); an unterminated comment or unclosed fence masks to end-of-file, which converts *less*, the safe direction. *`created`/`updated`*: untouched — `save_buffer` still stamps `updated` and never writes `created`, and the conversion runs before the stamp so the bytes reported and the bytes written are the same (R10). *Valid CommonMark*: the output is an ordinary inline link, and the character class excludes exactly the characters (` <>[]`) that could make either slot unparseable, so the angle-wrapped form can never itself fail (R7). *No file moved, no tag dropped*: no path is constructed and no tag is parsed anywhere in this feature. **One accepted limitation, recorded rather than hidden**: a top-level four-space-indented code block is not masked, so a URL in one converts. Masking four-space indents would break task bodies — indented prose beneath a checkbox, the dominant indentation in a choom vault and the case FR-015 most needs — and distinguishing the two needs a real block parser whose bugs would be data-shaped. The residual harm is cosmetic and reversible, and `heal_text` has the identical gap today (R8). |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; `ctrl+c` is never bound to anything, `ctrl+q` quits immediately unless something is dirty (in which case it MAY raise the existing confirmation); no non-`ctrl` modifier. | **PASS.** **No new binding, no new screen, no new state, no new dialog** — the feature rides `ctrl+s`, which already exists and is already in the editor footer. Nothing to add to `EDIT_HELP`, so `tests/unit/test_footer_bindings.py` needs no change and no key is hidden. **No confirmation is added, and that is the correct reading of the rule rather than an omission**: a prompt on every save would fire overwhelmingly when nothing was converted, which is precisely the reflex-dismissal failure the principle describes, and it would spend the twenty-second budget the principle exists to protect. What the user gets instead is *after*-the-fact and free: the converted text appears in the buffer the instant the save completes (FR-026, riding the buffer re-sync `_save` already performs for the `updated:` stamp), plus a status line naming the count **only when the count is non-zero** (FR-025). `ctrl+c` is not bound, inspected, or relied on. `ctrl+q` is untouched, including issue #64's dirty-buffer confirmation. No non-`ctrl` modifier anywhere. The one interaction detail this feature does owe the user is cursor stability, handled in core (R12) so the editor cannot drop the caret into the middle of a URL it just wrapped. |
| VI | Type hints and docstrings on new public `core` functions; test coverage is risk-based (chosen for what could break, not one test per acceptance scenario) and placed in the right layer; no test depends on the wall clock. | **PASS.** Both new public core functions carry full type hints and docstrings stating what they do and what they raise — `format_bare_urls` and `map_cursor_offset` both raise nothing, stated explicitly, since "never raises" is a load-bearing contract here (FR-032). Both are added to `core/__init__.py`'s `__all__`, which `tests/unit/test_core_imports.py` already checks mechanically. Coverage is chosen by what can plausibly break, not generated from the spec's 24 acceptance scenarios (R13): `unit/` carries almost all of it, because every guarantee in this feature is decidable against a string literal — the conversion corpus, the must-not-change corpus, the three-pass idempotency corpus, and the cursor arithmetic. `integration/` gets one file for exactly the boundaries a unit test cannot see: a document save converts and stamps in one write, a task-body save converts, **reconcile-on-open does not**, `links heal`/`check` convert nothing, and `check_links` reports an identical set before and after a workspace-wide save pass. No `contract/` change (no CLI surface) and no `performance/` change (no budget). **No test depends on the wall clock**: nothing in this feature reads a clock, and the only dates involved are inert frontmatter strings in fixtures; the one clock in the save path is `save_buffer`'s existing injectable `now`. |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS.** No elevation, no network, no subprocess — and the network point is load-bearing rather than incidental: fetching a page title for link text was considered and rejected in spec.md's Out of Scope precisely because no choom operation may require network access. No path is constructed, joined, or opened by the new code, so the 260-character Windows budget is untouched; `format_bare_urls` does not even take a `Path`. Spaces and non-ASCII survive verbatim — the URL is sliced out of the string by character offset and re-emitted unchanged, never slugified or re-encoded, and offsets are character offsets into a Python `str`, so a multi-byte URL cannot be split mid-character. Line endings are untouched by construction (masks preserve `\r`/`\n`; edits insert neither), and `_apply_line_ending_policy` still restores a CRLF file's convention on write, so a Windows-authored document round-trips exactly as it does today. No per-user state is created or read. |

**Post-Phase-1 re-check**: re-evaluated after research.md, data-model.md, contracts/, and quickstart.md
were written. No gate changed status. Phase 1 added no module, no dependency, no setting, no binding,
and no CLI surface. Two additive changes surfaced during design and were both re-checked: the
`UrlConversion` dataclass (gate I — a pure value returned by a core function, never persisted, which
is what lets the cursor mapping stay in core rather than being re-derived in the widget) and one new
field on `SaveResult` carrying the conversions to the adapter (gate I and gate II — `SaveResult` is
core's existing return type for a save, the field is additive so no consumer breaks, and it is not part
of any `--json` schema, so Principle II's stability rule is not engaged). Complexity Tracking remains
empty.

## Project Structure

### Documentation (this feature)

```text
specs/018-automatic-link-detection/
├── spec.md                  # Approved
├── plan.md                  # This file
├── research.md              # Phase 0 — R1..R13
├── data-model.md            # Phase 1
├── quickstart.md            # Phase 1
├── contracts/
│   ├── core-api.md          # format_bare_urls, map_cursor_offset, SaveResult
│   ├── text-format.md       # The on-disk contract: the three corpora
│   └── tui.md               # Save-path behaviour, status line, cursor
└── tasks.md                 # Phase 2 — NOT created by /speckit-plan
```

### Source Code (repository root)

```text
src/choom/
├── core/
│   ├── links.py             # CHANGED: + format_bare_urls, + map_cursor_offset,
│   │                        #          + 5 private masks; _mask_fences,
│   │                        #          _mask_code_spans, _render_destination reused
│   ├── models.py            # CHANGED: + UrlConversion; + SaveResult.conversions
│   ├── editing.py           # CHANGED: save_buffer calls format_bare_urls
│   │                        #          between heal_text and stamp_updated
│   ├── tasks.py             # UNCHANGED (set_task_body must not convert on open)
│   ├── mirrors.py           # UNCHANGED (write_document is the sync path)
│   └── __init__.py          # CHANGED: export the two new names
├── tui/
│   └── edit_screen.py       # CHANGED: open_task_editor._save converts before
│                            #          set_task_body; _save maps the cursor and
│                            #          renders the count
└── cli/                     # UNCHANGED — no command, flag, --json key, or exit code

tests/
├── unit/
│   ├── test_bare_url_format.py    # NEW: the three corpora from contracts/text-format.md
│   └── test_url_cursor_map.py     # NEW: cursor arithmetic
└── integration/
    └── test_bare_url_save.py      # NEW: save paths convert; open/heal/check do not
```

**Structure Decision**: single project, unchanged. The new logic lands in `src/choom/core/links.py`
rather than a new module, for the reason that file's own docstring gives — the scanner, the resolver,
the healer, and now the formatter are views of one grammar, and splitting them across files is how a
byte-preservation guarantee gets quietly broken. `core/tasks.py` and `core/mirrors.py` are explicitly
untouched, which is what keeps FR-016's "no write choom performs on the user's behalf converts
anything" true structurally rather than by convention.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No gate failed. This table is intentionally empty.

For the record, the three places this feature could have grown complexity and did not:

| Rejected addition | Why it was tempting | Why it was refused |
|---|---|---|
| `linkify-it-py` for detection | Already installed transitively via `textual`; zero apparent cost | Undeclared dependency; wrong matching rules (`www.`, emails); no notion of fences, comments, or frontmatter, so every Principle IV guarantee would still need building (R11) |
| A `convert_urls: bool` flag on `set_task_body` | One writer, one switch, symmetric with `save_buffer` | A boolean that must be `True` at exactly one of two call sites is a trap whose safe default hides the bug; the constitution prefers an explicit branch (R9) |
| An indented-code-block mask | Would close the last exclusion gap | Needs a real block parser to tell code from a task body's indented prose, and would disable the feature for task bodies — the case it most serves (R8) |
