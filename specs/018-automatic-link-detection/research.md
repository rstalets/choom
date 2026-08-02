# Phase 0 Research: Bare URLs Become Markdown Links on Save

**Feature**: `018-automatic-link-detection` | **Date**: 2026-08-02

Every finding below was checked against the installed source or reproduced in a scratch prototype,
not reasoned about from the module docstrings. Where a claim is empirical, the evidence is quoted.

The prototype used throughout is a faithful implementation of the algorithm this plan proposes,
exercised against a 25-case conversion corpus, an 18-case must-not-change corpus, a 15-case
adversarial corpus, and a whole-document integration probe. Final state: **0 failures, every case
idempotent through three passes.** The corpus is reproduced in
[contracts/text-format.md](./contracts/text-format.md) and becomes the unit suite.

---

## R1. `_LINK_RE` cannot be the exclusion mask, and reusing it would corrupt files

**Question**: FR-009 says a URL inside an existing link or image is never touched. `links.py` already
has `_LINK_RE`. Can it be reused as the mask?

**Finding: no, and this is the single most dangerous thing in the feature.** Probed directly:

| Input | `_LINK_RE` matches? |
|---|---|
| `[a](https://x.com/plain)` | yes |
| `[https://a.example](https://a.example)` | yes |
| `[a](<https://x.com/Foo_(bar)>)` | yes |
| `[a](https://x.com/Foo_(bar))` | **NO** |
| `![alt](https://x.com/a.png)` | **NO** |
| `[spec]: https://example.com/spec` | **NO** |
| `<https://example.com>` | **NO** |

`_LINK_RE`'s destination alternative is `[^\s()]*`, so a hand-written link whose destination carries
balanced parentheses — legal CommonMark, and exactly what a Wikipedia or SharePoint URL looks like —
does not match. `(?<!!)` deliberately excludes images. Neither reference definitions nor autolinks are
its business.

**Decision**: reuse `_mask_fences` and `_mask_code_spans` verbatim (FR-031), and write a **new,
deliberately wider** mask for links, images, autolinks, HTML tags, and reference definitions.

**Rationale — the failure directions are opposite, and that is why one regex cannot serve both.**
`_LINK_RE` exists to *find record links choom will act on*. Being narrow there is safe: a link it
misses is simply not healed, and the file is untouched. This feature needs to *find everything it
must not touch*. Being narrow there is unsafe: a link the mask misses gets a second `[...](...)`
wrapped around its destination, producing broken markdown in the user's file. A mask must be a
superset of the syntax, never a subset of it. Sharing the pattern would silently couple a
"correctness" requirement to a "safety" requirement that pull in opposite directions.

**Alternatives considered**:

- *Widen `_LINK_RE` so both use it.* Rejected. Widening the scanner changes what `links check`,
  `heal`, and `find_mirrors` consider a link — a behaviour change to three shipped features, to fix
  a problem none of them has. The 008 contract's "not recognised" table is a deliberate boundary.
- *Match links with a regex tolerant of nested parens.* Rejected; regular expressions cannot count
  nesting depth. The depth-counting scanner in R2 is ~25 lines and exact.

---

## R2. The masking pipeline, and why the order is what it is

**Decision**: seven length-preserving masks, applied in this order, each blanking its spans to
spaces while leaving `\n`/`\r` in place — the idiom `_mask_fences` and `_mask_code_spans` already
use. Candidate URLs are then matched against the fully masked text and spliced into the **original**
text at the offsets found. Length preservation is the whole reason those offsets are valid.

1. **Frontmatter** — leading `---\n` to the closing `\n---`, inclusive (R3).
2. **Fenced code blocks** — `_mask_fences`, reused unchanged.
3. **Inline code spans** — `_mask_code_spans`, reused unchanged.
4. **HTML comments** — `<!--` to the next `-->`, across lines; to end-of-file when unterminated.
5. **Links and images** — `[text](dest)` / `![alt](dest)`, destination scanned with paren-depth
   counting (R1).
6. **Angle spans** — `<...>` with no interior newline: CommonMark autolinks and raw HTML tags at once.
7. **Link reference definitions** — `^ {0,3}\[…\]:[ \t]*\S+`.

