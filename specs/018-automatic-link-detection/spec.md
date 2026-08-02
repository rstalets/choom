# Feature Specification: Bare URLs Become Markdown Links on Save

**Feature Branch**: `018-automatic-link-detection`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "issue #39. You are 018"

**Source**: GitHub issue #39 "[Feature]: Automatic link detection". Verbatim ask: *"Upon save,
unformatted links (starting with http:// or https://) should be automatically converted to markdown
format links."* The reported problem: *"if I paste a link into a note, I can't follow the link later
unless I take the time to put it in markdown format."*

---

## Overview

Someone in a meeting pastes `https://intranet.example.com/procurement/q3-vendor-comparison` into a
note. It is the most valuable line in the file — it is the thing the note is *about* — and it is
inert. Three weeks later they want it, and getting there means selecting the text with a mouse,
copying it, switching to a browser, and pasting. Every other link in choom is one keystroke away.

This feature closes that gap at the only moment where it can be closed without asking the user to do
anything: **when they save**. A bare `http://` or `https://` URL sitting in the document body becomes
`[<url>](<url>)` — a real CommonMark inline link, pointing at itself, saying exactly what it said
before.

### What is actually broken today, precisely

Two things, and they are not the same thing.

**In choom's own preview pane, a bare URL is already clickable.** The preview renders markdown
through markdown-it's `gfm-like` preset, which has `linkify` enabled, so `https://example.com` is
already drawn as a link; clicking it reaches `on_markdown_link_clicked`, `resolve_href` declines it
because it carries a URL scheme, and the handler falls through to `app.open_url`. That path works
today and this feature does not change it. So the issue's literal claim — "I can't follow the link" —
is true in the raw file and in the editor, and *not* true of a mouse click in the preview pane.

**In the file, the link does not exist.** That is the real defect, and it is the one that matters,
because in choom the file is the product. Strict CommonMark does not autolink a bare URL — linkify is
an extension, and whether it fires is a property of whichever renderer happens to be open. The same
line is a link in choom's preview, a link on GitHub, and dead plain text in a strict CommonMark
viewer, in a colleague's editor, in a PDF export, and in whatever the user's company uses next year.
The vault is meant to outlive choom. A URL that is only a link when choom is the one looking at it is
exactly the kind of dependence on a particular tool that the plain-markdown premise exists to avoid.

Writing `[url](url)` makes the link real in the bytes. Nothing downstream has to guess.

### The property that makes this safe to do without asking

`[url](url)` **renders identically to the bare URL it replaced** in any renderer that linkified the
URL, and it renders as a link rather than as dead text in every renderer that did not. The visible
result never gets worse and never changes for the worse. The rewrite is invisible in the reading
experience and visible only in the raw file, where it is strictly more capable.

This is why this feature can rewrite the user's text at all. It is not adding information, not
summarising, not reflowing, not "improving" prose. It is writing down, in a form the file format
guarantees, a fact the text already asserted.

### Three properties define the behaviour

1. **It only ever wraps. It never edits, moves, drops, or re-encodes a single character of a URL.**
   The URL appears twice in the output, byte-for-byte identical to the input both times, with
   `[`, `]`, `(`, `)` added around it. Deleting those four characters and the duplicate restores the
   original file exactly. No percent-encoding, no case folding, no trailing-slash normalisation, no
   query-string tidying.
2. **When it is not certain, it does nothing.** Every ambiguous context — code, comments,
   frontmatter, existing links, HTML — is left byte-identical. A URL choom declines to convert costs
   the user one manual edit. A URL choom converts wrongly costs them a corrupted file. The rule is
   asymmetric and the spec is written to the safe side of it throughout.
3. **It happens where the user is looking, and only there.** Only a save the user performed in the
   editor converts anything. No background pass, no scanner, no repair command, no
   whole-workspace rewrite.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The pasted URL becomes followable (Priority: P1)

Someone pastes a URL into a meeting note mid-conversation and keeps typing. When they press `ctrl+s`,
the URL becomes a markdown link in the buffer in front of them and in the file on disk. The rest of
the note is untouched.

**Why this priority**: This is the issue, in the shape the issue reports it. With this alone the
feature is worth shipping.

**Independent Test**: Open a note in the editor, type a line containing a bare `https://` URL, save,
and read the file back.

**Acceptance Scenarios**:

1. **Given** a note whose body contains the line `See https://example.com/spec for details.`,
   **When** the user saves in the editor, **Then** the line reads
   `See [https://example.com/spec](https://example.com/spec) for details.` and the trailing full stop
   is outside the link.
2. **Given** the same note after that save, **When** the user saves it again without typing anything,
   **Then** the only byte that changes is the `updated:` timestamp — the link is not wrapped a second
   time.
3. **Given** a note containing three bare URLs on three lines, **When** the user saves, **Then** all
   three are converted and no other line differs.
4. **Given** a note containing a bare URL, **When** the user saves, **Then** the editor buffer shows
   the converted text immediately, so the user sees what landed on disk rather than discovering it
   later.
5. **Given** a note containing `http://legacy.internal/report`, **When** the user saves, **Then** it
   is converted — `http://` is in scope exactly as `https://` is.

---

### User Story 2 - Nothing else in the file moves (Priority: P1)

A note that documents an API, or explains choom's own link syntax, or carries a URL in its title,
contains URLs that are content rather than references. Saving that note changes none of them.

**Why this priority**: Equal to P1 above, and non-negotiable. This feature writes to files the user
did not ask it to write to; if it gets this wrong once, the correct response is to remove the feature
rather than fix it. Principle IV is not graded on a curve.

**Independent Test**: Build one document containing a URL in every excluded context listed in FR-005
through FR-012, save it, and diff. Nothing but `updated:` may differ.

**Acceptance Scenarios**:

1. **Given** a fenced code block containing `curl https://api.example.com/v1`, **When** the user
   saves, **Then** the fence contents are byte-identical.
2. **Given** the inline code span `` `https://example.com` ``, **When** the user saves, **Then** it is
   byte-identical.
3. **Given** an existing link `[the spec](https://example.com/spec)`, **When** the user saves,
   **Then** it is byte-identical — the destination is not wrapped again.
4. **Given** an existing link whose text is already a URL, `[https://a.example](https://a.example)`,
   **When** the user saves, **Then** it is byte-identical. This is the same case as saving twice, and
   it is what makes the operation idempotent.
5. **Given** the autolink `<https://example.com>`, **When** the user saves, **Then** it is
   byte-identical — it is already a link.
6. **Given** frontmatter containing `title: "Notes on https://example.com"`, **When** the user saves,
   **Then** the frontmatter block is byte-identical.
7. **Given** a task line whose metadata comment reads
   `<!-- id:task_a1b2 links:meeting_20260728_a1b2c3d4 created:2026-07-30 -->`, **When** the user
   saves, **Then** the comment is byte-identical, and this holds for any HTML comment anywhere in the
   file.
8. **Given** an image `![screenshot](https://example.com/a.png)`, **When** the user saves, **Then** it
   is byte-identical.
9. **Given** a note whose only URL is inside a code fence, **When** the user saves, **Then** no
   "links formatted" message is shown, because nothing was formatted.

---

### User Story 3 - Punctuation stays out of the link (Priority: P1)

A URL at the end of a sentence, a URL in parentheses, a URL in quotes, and a URL that itself contains
parentheses all produce the boundary the reader expects.

**Why this priority**: This is the classic failure mode of this feature and the one most likely to
ship broken. A link that swallows the full stop at the end of a sentence is wrong in the file, wrong
on screen, and wrong when clicked — and it is wrong on the most common line shape there is.

**Independent Test**: A table-driven test over the boundary corpus in FR-013, asserting the exact
output string for each input.

**Acceptance Scenarios**:

1. **Given** `Read https://example.com/a.`, **When** saved, **Then** the destination is
   `https://example.com/a` and the `.` follows the closing `)`.
2. **Given** `Read https://example.com/a, then stop`, **When** saved, **Then** the `,` is outside the
   link.
3. **Given** `(https://example.com/a)`, **When** saved, **Then** both parentheses are outside the
   link.
4. **Given** `https://en.wikipedia.org/wiki/Foo_(bar)`, **When** saved, **Then** the closing
   parenthesis **is** part of the destination, because the URL's own parentheses are balanced.
5. **Given** `(https://en.wikipedia.org/wiki/Foo_(bar))`, **When** saved, **Then** the destination is
   `https://en.wikipedia.org/wiki/Foo_(bar)` and the outer parentheses are outside the link.
6. **Given** `"https://example.com/a"`, **When** saved, **Then** the quotes are outside the link.
7. **Given** `https://example.com/a?q=1&r=2#frag`, **When** saved, **Then** the query string and
   fragment are inside the destination — `?`, `&`, and `#` are part of a URL, not punctuation
   trailing it.
8. **Given** a URL whose destination contains a parenthesis, **When** saved, **Then** the destination
   is angle-bracket wrapped by the same escaping rule the existing link writer uses, so choom's own
   scanner and every CommonMark parser read the whole destination.

---

### User Story 4 - An assistant's bare URL is repaired the next time a human saves (Priority: P2)

An AI assistant, following the workspace's `AGENTS.md`, writes a meeting summary directly into a
note's markdown body and includes a bare URL. choom is not part of that write. The next time a person
opens that note in the editor and saves it, the URL is converted.

**Why this priority**: It is the same behaviour as P1 with no new mechanism, but it is the case where
"which write paths does this apply to" has to be answered out loud rather than assumed.

**Independent Test**: Write a bare URL into a note file with an ordinary file write, confirm choom
did not touch it, then open and save in the editor and confirm it converted.

**Acceptance Scenarios**:

1. **Given** an assistant has written a bare URL into a note file, **When** no one has saved that note
   in choom, **Then** the file still contains the bare URL — choom does not watch the filesystem and
   nothing converts behind the user's back.
2. **Given** that same note, **When** a user opens it in the editor and saves, **Then** the URL is
   converted along with anything else in the buffer.
3. **Given** a workspace full of bare URLs, **When** the user runs `choom links check` or
   `choom links heal`, **Then** no URL anywhere is converted and no file is written on their account.

---

### Edge Cases

- **A bare scheme with no host** (`https://` alone, or `see https:// for the scheme`): not converted.
  There is no URL there, and `[https://](https://)` is worse than what it replaced.
- **A URL immediately following a non-space character** (`xhttps://example.com`, `foo:https://a`):
  not converted. The candidate must begin a token.
- **A URL containing `[` or `]`** (an IPv6 literal host, `https://[::1]/status`): not converted. The
  bracket cannot survive the link-text slot, and choom does not rewrite the user's URL to make it fit.
- **A URL inside a raw HTML tag** (`<a href="https://example.com">`): not converted. It is already a
  destination.
- **A link reference definition** (`[spec]: https://example.com/spec`): not converted. Wrapping the
  destination would break the definition and silently kill every `[spec]` reference in the file.
- **An unterminated HTML comment or an unclosed code fence**: everything from the opener to the end of
  the file is treated as inside it and nothing there is converted. The conservative direction is to
  convert less.
- **The same URL twice on one line**: both are converted, independently.
- **A URL on the frontmatter delimiter line or in a heading**: a heading is ordinary body text and
  converts; frontmatter does not.
- **Cursor position after a save that converted a URL on the cursor's own line**: the line grew, so
  the saved cursor column no longer means what it meant. The cursor MUST remain on the same line and
  MUST NOT land inside the URL text it was in front of. Landing at the end of the newly written link
  is acceptable; jumping to another line is not.
- **A very large document with no URL in it at all**: costs one scan of a string already in memory and
  no additional file read, the same shape as `reconcile_on_open`'s cheap path.
- **`www.example.com` and bare email addresses**: not converted, and deliberately so — see Out of
  Scope.

---

## Requirements *(mandatory)*

### What is converted

- **FR-001**: On a qualifying save, choom MUST replace each bare URL in the saved text with
  `[<url>](<destination>)`, where `<url>` is the matched URL reproduced byte-for-byte as the link
  text and `<destination>` is that same URL rendered by the existing destination-escaping rule
  (bare, or angle-bracket wrapped when it contains a space, `(`, `)`, `<`, or `>`).
- **FR-002**: A **bare URL** is a run of text that begins with `http://` or `https://`
  (scheme matched case-insensitively), begins at the start of a line or immediately after a
  whitespace character or one of `(`, `[`, `{`, `"`, `'`, is not inside any excluded context in
  FR-005 through FR-012, and has at least one character after `://` once the trailing-boundary rule
  in FR-013 has been applied.
- **FR-003**: No other scheme is converted. `mailto:`, `ftp:`, `file:`, `s3:`, and a bare `www.` host
  are left untouched.
- **FR-004**: The operation MUST be idempotent. Applying it to its own output MUST produce that output
  unchanged, byte for byte. Saving a file twice with no intervening edit MUST change nothing but the
  `updated:` timestamp.

### What is never converted

Each of the following is left byte-identical, including every byte before and after it on the line:

- **FR-005**: Anything inside a fenced code block, opened by ``` ``` ``` or `~~~`, including the fence
  lines themselves.
- **FR-006**: Anything inside an inline code span, using CommonMark's equal-length-backtick-run rule.
- **FR-007**: Anything inside the document's frontmatter block. This is stricter than the existing
  link healer, which does not exclude frontmatter, and the strictness is load-bearing: a `[` opening
  an unquoted YAML scalar turns it into a flow sequence, the frontmatter stops parsing, and the
  document drops out of every list choom draws. A rewrite that can make a note invisible is not a
  rewrite this feature is willing to make.
- **FR-008**: Anything inside an HTML comment, `<!-- ... -->`, anywhere in the file and across line
  boundaries. This covers the task line's metadata comment, whose contents choom parses, and any
  comment the user wrote for themselves.
- **FR-009**: Anything inside an existing markdown inline link or image, `[text](dest)` /
  `![alt](dest)` — the whole span, so neither a URL used as the destination nor a URL used as the link
  text is touched. The link-text half of this rule is what delivers FR-004.
- **FR-010**: A CommonMark autolink, `<https://example.com>`. It is already a link.
- **FR-011**: Anything inside a raw HTML tag, `<...>`.
- **FR-012**: The destination of a link reference definition, a line matching `[label]: <url>`.
- **FR-012a**: A URL containing `[` or `]`. It cannot be placed in the link-text slot without either
  breaking the link or altering the user's URL, and altering the URL is not permitted by FR-001.

### The trailing boundary

- **FR-013**: The end of a bare URL MUST be determined by repeatedly applying, until neither applies:
  - drop a final character in the set `. , : ; ! ? ' " * _ ~`;
  - drop a final `)` when the candidate contains more `)` than `(`.

  A `<` terminates the candidate. `?`, `#`, `&`, `=`, `/`, and `%` inside the run are part of the URL
  and MUST NOT terminate it. Whitespace always terminates it.
- **FR-014**: Characters removed by FR-013 MUST remain in the document, outside the closing `)`, in
  their original order and position.

### Where it applies

- **FR-015**: The conversion MUST run on a save the user performed in choom's editor, and nowhere
  else. Concretely: the document save path (`save_buffer`, `ctrl+s` on a meeting or note) and the
  task-body save path (`ctrl+s` while editing a task's indented body). These are the two gestures in
  choom that mean "write what I typed".
- **FR-016**: The conversion MUST NOT run on any write choom performs on the user's behalf. Named
  explicitly: mirror reconcile-on-open, the mirror sync write that follows toggling a task's state,
  `choom links heal`, and `choom links check` (which writes nothing at all). A pass that rewrote prose
  across a workspace would show a colleague on a synced folder a wave of modifications nobody made —
  the outcome the 008 link contract records as rejected outright, and it is rejected again here.
- **FR-017**: The conversion MUST NOT run on `choom meeting new`, `choom note new`, or
  `choom note today`. Those commands write frontmatter and no body, so there is nothing to convert;
  should a body ever be created from user input, this same rule applies to it.
- **FR-018**: The conversion MUST NOT run on a task's one-line description, whether it arrives via
  `choom task add "<description>"` or `/task <description>` in the editor. It is excluded on both
  surfaces, identically, so the CLI and the TUI do not diverge. The reason it is excluded at all:
  a `/task` capture turns the description into the *link text* of a mirror
  (`- [ ] [description](../tasks.md#task_a1b2)`), and a link inside link text is not valid
  CommonMark — so the TUI physically cannot honour it and the CLI must not either. A task's indented
  **body**, which is prose in an editor buffer, does convert under FR-015.
- **FR-019**: choom MUST NOT scan, watch, or opportunistically rewrite files. A bare URL written to a
  file by an AI assistant, by another editor, or by hand outside choom stays exactly as written until
  a person saves that document in choom's editor.

### Interaction with the existing link subsystem

- **FR-020**: A converted link MUST NOT appear in the Links pane, in `choom links <id>` output, or in
  `choom links check` / `heal` reports, and MUST NOT be counted as a mirror. The existing scanner
  already declines any destination carrying a URL scheme, so this follows from FR-001 writing an
  ordinary `http(s)` destination and requires no change to the scanner — but it MUST be verified
  rather than assumed.
- **FR-021**: Running `choom links check` over a workspace MUST report exactly the same set of stale
  and dead links before and after every document in it has been saved once. This feature adds no link
  problem and resolves none.
- **FR-022**: Converting a URL MUST NOT change how a click on it behaves in the preview pane. It
  already resolves to nothing choom owns and already falls through to the platform's URL opener; it
  MUST continue to.
- **FR-023**: The conversion MUST run before the `updated:` stamp is applied on the document save
  path, so that a single write carries both and `updated:` reflects the bytes that landed.
- **FR-024**: Where a save both heals a stale record link and converts a bare URL, both MUST land in
  the same single atomic write, and each MUST leave the other's span untouched.

### Visibility, configuration, and reversibility

- **FR-025**: When a save converted at least one URL, the editor's status line MUST say so, naming the
  count. When it converted none, it MUST say nothing — a message on every save is a message nobody
  reads, and a confirmation that fires when nothing happened is exactly the reflex-dismissal failure
  Principle V describes.
- **FR-026**: The editor buffer MUST be updated to the text that landed on disk, as it already is for
  the `updated:` stamp, so the user sees the converted link the instant the save completes rather
  than discovering it the next time they open the file.
- **FR-027**: The feature MUST NOT introduce a setting. See "Why there is no setting" below.
- **FR-028**: choom MUST NOT offer an un-convert or revert operation. The editor's own undo, and the
  fact that the change is visible in the buffer the moment it happens, are the remedy; a user who
  wants the bare URL back deletes eight characters and a duplicate.
- **FR-029**: The generated `AGENTS.md` MUST NOT be changed by this feature. An assistant does not
  need to be told about a repair that happens after it has finished writing, and the file's content
  rule — nothing an assistant could infer, nothing that does not earn its line — bites well before the
  ~100-line backstop does.

### Core boundary

- **FR-030**: Detection and rewriting MUST be a pure text-in / text-out function in `choom.core`,
  taking a string and returning the new string plus the number of conversions. It MUST require no
  `Workspace`, no path, no filesystem access, no network, and no terminal, and MUST be exercisable by
  a unit test that passes a string literal and asserts on a string literal. Unlike link healing, it
  resolves nothing against the workspace — a URL is self-describing.
- **FR-031**: It MUST reuse the existing code-fence and code-span masking rather than reimplementing
  either. Two independent notions of "what counts as code" in one codebase is precisely how a
  byte-preservation guarantee gets quietly broken, which is the reason the existing link module holds
  its scanner, resolver, and healer in one file.
- **FR-032**: It MUST never raise. Any input is valid input; text it cannot make sense of is text the
  user typed, and it is returned unchanged.

---

## Why there is no setting

Principle III says a setting that could be a sensible default MUST be a sensible default. That is a
test to be argued, not a formula, so here is the argument.

**The rewrite has no losing side.** For every renderer, the output of a conversion renders the same as
its input or better, and never worse. There is no reader for whom the converted file is harder to
read, and no viewer in which it looks different. A setting exists to let two users who want different
outcomes both get theirs; here there is only one outcome, described two ways.

**choom already rewrites on save, twice, with no opt-out, and for weaker reasons.** Saving a document
stamps `updated:` — a change to the user's file they did not type. Saving a document heals every
stale record-link path in it — a change to the user's file they did not type, one that *does* alter
characters the user wrote, and one that can be wrong if two records share an id. Both are
unconditional. Adding an opt-out for the third, smallest, and most conservative of the three would be
an inconsistency in the tool, not a protection for the user.

**A setting cannot be found in time to help.** The only user who would want this off is one surprised
by it, and they can only be surprised by it after the first save. By then the setting's value is
retroactive regret, not prevention. What actually protects that user is that the change is visible in
the buffer the moment it lands (FR-026), announced in the status line (FR-025), and undoable with the
editor's own undo. Safety here comes from the rewrite being correct and visible, not from it being
optional.

**And a setting would cost more than it saves.** It doubles the behaviour under test, adds a branch to
the save path, and puts a question in front of a user in the twenty seconds before a meeting — the
exact budget Principle V says the tool exists to protect.

So: no setting, on by default, and unconditional. If this turns out to be wrong, the evidence will be
a real user reporting a real conversion they did not want, and the fix at that point is more likely to
be a narrower detection rule than a switch.

---

## Is it a surprise, and is that acceptable?

Yes, it is a change the user did not type, and yes, unconditionally acceptable — for the reasons above
and on these terms, which are part of the feature rather than mitigations bolted to it:

- It is **announced** (FR-025) and **shown** (FR-026) at the moment it happens, in the buffer the user
  is looking at.
- It is **bounded** to the file they just saved (FR-015, FR-016, FR-019). No file the user was not
  actively editing is ever written.
- It is **reversible by hand** and trivially so (FR-028). Nothing is deleted, so nothing has to be
  recovered.
- It is **exactly reversible in principle**: the transformation adds four characters and a duplicate
  of a substring, and removes nothing. It has an inverse. Contrast with a rewrite that shortened,
  reflowed, or re-encoded anything, which would not, and which this spec forbids.

---

## Key Entities

- **Bare URL**: a run of text in a document body starting `http://` or `https://`, delimited on the
  left by a line start or an opening character and on the right by FR-013's boundary rule, sitting in
  none of the excluded contexts. It has no identity, is never stored, and is recomputed from the text
  every time.
- **Excluded context**: a span of the document — a code fence, a code span, the frontmatter block, an
  HTML comment, an existing link or image, an autolink, an HTML tag, a link reference definition —
  inside which no conversion happens. Recognising these is the entire risk surface of the feature.
- **Conversion count**: how many bare URLs one save rewrote. Reported to the editor's status line and
  to nothing else; never persisted.

---

## Success Criteria *(mandatory)*

- **SC-001**: A document containing a bare `http://` or `https://` URL in ordinary body prose, saved
  once, contains a markdown inline link whose link text and whose destination are each the original
  URL byte-for-byte.
- **SC-002**: Saving any document a second time, with no edit in between, changes no byte except the
  `updated:` timestamp.
- **SC-003**: A single document carrying a URL in every excluded context named in FR-005 through
  FR-012a, saved once, differs from its input only in the `updated:` timestamp — zero other bytes.
- **SC-004**: Every input in the FR-013 boundary corpus (trailing `.`, `,`, `:`, `;`, `!`, `?`, quote,
  wrapping parentheses, balanced parentheses inside the URL, and the combinations in User Story 3)
  produces the exact expected output string.
- **SC-005**: `choom links check` over a workspace reports an identical set of stale and dead links
  before and after every document in that workspace has been opened and saved once.
- **SC-006**: Running `choom links heal` and `choom links check` over a workspace containing bare URLs
  converts zero of them and writes zero files that had no stale record link.
- **SC-007**: Saving a 200 KB document containing no URL adds no perceptible time to the save; the
  detection pass is a scan of a string already in memory and performs no file read.
- **SC-008**: A file that has been through a save is readable by a strict CommonMark parser with no
  linkify extension and yields a link element for every URL that was converted.

---

## Out of Scope

- `www.` hosts and bare email addresses. The issue names two schemes; a `www.` prefix is a convention
  rather than a scheme and appears in prose (`see the www. variant`) in a way `https://` does not.
  Adding them later is a widening of FR-002 and costs nothing to defer.
- Other schemes: `mailto:`, `ftp:`, `file:`, and anything else.
- Fetching a page title to use as link text. It requires network access, which no choom operation may
  require, and it would replace the URL the user typed with text they did not — the opposite of this
  feature's premise.
- Shortening or prettifying the displayed URL (e.g. `[example.com](https://example.com/very/long)`).
  It hides part of what the user wrote behind display text, which is a Principle IV question this
  feature has no need to open.
- Converting URLs anywhere outside the two save paths in FR-015 — no repair command, no
  `links autoformat`, no whole-workspace pass.
- Any change to how external links are clicked, rendered, or displayed. That path already works.
- Turning a converted external link into a first-class record link, or listing it in the Links pane.
  External URLs are outside the id-and-path grammar by design.

---

## Assumptions

- The user wants the URL itself as the visible link text. Nothing else is available without a network
  call, and it is what preserves the rendered appearance exactly (Overview).
- The two save gestures in FR-015 are the complete set of "the user asked for their text to be
  written" moments in choom today. If a third is added, it inherits this behaviour.
- Documents are small enough — hundreds to low thousands of lines — that a full-text scan on save is
  free, consistent with the same assumption the rest of choom is built on.
- The existing destination-escaping rule (angle-bracket wrapping for a destination containing a space,
  `(`, `)`, `<`, or `>`) is correct and is reused rather than re-derived.
- `choom links check` and `heal` will continue to skip destinations carrying a URL scheme. FR-020
  depends on it, and FR-021 is the test that keeps it true.
