# Phase 0 Research: 001-meeting-notes

**Date**: 2026-07-28
**Feature**: [spec.md](./spec.md)

All unknowns from Technical Context are resolved below. Four were architecture forks put to the
requirements owner and answered directly; the rest were resolved by measurement or by reading
current library documentation.

---

## R1. Markdown rendering in the terminal

**Decision**: Use `textual.widgets.Markdown`. Do not install any markdown plugin package.

**Rationale**: The phrase "Textual and its markdown plugin" in the feature request refers to a
package (`textual-markdown`) that no longer exists independently — it was folded into Textual core
at v0.11.0. Current Textual ships both `Markdown` and `MarkdownViewer` in `textual.widgets`, with
rendering powered by `markdown-it-py` using a GFM-like parser by default. Measured against a clean
install of Textual 8.2.8, `markdown-it-py 4.2.0`, `mdit-py-plugins`, and `linkify-it-py` arrive as
transitive dependencies, so markdown preview costs nothing beyond Textual itself.

**`Markdown` over `MarkdownViewer`**: `MarkdownViewer` wraps `Markdown` with a table-of-contents
sidebar and browser-like navigation. The spec (FR-034) requires exactly one screen made of a list
and a preview pane; a second navigation chrome inside the preview works against that. `Markdown`
also lets us own scrolling and key handling rather than inheriting the viewer's.

**Alternatives considered**:
- `MarkdownViewer` — rejected as above; revisit if users ask for in-document navigation.
- `rich.markdown.Markdown` rendered into a `Static` — loses Textual's link handling and per-block
  widget model for tables and code, and gains nothing.

**Verified against**: Textual documentation (widgets/markdown, widgets/markdown_viewer), retrieved
2026-07-28.

---

## R2. Frontmatter parsing and writing

**Decision** (requirements owner): Read with `yaml.safe_load`. **Write with a deterministic
hand-written emitter, not `yaml.safe_dump`.**

**Rationale**: The read and write paths have opposite requirements and should not share a
mechanism.

*Reading* must survive anything a human types into a file that endpaper does not control.
PyYAML is battle-tested at exactly that, and hand-rolling a parser for arbitrary hand-edited input
is where Principle IV gets violated by accident.

*Writing* must be byte-deterministic. FR-018 fixes the field set at exactly six, and US2 scenario 2
requires the CLI and TUI create paths to produce identical output. `safe_dump` gives us none of
that for free: it sorts keys alphabetically, chooses its own quoting, and line-wraps long values at
80 columns — so a long title would wrap and no longer round-trip. A ~25-line emitter that writes six
known fields in a fixed order with fixed quoting is both simpler and more predictable than
configuring `safe_dump` into submission.

**Required normalization on the read path.** PyYAML implements YAML 1.1, which coerces in two ways
that matter here:

| Input | `safe_load` gives | We need |
|---|---|---|
| `tags: [no, on, off, y]` | `[False, True, False, True]` | `["no", "on", "off", "y"]` |
| `created: 2026-07-28T09:14:00` | `datetime.datetime` | ISO string |
| `title: 3.10` | `float` | `"3.10"` |

The "Norway problem" (first row) is a real hazard for a free-form tag vocabulary. The reader
therefore coerces every scalar back to `str` before it reaches a record, and the writer always
quotes tag and title scalars so endpaper-written files never round-trip into a boolean.

**Reader contract** (Principle IV): unknown key, missing required key, unparseable YAML, or a
non-list `tags` all produce the same outcome — log a warning naming the file, skip that file, and
continue. The offending file is never rewritten and never repaired in place.

**Alternatives considered**:
- Hand-rolled reader — recommended by the planner for zero dependencies and no coercion, but not
  chosen. Rejected trade-off is accepted: we take one dependency and a normalization layer in
  exchange for not owning a YAML parser.
- `python-frontmatter` — wraps PyYAML, so it inherits every coercion issue above while adding a
  second dependency and taking away control of the write path.

---

## R3. CLI argument parsing

**Decision**: `argparse` from the standard library.

**Rationale**: Principle III prefers stdlib and requires every third-party dependency to justify
itself. argparse also happens to fit the contract better than the alternatives: it already exits 2
on a usage error, which is exactly the code FR-041 mandates, and it writes usage errors to stderr
without help. Typer and Click both route errors through their own exit codes (Click uses 2 as well,
but via `UsageError`) and Typer additionally pulls Rich into the error path, which would have to be
suppressed to satisfy FR-039's no-decoration-when-piped rule.

