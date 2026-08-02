# Quickstart: validating bare-URL formatting on save

**Feature**: `018-automatic-link-detection`

How to prove the feature works, and how to prove it has not broken anything. Scenarios are ordered so
that a failure in an early one makes the later ones meaningless.

## Prerequisites

```bash
uv sync --extra dev
scripts/dev-tests.sh          # baseline: green before you start
```

A scratch workspace:

```bash
mkdir -p /tmp/qs018 && cd /tmp/qs018
choom init
choom note new "Vendor comparison"
```

---

## 1. The core function, with no terminal involved

The whole feature is decidable here. Everything else is plumbing.

```bash
python3 -c "
from choom.core.links import format_bare_urls
print(format_bare_urls('See https://example.com/a.')[0])
"
```

**Expect**: `See [https://example.com/a](https://example.com/a).` — with the full stop outside the
link.

---

## 2. Idempotency — the one that matters most

```bash
python3 -c "
from choom.core.links import format_bare_urls
t = 'Read https://example.com/a, and https://en.wikipedia.org/wiki/Foo_(bar).'
a = format_bare_urls(t)[0]
b = format_bare_urls(a)[0]
c = format_bare_urls(b)[0]
print(a)
print('idempotent:', a == b == c)
print('second pass conversions:', len(format_bare_urls(a)[1]))
"
```

**Expect**: `idempotent: True` and `second pass conversions: 0`.

If this fails, stop. Every subsequent save compounds the damage, and no other scenario is worth
running.

---

## 3. Nothing else in a document moves

Build one file carrying a URL in every excluded context and confirm it is inert.

```bash
python3 -c "
from choom.core.links import format_bare_urls
cases = [
  '\`\`\`\ncurl https://api.example.com/v1\n\`\`\`\n',
  '\`https://example.com\`',
  '[the spec](https://example.com/spec)',
  '[https://a.example](https://a.example)',
  '[a](https://x.com/Foo_(bar))',
  '<https://example.com>',
  '![i](https://example.com/a.png)',
  '[spec]: https://example.com/spec',
  '<a href=\"https://example.com\">x</a>',
  '- [ ] t <!-- id:task_a1b2 created:2026-07-30 -->',
  'https://[::1]/status',
  'text https:// more',
  'xhttps://example.com/a',
]
bad = [c for c in cases if format_bare_urls(c)[0] != c]
print('unchanged:', len(cases) - len(bad), '/', len(cases))
for c in bad: print('  CHANGED:', repr(c))
"
```

**Expect**: `unchanged: 13 / 13`.

The full corpus is [contracts/text-format.md](./contracts/text-format.md); this is the smoke subset.

---

## 4. Frontmatter survives

The failure this guards against makes a note vanish from the tool.

```bash
python3 -c "
from pathlib import Path
from choom.core.links import format_bare_urls
from choom.core.documents import _parse_document
t = open('$(ls notes/2026/*/*.md | head -1)').read().replace(
    'title:', 'title: https://example.com/a #', 1)
new, conv = format_bare_urls(t)
doc, warn = _parse_document(new, Path('x.md'))
print('conversions in frontmatter:', len([c for c in conv if c.start < t.index(chr(10)+'---')]))
print('parses:', doc is not None, '| warn:', warn.reason if warn else None)
"
```

**Expect**: zero conversions inside the frontmatter block, and the document still parsing.

---

## 5. A real save, end to end

```bash
choom
```

- Open the "Vendor comparison" note, press `e`.
- Type: `Ref https://intranet.example.com/procurement/q3 and https://en.wikipedia.org/wiki/Foo_(bar).`
- Press `ctrl+s`.

**Expect**:

- Both URLs become links **in the buffer**, immediately.
- The status line reads `formatted 2 links`.
- The cursor stays on the same line and is not sitting inside a URL.
- Press `ctrl+s` again with no edit: **no** `formatted…` message appears.

Then confirm the file:

```bash
grep -c '](http' notes/2026/*/*.md
```

---

## 6. The paths that must NOT convert

```bash
# An assistant writes a bare URL directly.
F=$(ls notes/2026/*/*.md | head -1)
printf '\nAssistant wrote https://example.com/untouched here.\n' >> "$F"
cp "$F" /tmp/qs018/before.md

choom links check
choom links heal
diff "$F" /tmp/qs018/before.md && echo "OK: heal/check converted nothing"
```

**Expect**: `OK: heal/check converted nothing`.

Then, in the TUI, **open** that note and leave without saving. The bare URL must still be bare.
Opening a task whose body contains a URL must likewise change nothing until `ctrl+s`.

---

## 7. The existing link subsystem is unaffected

```bash
choom links check --json > /tmp/qs018/links-before.json
# ...open and save every document in the TUI, then:
choom links check --json > /tmp/qs018/links-after.json
diff /tmp/qs018/links-before.json /tmp/qs018/links-after.json && echo "OK: identical"
```

**Expect**: `OK: identical` (SC-005). A converted link carries a URL scheme, so
`_link_from_match` declines it and it never becomes a record link, a Links-pane row, or a mirror.

---

## 8. Clicking still works

In the preview pane, click a converted link.

**Expect**: it opens in the browser, exactly as a bare URL already did — `resolve_href` returns `None`
for a scheme-carrying href and the handler falls through to `app.open_url` (FR-022).

---

## Test suite

```bash
scripts/dev-tests.sh tests/unit/test_bare_url_format.py
scripts/dev-tests.sh tests/unit/test_url_cursor_map.py
scripts/dev-tests.sh tests/integration/test_bare_url_save.py
scripts/dev-tests.sh                      # whole suite must stay green
```

Pay particular attention to `tests/integration/test_link_heal.py` and
`tests/integration/test_delete_mirrors.py` — they exercise `save_buffer` and are the existing tests
most likely to notice an unintended change to the save path.

## Cleanup

```bash
rm -rf /tmp/qs018
```
