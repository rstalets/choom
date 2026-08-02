# Contract: what a save does to the text

**Feature**: `018-automatic-link-detection`

This is the contract with the **file**, not with a caller. It is what a person hand-editing a note, an
assistant writing markdown, and any markdown viewer can rely on. Everything else in this feature is
downstream of it.

Every row below was executed against a faithful prototype of the algorithm. **0 failures.** These
three corpora become `tests/unit/test_bare_url_format.py` verbatim.

---

## The rule, in one sentence

On a save the user performed in choom's editor, each bare `http://` or `https://` URL in the document
body is replaced by `[<url>](<destination>)`, where the URL appears byte-for-byte in both slots and
`<destination>` is angle-wrapped only when it contains ` `, `(`, `)`, `<`, or `>`.

---

## Grammar

```
candidate   := (?i) "http" "s"? "://" [^ \t\r\n<>\[\]]*
leading     := start-of-text | one of  whitespace ( [ { " ' * _ ~ | >
trailing    := trim repeatedly:  [ . , : ; ! ? ' " * _ ~ ]
                                 | ")" when count(")") > count("(")
accepted    := candidate has >= 1 character after "://" post-trim
               and contains no "[" or "]"
output      := "[" url "]" "(" destination ")"
destination := url  |  "<" url ">"      -- angle-wrapped iff url contains one of  ()<> or space
```

`<` is deliberately absent from `leading`. That single omission is what makes the CommonMark autolink
`<https://example.com>` non-convertible before any mask is consulted.

---

## Corpus A — converted

| Input | Output |
|---|---|
| `See https://example.com/spec for details.` | `See [https://example.com/spec](https://example.com/spec) for details.` |
| `Read https://example.com/a.` | `Read [https://example.com/a](https://example.com/a).` |
| `Read https://example.com/a, then stop` | `Read [https://example.com/a](https://example.com/a), then stop` |
| `(https://example.com/a)` | `([https://example.com/a](https://example.com/a))` |
| `https://en.wikipedia.org/wiki/Foo_(bar)` | `[https://en.wikipedia.org/wiki/Foo_(bar)](<https://en.wikipedia.org/wiki/Foo_(bar)>)` |
| `(https://en.wikipedia.org/wiki/Foo_(bar))` | `([https://en.wikipedia.org/wiki/Foo_(bar)](<https://en.wikipedia.org/wiki/Foo_(bar)>))` |
| `"https://example.com/a"` | `"[https://example.com/a](https://example.com/a)"` |
| `https://example.com/a?q=1&r=2#frag` | `[https://example.com/a?q=1&r=2#frag](https://example.com/a?q=1&r=2#frag)` |
| `http://legacy.internal/report` | `[http://legacy.internal/report](http://legacy.internal/report)` |
| `**https://example.com/a**` | `**[https://example.com/a](https://example.com/a)**` |
| `*https://example.com/a*` | `*[https://example.com/a](https://example.com/a)*` |
| `- item https://example.com/a, next` | `- item [https://example.com/a](https://example.com/a), next` |
| `a https://x.com/1 b https://x.com/2 c` | both converted independently |
| `# Heading https://example.com/a` | `# Heading [https://example.com/a](https://example.com/a)` |
| `HTTPS://EXAMPLE.COM/A` | `[HTTPS://EXAMPLE.COM/A](HTTPS://EXAMPLE.COM/A)` — scheme matched case-insensitively, case preserved |
| `see https://example.com/a; also` | `;` outside |
| `done https://example.com/a!` | `!` outside |
| `\| https://example.com/a \| next \|` | converted inside a table cell |
| `> quoted https://example.com/a here` | converted inside a blockquote |
| `trailing slash https://example.com/` | `/` kept — it is not trailing punctuation |
| `stray paren https://example.com/a)` | `)` outside — unbalanced |
| `both https://example.com/a).` | both `)` and `.` outside |
| `ellipsis https://example.com/a...` | all three dots outside |
| `(see https://example.com/a).` | `)` and `.` outside |
| `    https://example.com/a` | converted — indented blocks are **not** masked (research R8) |

---

## Corpus B — byte-identical, no conversion