**Consequences to implement deliberately**:
- `argparse` calls `sys.exit` internally. All command bodies are wrapped so that our own
  `EndpaperError` hierarchy maps to exit codes 1 and 3, while argparse keeps 2.
- Subcommand help text is written by hand; there is no introspection-driven help.
- `endpaper` with no arguments must not be an argparse error. The entry point checks for an empty
  `argv` before parsing and dispatches to the TUI (FR-003).

**Alternatives considered**: Typer (least boilerplate, but two dependencies and Rich in the error
path), Click (one dependency, no Rich, but still buys nothing argparse lacks here).

---

## R4. The `/` key: filter and command in one input

**Decision**: One input bar, opened by `/`, that decides between filtering and commanding by
sniffing the first token.

**Rationale**: REQUIREMENTS.md §3.1 specifies `/` as both "focuses a filter input" and the prefix of
`/meeting.standup ...`. These are the same key. Rather than introduce a second binding the
requirements never mention, the bar parses its first whitespace-delimited token: if that token's
stem (the part before any `.`) is a registered verb, the input is a command; otherwise every
keystroke is a live filter over the in-memory list.

**Grammar**:

```
input      := command | filter
command    := verb ["." type] [SP description]
verb       := "meeting" | "meetings" | "init"      # this feature's registered set
filter     := any text whose first token stem is not a registered verb
```

**Ambiguity and its containment**: a user filtering for the literal word "meetings" gets the command
instead. This is accepted, with two mitigations: the footer shows the resolved mode live
(`[filter]` vs `[command: meeting.standup]`) so the user sees the decision before pressing enter,
and a leading space forces filter mode. Commands only take effect on enter; filtering is live. That
asymmetry means a mis-sniffed command never *does* anything without a confirming keystroke.

**Verb set is closed and owned by core**, so `note`, `task`, and `workspace` can be registered by
later features without touching the bar.

**Alternatives considered**: separate `:` command key (unambiguous, but invents a binding the
requirements do not document); Textual's built-in command palette (free fuzzy matching and
discoverability, but discards the documented `/meeting.<type>` shorthand along with its inline
`#tag` parsing).

---

## R5. Meeting identifier format

**Decision** (requirements owner): `m_<YYYYMMDD>_<8 lowercase hex>`, e.g. `m_20260728_a1b2c3d4`.
Generated from `secrets.token_hex(4)`. No uniqueness lookup, no retry.

**Rationale**: With 4 hex digits (the format in REQUIREMENTS.md §4.6) the space is 65,536 per day,
where the birthday bound puts collision probability near 50% at roughly 300 same-day notes — so
4 digits would have required a scan-and-retry loop, and that loop races when two people create
notes in the same synced folder simultaneously. 8 hex digits gives 4.3 billion values per day,
making the check unnecessary and the create path lock-free.

**Consequence**: REQUIREMENTS.md §4.6 shows `m_20260728_a1b2`. Its example must be updated to match.
Tracked as a follow-up; the spec itself (FR-019) only requires uniqueness and stability, so no spec
change is needed.

**Note on uniqueness**: FR-019 says unique *within the workspace*. Random generation makes this
probabilistic rather than guaranteed. Accepted at 8 hex digits. Ids are metadata for addressing, not
a primary key — the file path is the real identity, and no operation in this feature resolves a
meeting by id.

---

## R6. File creation must never overwrite

**Decision**: Create with `os.open(..., O_CREAT | O_EXCL | O_WRONLY)`. On `FileExistsError`,
increment the numeric suffix and retry.

**Rationale**: FR-017 and FR-025 require that an existing file is never read, modified, or
overwritten. A check-then-write (`if not path.exists(): write`) has a window between the two
operations; in a OneDrive folder shared by a team, that window is reachable. Exclusive creation
makes the collision test and the write a single atomic operation, so the retry loop is correct
without a lock. This is why the suffix loop is a `for` over candidate names rather than a
count-and-append.

**Scope note**: this covers creation, which is all this feature does. When the edit feature (§3.5)
adds in-place updates, those will need write-to-temp-then-`os.replace`, which is a different
mechanism for a different requirement. Not built here.