**Rationale for the order**: code and comments come first because their contents are opaque — a
fenced block containing `[a](b)` must not be read as link syntax by mask 5, and a commented-out link
must not be read as one either. Masks 5–7 then run on text where every opaque region is already
spaces, so they only ever see real structure. Mask 6 after mask 5 is a deliberate backstop: an
angle-bracketed destination with *unbalanced* parens inside it defeats mask 5's depth counter, and
mask 6 catches the `<…>` anyway — verified with `[a](<https://x.com/Q3 (draft>)`, which converts
nothing.

**Verified consequence**: no mask inserts or removes a character, so **no newline is ever added**.
The whole-document probe confirms line counts are identical before and after (19 → 19), which is
what keeps `heal_text`'s warning line numbers, `parse_tasks`'s task line numbers, and the editor's
cursor row all valid across a conversion.

---

## R3. Frontmatter must be excluded, and the evidence is a note that disappears

**Question**: `heal_text` does not mask frontmatter. Does this feature need to?

**Finding: yes, and the failure is worse than a corrupted title.** Reproduced against
`documents._parse_document`:

| Frontmatter line | Parses? |
|---|---|
| `title: https://example.com/a` | yes — `title='https://example.com/a'` |
| `title: "Notes on https://example.com/a"` | yes |
| `title: [https://example.com/a](https://example.com/a)` | **no — `doc=None`, `malformed_yaml`** |
| `title: "Notes on [https://…](https://…)"` | yes, but the title now reads `Notes on [https://…](https://…)` |

An unquoted YAML scalar beginning `[` is a **flow sequence**. Converting a URL in one turns the
frontmatter into unparseable YAML, `_parse_document` returns `(None, warning)`, and the document
drops out of `scan_documents` — out of every list, every search, every `--json` payload choom
produces. The user's note is still on disk and is now invisible in the tool. The quoted case
survives YAML but silently rewrites the title shown in the list, the preview header, and the
terminal tab.

**Decision**: mask the entire frontmatter block, first, before anything else.

**Note on the divergence from `heal_text`**: the healer's exposure to the same hazard is theoretical
(it only rewrites a destination inside an already-existing `[…](…)`, which cannot occur in
frontmatter choom wrote) whereas this feature's is immediate. Not masking frontmatter in the healer
is therefore not evidence that this feature can skip it. This asymmetry is intentional and recorded
here so a future reader does not "unify" the two by deleting the mask.

---

## R4. The trailing-boundary rule, with the corpus that pins it

**Decision**: after matching a candidate, trim its tail by repeatedly applying, until neither fires:

1. drop a final character in `. , : ; ! ? ' " * _ ~`
2. drop a final `)` when the candidate contains more `)` than `(`

**Rationale**: rule 2 is what separates "the URL owns this parenthesis" from "the sentence does".
Counting is exact for both directions and needs no lookahead into the surrounding text. This matches
the GFM autolink extension's behaviour, which matters because markdown-it's linkify — already running
in choom's preview — approximates the same rule; a boundary that disagreed would make the preview
underline a different span before and after a save.

**Worked corpus** (all verified passing; `→` shows the resulting file text):

| Input | Destination chosen | Output |
|---|---|---|
| `Read https://example.com/a.` | `https://example.com/a` | `Read [https://example.com/a](https://example.com/a).` |
| `Read https://example.com/a, then stop` | `https://example.com/a` | `…](https://example.com/a), then stop` |
| `(https://example.com/a)` | `https://example.com/a` | `([https://example.com/a](https://example.com/a))` |
| `https://en.wikipedia.org/wiki/Foo_(bar)` | `…/Foo_(bar)` — balanced, kept | `[…/Foo_(bar)](<…/Foo_(bar)>)` |
| `(https://en.wikipedia.org/wiki/Foo_(bar))` | `…/Foo_(bar)` | `([…/Foo_(bar)](<…/Foo_(bar)>))` |
| `"https://example.com/a"` | `https://example.com/a` | quotes stay outside |
| `**https://example.com/a**` | `https://example.com/a` | `**[…](…)**` |
| `https://example.com/a?q=1&r=2#frag` | whole thing | `?`, `&`, `#` are URL, not punctuation |
| `see https://example.com/a; also` | `https://example.com/a` | `;` outside |
| `both https://example.com/a).` | `https://example.com/a` | both `)` and `.` outside |
| `ellipsis https://example.com/a...` | `https://example.com/a` | all three dots outside |
| `(see https://example.com/a).` | `https://example.com/a` | `)` and `.` outside |
| `trailing slash https://example.com/` | `https://example.com/` | `/` is **not** trailing punctuation |

