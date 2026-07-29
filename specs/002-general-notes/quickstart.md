# Quickstart: Validating General Notes

**Feature**: `002-general-notes` | **Plan**: [plan.md](./plan.md)

A runnable pass that proves the feature end to end. Every step maps to a spec acceptance scenario;
the mapping is in the last section. Details of *what* each command guarantees live in
[contracts/cli.md](./contracts/cli.md) and [contracts/tui.md](./contracts/tui.md) — this page is the
order to run things in and what to look for.

---

## Prerequisites

```bash
uv sync                       # dev environment, no admin rights needed
uv run pytest                 # baseline: feature 001's suite must be green before you start
```

**Stage 0 gate.** The core generalisation ([R1](./research.md#r1-how-notes-share-code-with-meetings),
[R2](./research.md#r2-naming-and-backward-compatibility-of-the-core-api)) is a refactor with no
user-visible effect. Its acceptance criterion is that the command above stays green **with no test
file edited**. If a 001 test needs changing, the aliases-only premise has broken — fix that before
building notes on top of it.

---

## Setup

```bash
mkdir -p /tmp/ep-notes && cd /tmp/ep-notes
uv run endpaper init
```

Expected: the workspace root path on stdout, exit 0, and `notes/daily/` already present — feature
001 creates it, so there is no migration in this feature (SC-010).

```bash
ls notes/daily/               # exists, empty
```

---

## 1. The daily note is idempotent (US1)

The core promise of §3.2, and the one worth checking most carefully.

```bash
uv run endpaper note today
# → notes/daily/2026-07-28.md

echo "called the vendor, they want a call back friday" >> notes/daily/2026-07-28.md

# capture the file exactly as it is now
cp notes/daily/2026-07-28.md /tmp/ep-before.md
stat -f %m notes/daily/2026-07-28.md > /tmp/ep-before.mtime   # Linux: stat -c %Y

uv run endpaper note today
# → notes/daily/2026-07-28.md   (same line)

diff /tmp/ep-before.md notes/daily/2026-07-28.md          # must be empty
stat -f %m notes/daily/2026-07-28.md | diff - /tmp/ep-before.mtime   # must be empty
ls notes/daily/ | wc -l                                    # must be 1
```

**What to look for**: identical output both times, one file, byte-identical content, and an
unchanged mtime. The mtime check is not pedantry — on a synced folder a no-op rewrite still costs
the user an upload, so [R10](./research.md#r10-test-strategy-for-the-file-did-not-change) makes it
part of the contract.

**Idempotence under concurrency** — the property `O_EXCL` buys
([R3](./research.md#r3-making-the-daily-note-idempotent-without-a-read-modify-write)):

```bash
rm notes/daily/*.md
for i in $(seq 1 20); do uv run endpaper note today & done; wait
ls notes/daily/ | wc -l        # must be 1
```

**A broken daily note still opens** (FR-005):

```bash
printf -- '---\nid: [unclosed\n' > notes/daily/2026-07-28.md
uv run endpaper note today     # → notes/daily/2026-07-28.md, exit 0, file untouched
uv run endpaper note list      # the broken file is absent; a warning is on stderr
ls notes/daily/ | wc -l        # still 1 — no second file for the day
```

Listing and daily-note resolution disagree here on purpose: listing reports what parses, the daily
note is defined by its path.

**A missing directory is recreated** (FR-006):

```bash
rm -rf notes/daily && uv run endpaper note today && ls notes/daily/
```

---

## 2. Typed and untyped notes (US2)

```bash
uv run endpaper note new "vendor landscape" --type research --tag procurement
# → notes/2026-07-28-research-vendor-landscape.md

uv run endpaper note new "some idea"
# → notes/2026-07-28-some-idea.md          (untyped: no type segment)

uv run endpaper note new "vendor landscape" --type research
# → notes/2026-07-28-research-vendor-landscape-2.md   (collision suffixed, original untouched)

uv run endpaper note new "quick thought #ideas #ideas"
# tags deduplicated; "#ideas" stripped from the title
```

Check the frontmatter carries the six fields, an `n_` id prefix, and the tag:

```bash
head -8 notes/2026-07-28-research-vendor-landscape.md
```

**The reserved type is refused before anything is written** (FR-012):

```bash
uv run endpaper note new "x" --type daily; echo "exit=$?"
# stderr: endpaper: type 'daily' is reserved; use 'endpaper note today' for the daily note
# exit=2, and no new file in notes/
```

**A crafted type cannot escape `notes/`** (FR-013):

```bash
uv run endpaper note new "x" --type ../../etc; echo "exit=$?"   # exit=2, nothing written
```

---

## 3. Listing, filtering, and separation (US3)

```bash
uv run endpaper note list                    # daily and typed together, newest first
uv run endpaper note list --json | python3 -m json.tool
uv run endpaper note list --type daily       # only daily notes
uv run endpaper note list --tag procurement --since 2026-07-01
```

**The JSON has the same seven keys as meetings** — no key added for this feature:

```bash
uv run endpaper note list --json | python3 -c "
import json,sys
keys = {tuple(sorted(o)) for o in json.load(sys.stdin)}
assert keys <= {('created','id','path','tags','title','type','updated')}, keys
print('schema ok')"
```

**Notes and meetings never mix** (FR-018):

```bash
uv run endpaper meeting new "Q3 planning" --type standup
uv run endpaper meeting list --json | grep -c '"path": "notes/'   # must be 0
uv run endpaper note list   --json | grep -c '"path": "meetings/' # must be 0
```

**Non-markdown and stray directories are ignored** (FR-023):

```bash
touch notes/scratch.txt && mkdir -p notes/archive && touch notes/archive/old.md
uv run endpaper note list --json | grep -cE 'scratch\.txt|archive/'   # must be 0
```

**An empty workspace is not an error** (FR-022):

```bash
mkdir -p /tmp/ep-empty && (cd /tmp/ep-empty && uv run endpaper init && uv run endpaper note list --json)
# → [] , exit 0
```

---

## 4. The interface (US1–US3)

```bash
cd /tmp/ep-notes && uv run endpaper
```

| Do this | Expect |
|---|---|
| `/` then `notes` then `enter` | List switches to notes; status bar names the active collection |
| `/` then type `vendor` | Rows narrow live; no disk access per keystroke |
| `↑` `↓` `j` `k` | Selection moves, stops at both ends without wrapping |
| `enter` on a row | Full-screen **rendered** markdown — headings and lists formatted, no raw frontmatter |
| `esc` | Back to the list |
| `/` then `note` then `enter` | Today's daily note opens in preview — created if absent, opened untouched if not |
| `/` then `note vendor landscape` then `enter` | An **untyped note** is created; the daily note is not touched |
| `/` then `note.research an idea` then `enter` | A `research` note is created, preview opens on it |
| `/` then `note.research` then `enter` | Status-bar error naming the missing description; nothing created |
| `/` then `meetings` then `enter`, then back to `/notes` | Both lists current, including anything created this session |
| Look at the footer, in every state | Every active binding shown; **no edit key advertised** |
| `/` then ` notes` (leading space) | Stays in filter mode — the escape hatch still works |

**Check the empty state names the collection**: in a workspace with no notes, the message should say
notes and show how to create one.

---

## 5. The assistant contract (US4)

```bash
wc -l AGENTS.md                            # <= 58; the budget is ~60 (REQUIREMENTS.md §4.3)
grep -E 'note today|note new|note list' AGENTS.md    # all three documented
grep -- '--tag' AGENTS.md                  # the tag form is still stated explicitly
```

**Nothing blocks and nothing decorates when redirected**:

```bash
for c in "note today" "note new x" "note list" "note list --json"; do
  timeout 5 uv run endpaper $c > /tmp/out 2>/tmp/err </dev/null || echo "FAILED: $c"
  grep -qP '\x1b' /tmp/out && echo "ANSI LEAK: $c"
done
```

Expect no timeouts (nothing waits for input) and no ANSI bytes.

**Streams stay separated** — a warning must never land in stdout:

```bash
printf 'broken\n' > notes/2026-07-28-bad.md
uv run endpaper note list --json 2>/dev/null | python3 -m json.tool >/dev/null && echo "stdout still parses"
uv run endpaper note list --json 2>&1 >/dev/null | head -1     # the warning, on stderr
```

**Exit codes**:

```bash
uv run endpaper note new "x" --type daily; echo "expect 2, got $?"
(cd /tmp && uv run endpaper note list); echo "expect 3, got $?"
```

---

## 6. Automated suite

```bash
uv run pytest                       # everything, including 001's suite unchanged
uv run pytest tests/performance     # SC-005: scan and filter budgets, both collections
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

---

## Scenario coverage

| Spec scenario | Covered by |
|---|---|
| US1 1–6 (daily note) | §1 — creation, idempotence, bytes+mtime, concurrency, broken file, missing dir |
| US2 1–4, 6–7 (typed notes) | §2 — creation, collision, tags, reserved type, crafted type |
| US2 5 (`/note <desc>` is not the daily note) | §4, command-bar row |
| US3 1–3, 8 (interface list) | §4 — switching, filtering, preview, currency |
| US3 4–7 (CLI list) | §3 — JSON schema, filters, separation, empty result |
| US4 1–4 (assistant) | §5 — AGENTS.md, no blocking, streams, exit codes |
| SC-002, SC-003 (idempotence, no modification) | §1, and `tests/integration/test_daily_note.py` |
| SC-005 (performance) | §6 |
| SC-010 (no migration) | Setup, and §3's empty-workspace check |
| SC-011 (cross-platform) | §6 on each target OS; `stat` differs per platform as noted in §1 |