**Alternatives considered**: `pathlib.Path.touch(exist_ok=False)` — same guarantee, but requires a
second open to write, so it is strictly worse.

---

## R7. Testing a Textual app without a terminal

**Decision**: `pytest` + `pytest-asyncio`, driving the TUI through `App.run_test()` and `Pilot`.

**Rationale**: Textual's documented testing path runs the app fully headless — all app logic
executes, only the display is not updated — and yields a `Pilot` for `press()` and `click()`. This
satisfies SC-006 (every acceptance scenario covered by tests that run with no terminal attached) and
Principle I (core testable without a terminal), and it is what lets TUI acceptance scenarios run in
CI on all three platforms.

**Implementation notes gathered from the docs**:
- `run_test()` is an async context manager; tests are `async def` and need an asyncio plugin.
- State does not settle synchronously after a key press — messages bubble. `await pilot.pause()`
  before asserting, or assertions race the message pump.
- `run_test(size=(80, 24))` fixes terminal size, which keeps layout assertions stable.

**Alternatives considered**: `anyio` plugin (equivalent; `pytest-asyncio` is the more common
pairing), snapshot testing via `pytest-textual-snapshot` (useful later for layout regressions, but
it asserts on rendered SVG, which is too brittle to hang acceptance criteria on).

---

## R8. Packaging, layout, and distribution

**Decision**: `hatchling` build backend, `src/` layout, single console entry point, `requires-python = ">=3.11"`.

**Rationale**: `src/` layout is mandated by the feature request (FR-006) and has the independent
benefit that tests import the installed package rather than the working directory, so a missing
`__init__.py` or an unpackaged data file fails in CI instead of in a user's install. Hatchling is
the modern default, needs no `MANIFEST.in` for the `AGENTS.md` template, and is what `uv init`
produces — relevant because `uv tool install endpaper` is the documented install path (FR-001).

**Dependency budget** (Principle III requires each to be justified):

| Dependency | Runtime? | Justification |
|---|---|---|
| `textual>=8.2` | yes | Mandated by REQUIREMENTS.md §4.5. Brings `markdown-it-py`, `rich`, `platformdirs`, `pygments` transitively — all four otherwise needed. |
| `PyYAML>=6.0` | yes | Frontmatter reading, per R2. Cost of doing without: owning a YAML parser against hand-edited input. |
| `pytest`, `pytest-asyncio` | dev | Acceptance tests, incl. headless TUI (R7). |
| `ruff` | dev | Lint + format, Principle VI. |
| `mypy`, `types-PyYAML` | dev | Type checking, Principle VI. |

Total runtime dependency count declared by endpaper: **two**.

**Entry point**: `endpaper = "endpaper.cli.main:main"`. `main()` inspects `sys.argv[1:]` and launches
the TUI when it is empty (FR-003), before argparse sees anything.

**Alternatives considered**: setuptools (works, but needs more configuration for the template data
file), flat layout (contradicts FR-006), `uv_build` (very new; hatchling is the safer default for a
package other people will build from source).

---

## R9. Timestamps and timezone

**Decision**: Local naive time, formatted `YYYY-MM-DDTHH:MM:SS`, seconds precision, no offset.

**Rationale**: Matches the frontmatter example in REQUIREMENTS.md §4.6 exactly. The alternative —
timezone-aware UTC — is more correct in the abstract, but these files are read by humans in the
timezone they took the notes in, and a `Z` suffix on a personal note is noise. Filenames use the
local date, so a note taken at 11pm files under that day, which is what the user means.

**Consequence**: sorting across a team spanning timezones is approximate. Accepted; the requirements
describe a personal vault synced to a shared folder, not a coordinated event log.

---

## R10. Windows path length

**Decision**: Budget generated paths at ≤120 characters below the workspace root.

**Rationale**: FR-044 requires staying well within the 260-character limit assuming a root like
`C:\Users\name\OneDrive - Contoso Corporation\Team Notes\` (~56 chars). Worst case generated path is
`meetings/YYYY-MM-DD-<type>-<slug>-NN.md`: 9 + 10 + 1 + 40 (type cap) + 1 + 40 (slug cap) + 3 + 3 =
107. That leaves ~150 characters of headroom for the root, which covers deeply nested corporate
OneDrive paths. Slug and type caps are therefore load-bearing, not cosmetic, and are asserted in
tests.