**Alternative considered**: hand the trailing-punctuation decision to a URL-validation library.
Rejected under R11.

---

## R5. The leading boundary

**Decision**: a candidate must start at the beginning of the text or immediately after one of:
whitespace, `(`, `[`, `{`, `"`, `'`, `*`, `_`, `~`, `|`, `>`. Expressed as the negative lookbehind
`(?<![^\s([{"'*_~|>])`, which also succeeds at position 0.

**Rationale**: the set is "characters that can legitimately abut the start of a URL in markdown
prose" — openers, quote marks, emphasis runs, table pipes, and blockquote markers. Excluding
everything else prevents matching the tail of a longer token: `xhttps://example.com/a` converts
nothing, verified.

`<` is deliberately **absent** from the set. That single omission is what makes a CommonMark autolink
`<https://example.com>` non-convertible even before mask 6 sees it, and it is the reason
`href="…"` still needs mask 6 — `"` *is* in the set, so an unmasked HTML attribute would otherwise
match. Both verified.

`*`, `_`, `~`, `|`, `>` were added after the first corpus run failed on `**https://example.com/a**`.
Recorded because the omission was not obvious and the test that caught it is the one worth keeping.

---

## R6. Idempotency is structural, not incidental — and it is the safety property

**Question**: FR-004 requires that applying the transform to its own output changes nothing. What
mechanism guarantees it, rather than making it true by luck?

**Finding**: it falls out of mask 5 covering **both halves** of an existing link, and nothing else is
needed.

The transform's output for a URL `U` is `[U](D)` where `D` is `U`, optionally angle-wrapped. On a
second pass:

- mask 5 finds `[` at the start, the matching `]`, the immediately following `(`, and depth-counts to
  the closing `)`. It blanks that **entire span** — link text and destination together.
- Both copies of `U` are inside that span. Neither is visible to the candidate scanner.
- Therefore zero candidates are found, zero edits are produced, and the text is returned unchanged.

This is why FR-009 is written as "the whole span" rather than "the destination". A mask covering only
the destination would leave the link-text copy exposed and produce
`[[U](U)](U)` on the second save, `[[[U](U)](U)](U)` on the third — silent, compounding corruption
that only shows up as a rendering failure weeks later. **The link-text half of the mask is the
idempotency mechanism.**

Two supporting facts make the guarantee total rather than probabilistic:

- The destination written is always either bare (contains none of ` ()<>`) or angle-wrapped. Mask 5
  handles both — the bare form by depth counting, the angle form because the wrapper's parens are
  balanced. Verified against `[a](<…/Foo_(bar)>)`.
- The transform never emits `[` or `]` inside `U` (FR-012a rejects such URLs outright), so the
  `]`-search in mask 5 cannot terminate early inside a destination it should have covered.

**Verification**: every one of the 25 conversion cases was run through three consecutive passes;
pass 1 == pass 2 == pass 3 for all of them. The whole-document probe reports `second pass
conversions: 0`. This is the property the unit suite leans on hardest — see R13.

---

## R7. The URL character class makes angle-wrapping unconditionally safe

**Decision**: a candidate is `https?://[^\s<>\[\]]*`, matched case-insensitively, requiring at least
one character after `://` once R4's trim has run.

**Rationale**: the excluded characters are exactly the ones that would make the output unsafe.

| Excluded | If it were allowed |
|---|---|
| whitespace | would run the destination past the URL; also illegal in a bare destination |
| `<`, `>` | would break the angle-wrapped destination form `<…>` |
| `[`, `]` | would break the link-text slot `[…]` (FR-012a) |

Because `(` and `)` *are* allowed, the destination is rendered through the existing
`links._render_destination`, which angle-wraps anything containing ` ()<>`. Reusing it rather than
re-deriving an escaping rule means the healer, `/link` insertion, and this feature can never disagree
about how a destination is escaped. And since the character class already guarantees no `<` or `>` is
present, the angle-wrapped form is **always** valid — there is no input for which the escape itself
can fail.

`https://` with nothing after it converts nothing, verified — `[https://](https://)` would be worse
than what it replaced.

---

## R8. Indented code blocks are not masked — accepted, with the alternative rejected