| Input | Why |
|---|---|
| ```` ```\ncurl https://api.example.com/v1\n``` ```` | fenced code block |
| `~~~\nhttps://example.com/a\n~~~` | tilde fence |
| ```` ```\nunclosed fence https://example.com/a ```` | unclosed fence masks to end of file |
| `` `https://example.com` `` | inline code span |
| `[the spec](https://example.com/spec)` | existing link — destination |
| `[https://a.example](https://a.example)` | existing link — **link text**; this is the idempotency case |
| `[a](https://x.com/Foo_(bar))` | unescaped balanced parens — the form `_LINK_RE` misses (R1) |
| `[a](<https://x.com/Foo_(bar)>)` | angle-wrapped destination |
| `<https://example.com>` | CommonMark autolink |
| `![screenshot](https://example.com/a.png)` | image |
| `[spec]: https://example.com/spec` | link reference definition |
| `<a href="https://example.com">x</a>` | raw HTML tag attribute |
| `- [ ] call Terry <!-- id:task_a1b2 links:meeting_1 created:2026-07-30 -->` | task metadata comment |
| `<!--\nsee https://example.com/a\n-->` | multi-line HTML comment |
| frontmatter with `title: https://example.com/a` | frontmatter block (R3) |
| `text https:// more` | no host after `://` |
| `xhttps://example.com/a` | fails the leading boundary |
| `https://[::1]/status` | contains `[` / `]` (FR-012a) |

---

## Corpus C — adversarial

Fifteen cases built to break the masks rather than to exercise the happy path. Each was run; the
"result" column is what the prototype produced.

| Input | Result |
|---|---|
| `[a](<notes/Q3 (draft).md#note_1>)` | unchanged — choom's own escaped record link |
| `[a](<notes/Q3 (draft).md#note_1> )` | unchanged — trailing space before `)` |
| `[a](<https://x.com/Q3 (draft>)` | unchanged — unbalanced paren defeats mask 5's depth counter; **mask 6 backstops it** |
| ```` ```https://example.com/a\nbody\n``` ```` | unchanged — a URL in a fence info string |
| `[[wiki]] https://example.com/a` | URL converted, `[[wiki]]` untouched |
| `[unclosed\n\nplain https://example.com/a\n` | URL converted — an unclosed `[` must not swallow the rest of the file |
| `see ] https://example.com/a` | URL converted — a stray `]` in prose |
| `see ( https://example.com/a` | URL converted — a stray `(` in prose |
| `` `[x]` then https://example.com/a `` | URL converted, code span untouched |
| `[a](x.md#note_1) https://example.com/a [b](y.md#note_2)` | only the middle URL converted |
| `![i](p.png) https://example.com/a` | URL converted, image untouched |
| `text https://example.com/a <!-- id:task_a1b2 -->` | URL converted, comment untouched |
| `    https://example.com/a` | **converted** — indented code blocks are not masked (research R8, accepted) |
| `end https://example.com/a\nnext line` | converted; the following line untouched |
| `a https://example.com/a\nb\n` | converted; newline count unchanged |

---

## Corpus D — idempotency

For **every** input in Corpus A: `f(x)` == `f(f(x))` == `f(f(f(x)))`, byte for byte.

Three passes, not two. A defect that is stable at pass 2 but not pass 3 is exactly the compounding
shape this guards against: had the link mask covered only the destination and not the link text, pass
2 would yield `[[U](U)](U)` and pass 3 `[[[U](U)](U)](U)`.

**This is the single most important assertion in the feature.** Every subsequent save re-runs the
transform over already-converted text; if it is not exactly idempotent, the user's file degrades a
little on every save, silently, forever.

---

## Whole-document guarantees

Verified on a document containing frontmatter, a bare URL, a record link, a task mirror, a fenced
code block, and a URL with balanced parens:

| Guarantee | Verified |
|---|---|
| Frontmatter still parses; title unchanged | yes |
| `find_links` returns an identical set — same lines, ids, and paths | yes |
| `find_mirrors` returns an identical set | yes |
| Newline count identical (no line inserted or removed) | 19 → 19 |
| `stamp_updated` still locates its line afterwards | yes |
| Second pass reports 0 conversions | yes |

---

## What is out of the grammar

`www.` hosts, bare email addresses, and every scheme other than `http`/`https` — `mailto:`, `ftp:`,
`file:`, `s3:`. A bare URL is never shortened, percent-encoded, case-folded, or given or denied a
trailing slash. The file's line endings and trailing-newline state are decided by
`_apply_line_ending_policy`, exactly as before.
