# Quickstart: validating 001-meeting-notes

Runnable checks that prove the feature works end to end. Details live in
[contracts/](./contracts/) and [data-model.md](./data-model.md); this page is the run guide.

## Prerequisites

- Python 3.11+ and `uv`
- A clone of this repository, on branch `001-meeting-notes`

## Set up the development environment

```bash
uv sync --all-extras          # creates .venv from pyproject.toml
uv run endpaper --version     # smoke test: prints a version, exits 0
```

## Run the quality gates

These are the gates every pull request must pass (Principle VI).

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest -q
```

---

## Scenario 1 — install and initialize (spec US1)

```bash
cd "$(mktemp -d)"
uv run --directory /path/to/endpaper endpaper init
```

**Expect**: prints the workspace root, exits 0, and creates:

```
.endpaper/config.toml
AGENTS.md
meetings/
notes/daily/
tasks.md
```

Then confirm the guard rails:

```bash
endpaper init ; echo "exit=$?"        # already a workspace -> exit=3, nothing changed
cd /tmp && endpaper meeting list ; echo "exit=$?"   # outside a workspace -> exit=3
wc -l AGENTS.md                       # <= ~60 lines (FR-012)
grep -c -- --tag AGENTS.md            # >= 1: the tag form must be documented
```

## Scenario 2 — create a meeting (spec US2)

```bash
endpaper meeting new "Q3 planning" --type standup --tag platform
cat meetings/2026-*-standup-q3-planning.md
```

**Expect** a path on stdout, exit 0, and frontmatter with exactly six keys in fixed order, `type:
"standup"`, `tags: ["platform"]`, `title: "Q3 planning"`, and `created == updated`.

Collision and tag handling:

```bash
endpaper meeting new "Q3 planning" --type standup     # -> ...-q3-planning-2.md
ls meetings/                                          # two files, first untouched
endpaper meeting new "vendor call #procurement #legal" # tags parsed out of the quoted description
endpaper meeting new "hallway chat"                    # untyped -> no type segment in the filename
```

## Scenario 3 — browse and filter (spec US3)

```bash
endpaper meeting list                                  # tab-separated, newest first
endpaper meeting list --json | python -m json.tool     # parses; exactly 7 keys per object
endpaper meeting list --type standup --tag platform    # filters combine conjunctively
endpaper meeting list --since 2026-07-01
endpaper meeting list --since yesterday ; echo "exit=$?"   # -> exit=2
```

In the TUI:

```bash
endpaper
```

- `/` opens the bar; type `vendor` and watch the list narrow live; footer reads `[filter]`
- `/` then `meeting.standup Q3 planning #platform`; footer reads `[command: meeting.standup]`;
  `enter` creates the file and lands you in its preview
- `j`/`k` and arrows move and stop at both ends; `enter` opens; `esc` returns; `ctrl+q` quits
- Every listed binding is visible in the footer

## Scenario 4 — the AI-facing contract (spec US4)

The point of these is that they run with **no terminal attached**.

```bash
endpaper meeting list --json > out.json 2> err.txt
python -c "import json;json.load(open('out.json'))"        # parses: no banner, no preamble
grep -c $'\x1b' out.json ; echo "expect 0"                  # no ANSI in redirected output
test ! -s err.txt && echo "stderr clean"
```

Malformed input must not contaminate stdout or destroy data:

```bash
printf -- '---\nid: broken\n' > meetings/2026-07-28-broken.md
cp meetings/2026-07-28-broken.md /tmp/before.md
endpaper meeting list --json > out.json 2> err.txt ; echo "exit=$?"   # exit=0
python -c "import json;print(len(json.load(open('out.json'))))"       # every well-formed meeting
cat err.txt                                                            # one warning naming the file
diff /tmp/before.md meetings/2026-07-28-broken.md && echo "file untouched"
```

The last line is the one that matters: Principle IV means a file we could not parse is a file we did
not touch.

Timeouts prove nothing blocks:

```bash
timeout 10 endpaper meeting list --json < /dev/null ; echo "exit=$?"   # not 124
```

---

## Performance checks (SC-004, SC-005)

```bash
uv run python -m tests.fixtures.generate --count 1000    # 1,000 meetings
time endpaper meeting list --json > /dev/null            # well under 2s
uv run pytest tests/performance -q                       # asserts scan < 2s, filter < 100ms
```

## Cross-platform (SC-010)

Run the full suite on Windows, macOS, and Linux. Two checks that only fail on Windows:

```bash
endpaper meeting new "café résumé — naïve"    # non-ASCII: slug is ASCII, title is not
endpaper meeting list --json | grep '"path"'  # forward slashes on every platform
```

Path budget: generated paths stay ≤120 characters below the workspace root
([research.md R10](./research.md#r10-windows-path-length)), asserted by a test rather than measured
by hand.