**Finding**: `    https://example.com/a` (four-space indent, a CommonMark indented code block at top
level) **is** converted. `_mask_fences` handles only fenced blocks.

**Decision**: accept this, do not mask indented blocks, and record it as a known limitation.

**Rationale**: masking four-space indents would be actively wrong for choom. A task's body is
*indented lines beneath its checkbox* — that is the dominant use of indentation in a choom vault, it
is prose, and FR-015 explicitly requires it to convert. CommonMark agrees: an indented block inside a
list item is a continuation paragraph, not code. Distinguishing the two requires tracking list
context through the document, which is a real block parser — a large amount of new, subtle,
Principle-IV-critical code to serve a case that is rare in a notes vault and that choom's own
templates steer away from (`AGENTS.md` and every generated document use fenced blocks).

The residual harm is bounded and reversible: inside a top-level indented block the reader sees
`[url](url)` rendered literally instead of `url`. Nothing is lost, and deleting the wrapper restores
it. That is a cosmetic regression in a rare case, weighed against a block parser whose bugs would be
data-shaped.

**Consistency note**: `heal_text` has exactly this gap today — a record link inside an indented code
block is healed. So this is the shipped behaviour of the module, not a new class of exposure.

**Alternative considered**: mask any line indented four or more spaces. Rejected — it would disable
the feature for task bodies, the single place this feature is most useful.

---

## R9. Where the conversion attaches: two call sites, and why they differ

**Question**: FR-015 names two save paths. Can one hook serve both?

**Finding**: no, and the reason is a real constraint rather than an inconvenience.

| Path | Writer | Called by | Can the hook live in the writer? |
|---|---|---|---|
| Document save | `editing.save_buffer` | `edit_screen.open_editor._save` **only** (verified: the sole `src/` caller) | **Yes** |
| Task-body save | `tasks.set_task_body` | `open_task_editor._save` **and** `open_task_editor`'s reconcile-on-open | **No** |

`save_buffer` *is* the user-save primitive — it already stamps `updated` and already heals links, both
of which are "the user saved" semantics. Adding the conversion there is consistent and cannot leak.

`set_task_body` is a general body writer with two callers, one of which is reconcile-on-open. Putting
the conversion inside it would convert on **open**, violating FR-016 and rewriting a document the user
has not touched.

**Decision**: the pure core function is called from `save_buffer` (inside core) and from
`open_task_editor._save` (in the adapter, immediately before `set_task_body`). One function, two call
sites, both on the user-save path.

**Alternative considered**: add `convert_urls: bool = False` to `set_task_body`. Rejected — a boolean
parameter that must be `True` at exactly one of two call sites is a trap whose safe default hides the
bug rather than preventing it, and the constitution prefers an explicit branch to a clever one. The
adapter calling a pure core function and then a core writer keeps the *decision* in core and only the
*sequencing* outside it.

**Guard**: an integration test asserts that opening a task whose body contains a bare URL, with no
save, leaves the file byte-identical. That is the test that keeps FR-016 true if someone later moves
the call.

---

## R10. Ordering inside `save_buffer`, and the single write

**Decision**, replacing the body of `save_buffer` between its current heal step and its write:

```
1. heal_text(workspace, text)          # existing, unchanged, when workspace is not None
2. format_bare_urls(text)              # new, unconditional
3. stamp_updated(text, timestamp)      # existing, unchanged
4. _apply_line_ending_policy(...)      # existing
5. write_text_atomic(path, out_text)   # existing — still exactly one write
```

**Why heal before convert**: the two operate on provably disjoint spans, so correctness does not
depend on the order — a healed link is `[text](path#id)`, whose destination carries no scheme, and
this feature masks that whole span; a converted link's destination *does* carry a scheme, and
`_link_from_match` returns `None` for it. Verified end to end: in the whole-document probe the record
link's line, id, and path are identical before and after conversion, and `find_mirrors` returns the
identical mirror set. Order is therefore chosen for the smaller diff — the existing heal call stays
first and unmodified.

**Why convert before stamp (FR-023)**: `stamp_updated` locates the `updated:` line by searching the
frontmatter block. Converting afterwards would mean stamping text that is then rewritten, so
`SaveResult.saved_text` and the bytes on disk could diverge. Verified that `stamp_updated` still finds
its line in converted text.

