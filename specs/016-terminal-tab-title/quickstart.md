# Quickstart: Validating the terminal tab title

**Feature**: `016-terminal-tab-title` | **Date**: 2026-08-02

How to prove the feature works. Automated checks first, then the manual passes that only a real terminal
can settle.

## Prerequisites

```bash
uv sync --extra dev          # or: pip install -e '.[dev]'
mkdir -p /tmp/work-notes && cd /tmp/work-notes && choom init
```

## Automated

```bash
scripts/dev-tests.sh                                   # whole suite
scripts/dev-tests.sh tests/unit/test_workspace_title.py    # core composition rules
scripts/dev-tests.sh tests/unit/test_terminal_title.py     # emitter, against a fake stream
scripts/dev-tests.sh tests/contract/test_no_ansi.py        # FR-016: no escape bytes from any subcommand
scripts/dev-tests.sh tests/integration/test_tui_launch.py  # launcher wiring
```

Expected: all green. The contract file is the one to watch — it is what stops a future change from
letting an escape sequence into a stream an AI assistant parses.

## The non-TTY guarantee, by hand

```bash
cd /tmp/work-notes
choom task list | cat -v | grep -c '\^\[' ; echo "expect 0"
choom task list --json > /tmp/out.json 2>/tmp/err.txt
grep -c $'\x1b' /tmp/out.json /tmp/err.txt ; echo "expect 0 and 0"
choom < /dev/null > /tmp/tui.txt 2>&1 ; echo "exit $?"   # refuses; expect exit 3
grep -c $'\x1b' /tmp/tui.txt ; echo "expect 0"
```

## What the terminal actually shows

Each of these needs eyes on a tab strip; none can be asserted in CI.

**1. The title appears (US1, FR-001).** Open at least three tabs. In one, `cd /tmp/work-notes && choom`.
That tab should read `choom — work-notes` while the others are unchanged.

**2. It does not churn (FR-009).** With choom open, press `tab` between collections, change month in the
scope pane, press `/` and filter, open a record, edit it, save it. The tab title must not flicker or
change once.

**3. Every exit restores it (US2, FR-011).** From a fresh launch each time:

| Route | Expected |
|---|---|
| `ctrl+q`, nothing unsaved | Exits at once; tab no longer reads choom's title. |
| `ctrl+q` with a dirty editor, then confirm discard | Exits; tab restored. |
| `ctrl+q` with a dirty editor, then **cancel** | Still running; tab **still** reads `choom — work-notes` (FR-012). |
| `ctrl+c` while running | choom stays open and shows "Press ctrl+q to quit" — Textual's own binding. This is not an exit path (research R4). |
| `kill -INT <pid>` from another tab | Process ends; tab restored. |

On a terminal with a title stack (iTerm2, Windows Terminal, GNOME Terminal, kitty, alacritty) the tab
returns to exactly what it read before. On one without, it goes empty and the shell reclaims it at the
next prompt — either outcome satisfies FR-010.

**4. Awkward names (FR-002, FR-004, FR-005, FR-006).**

```bash
mkdir -p "/tmp/Notas de reunión" && (cd "/tmp/Notas de reunión" && choom init && choom)
# expect: choom — Notas de reunión

mkdir -p /tmp/$(python3 -c "print('x'*70)") && (cd /tmp/$(python3 -c "print('x'*70)") && choom init && choom)
# expect: truncated with a trailing …, 64 characters total

mkdir -p "$(printf '/tmp/inject\aecho pwned')" && (cd "$(printf '/tmp/inject\aecho pwned')" && choom init && choom)
# expect: choom — injectecho pwned, and no command executed by the terminal
```

**5. tmux.** Run choom inside tmux with `set -g set-titles on`. The outer terminal's tab should take the
title. With `set-titles off` it will not — that is tmux's setting, not a choom bug (FR-020).

**6. Windows.** In Windows Terminal, launch choom and confirm the tab renames and restores. In a legacy
console window, launch and quit choom and confirm the session output is byte-identical to today's — no
title change and, critically, no literal `←]0;…` text anywhere (FR-022).

## Release checklist

Per `docs/REQUIREMENTS.md` §4.3, verify steps 1, 3, and 6 on Windows Terminal, iTerm2, macOS Terminal,
PuTTY, and inside tmux before release.

## Not to be done

`README.md` stays untouched. Per `CLAUDE.md`, the feature list describes the released version; this
behaviour joins it when `/release` cuts the version that carries it, and not before.