**Why it stays one write (FR-024)**: nothing above touches the filesystem except step 5. Both
transforms are string-to-string, and the existing atomic temp-file-and-replace is unchanged.

---

## R11. `linkify-it-py` is present but MUST NOT be used

**Finding**: `linkify-it-py==2.1.0` is installed, and `markdown-it-py[linkify]` is a hard requirement
of `textual==8.2.8`. It is therefore importable today without touching `pyproject.toml` — which is
exactly the trap.

**Decision**: reject it. Detection uses the standard library `re` only. No dependency is added.

**Rationale**, three independent reasons any one of which is sufficient:

1. **It would be an undeclared dependency.** choom declares `textual` and `PyYAML`. Importing
   linkify because a *transitive* dependency happens to pull it in means the day Textual drops the
   `[linkify]` extra, choom breaks at runtime with no version constraint that could have caught it.
   Principle III requires every third-party dependency to be justified by what doing without would
   cost; here doing without costs one 30-line function.
2. **Its rules are the wrong rules.** linkify matches `www.` hosts, bare email addresses, and
   scheme-less domains with fuzzy TLD heuristics — all explicitly out of scope. Adopting it would
   widen FR-002 by accident and put the scope boundary in a third party's release notes.
3. **It solves a different problem.** linkify finds URLs in text to render them. This feature needs
   offsets into *raw markdown* that survive seven exclusion masks and splice back into the original
   string. linkify has no notion of a code fence, an HTML comment, or a frontmatter block, so every
   Principle IV guarantee in this feature would still have to be built around it.

The one thing linkify's presence *does* justify is aligning R4's boundary rule with GFM's, so the
preview's underline and the file's link cover the same span.

---

## R12. Cursor position after a conversion on the cursor's line

**Finding**: `EditorPane._save` already re-syncs the buffer after a save
(`editor.text = result.saved_text`, capturing and restoring `cursor_location` around it) because the
`updated:` stamp changes the text. That stamp is length-neutral, so restoring `(row, col)` verbatim
has always been correct. A conversion is **not** length-neutral, so restoring the raw column can drop
the cursor into the middle of the URL text.

**Decision**: the core function returns its edits, and the adapter maps the cursor through them.

- Row is invariant — no mask or edit inserts a newline (R2), so the cursor never changes line.
- Column maps by: `new_col = col + Σ (len(replacement) − (end − start))` over conversions on that row
  ending at or before `col`; a cursor that fell strictly inside a converted span lands at the end of
  that span's replacement.
- Row/column ↔ offset conversion uses Textual's own `Document.get_index_from_location` and
  `get_location_from_index`, both confirmed present on `textual==8.2.8`. The same idiom 017 used.

The mapping arithmetic is a pure function over the returned conversions and is unit-tested in core
without a terminal; the adapter only supplies the coordinates.

**Alternative considered**: clamp the column to the new line length. Rejected — correct only when the
cursor is at end of line, and silently wrong (cursor lands inside the URL) in the common case of
typing a sentence after pasting a link.

---

## R13. Test layering

**Decision**, following Principle VI's risk-based rule rather than one test per acceptance scenario:

- **`tests/unit/` carries the weight.** Every guarantee in this feature is decidable against a
  string. One new file drives the three corpora from
  [contracts/text-format.md](./contracts/text-format.md): conversion, must-not-change, and
  idempotency. The idempotency corpus is asserted through **three** passes, not two — a bug that is
  stable at pass 2 but not pass 3 is exactly the compounding-corruption shape R6 exists to prevent.
  A second small file covers the cursor-mapping arithmetic.
- **`tests/integration/` gets the boundaries the unit tests cannot see**: a document save converts and
  stamps in one write; a task-body save converts; **reconcile-on-open does not**; `links heal` and
  `links check` convert nothing; and `check_links` reports an identical set before and after a
  workspace-wide save pass (SC-005).
- **No `tests/contract/` change** — no CLI surface, no `--json` key, no exit code is added (FR-017,
  FR-018).
- **No `tests/performance/` change** — the pass is one scan of a string already in memory, with no
  file read and no budget to protect (SC-007). Consistent with the existing rule that
  `performance/` covers only scenarios with a real budget.
- **No wall-clock dependency**: the only dates involved are frontmatter fixtures, which are inert
  strings here; nothing in this feature reads a clock except the existing `save_buffer` stamp, which
  already takes an injectable `now`.
