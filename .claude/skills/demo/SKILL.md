---
name: "demo"
description: "Create a throwaway endpaper workspace under /tmp, populate it with realistic meetings, notes, and tasks -- including cross-record links -- and hand back ready-to-use prompts for exercising an AI assistant against it."
argument-hint: "[path] (default: a fresh /tmp/endpaper-demo-<timestamp> directory)"
metadata:
  author: "endpaper"
user-invocable: true
disable-model-invocation: false
---

## Purpose

Stand up a disposable endpaper workspace populated with enough realistic, varied content to
demonstrate every shipped feature at once -- multiple meeting/note types, multi-month history,
tagging, open and completed tasks with bodies, and cross-record markdown links -- so it can be
used for screenshots, docs, or a live walkthrough without hand-typing sample data.

It also has a second job: this workspace is a natural test bed for an AI assistant working
non-interactively in an endpaper vault (the whole point of `AGENTS.md`, `--json`, and the
CLI-first design). So the skill's last step hands back a list of prompts -- referencing the
actual names, dates, and topics it just created -- that someone can paste into an assistant
session to watch it search, cross-reference, and write into the vault.

This workspace lives under `/tmp`. It is scratch content, not part of the repo -- don't create it
inside a git worktree, and don't commit anything from it.

## Step 1 — Find the `endpaper` executable

Don't assume `endpaper` is on `PATH`, and don't assume any particular worktree path -- other
people (and other worktrees) will run this skill too.

1. Try `endpaper --version`. If it works, use `endpaper` directly for every command below.
2. Otherwise, find an endpaper source checkout to run against: starting from the current
   directory and walking up, then checking common locations, look for a directory containing
   `pyproject.toml` whose `[project] name = "endpaper"`. Use
   `uv run --project <that-path> endpaper` in place of `endpaper` for every command below.
3. If neither resolves, stop and tell the user endpaper isn't available to run.

## Step 2 — Create and init the workspace

```bash
WORKDIR="${1:-/tmp/endpaper-demo-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$WORKDIR" && cd "$WORKDIR"
endpaper init
```

If the path was user-supplied and already contains a workspace (`.endpaper/config.toml`
exists), ask before reusing/overwriting it rather than assuming.

## Step 3 — Check what's actually shipped

Run `endpaper --help` and `endpaper <subcommand> --help` for each subcommand before populating.
Feature surface has moved fast in this repo (document links, in particular, may or may not have
landed yet) -- **build the demo around what this build actually supports, not around what
REQUIREMENTS.md aspires to.** Two things specifically to check:

- Is there a `link`/`links` subcommand? If yes, read its `--help` and use it for Step 6. If no,
  fall back to hand-written relative markdown links (Step 6 covers both).
- Does `task add`/`meeting new`/`note new` support anything beyond `--type`/`--tag` in this
  build? Use whatever's actually there.

## Step 4 — Populate meetings and notes across several months

The CLI only stamps "today." To demonstrate month-scoped browsing (the top collection bar,
`/filter` across months, etc.), most content needs to be spread across at least 3-4 different
months, which means hand-writing some files directly rather than only shelling out to the CLI --
this is intentional and safe: endpaper's own docs describe these files as plain, hand-editable
markdown with no index or database, so a well-formed hand-written file is indistinguishable from
a CLI-generated one.

For **today's** content, use the real CLI so ids/timestamps are authentic:

```bash
endpaper meeting new "Q3 planning" --type standup --tag platform
endpaper meeting new "Acme Corp renewal" --type vendor --tag procurement
endpaper note new "vendor landscape" --type research --tag procurement
endpaper note today
```

For **past months**, hand-write additional files following the exact schema (confirm current
field names against a CLI-generated file from Step 4's first commands, in case it's drifted):

```
meetings/YYYY/MM/YYYY-MM-DD-<type>-<slug>.md
notes/YYYY/MM/YYYY-MM-DD-<type>-<slug>.md
notes/daily/YYYY/MM/YYYY-MM-DD.md
```

```yaml
---
id: m_YYYYMMDD_<8 hex chars>       # m_ for meetings, n_ for notes
type: "standup"                    # "" if untyped
title: "Q2 planning"
tags: ["platform"]                 # [] if none
created: YYYY-MM-DDTHH:MM:SS
updated: YYYY-MM-DDTHH:MM:SS       # equal to created unless simulating an edit
---

<body -- see Step 5>
```

Generate distinct, plausible ids (random 8 hex chars is fine -- uniqueness is what matters, not
cryptographic quality). Cover a spread of meeting types (`standup`, `1on1`, `vendor`, `retro`,
and one untyped) and note types (several `research`/`decision`/similar, plus at least one daily
note per represented month), reusing a handful of tags across records (e.g. `platform`,
`procurement`, `onboarding`) so tag-filtering has something real to demonstrate.

Compute all dates relative to **today** (`date` arithmetic, not hardcoded years) -- the demo
prompts in Step 9 will reference "last week" and similar, and those only make sense if the
underlying dates actually are last week relative to whenever this skill runs.

**Name at least one person explicitly**, on a `1on1` or `vendor` meeting dated within the last
7 days (e.g. "1:1 with Bob" or "Vendor sync with Priya from Acme"). Give that meeting a body that
raises something actionable (a question to research, a decision pending data), and make sure a
task or note elsewhere in the workspace plausibly follows from it -- this is what makes a prompt
like "find the meeting I had with Bob last week and do the research it calls for" resolvable
against real content instead of hypothetical content.

## Step 5 — Give records actual body content

A record with an empty body (all a fresh CLI-created file has) doesn't demonstrate the markdown
preview, so write a few sentences of plausible body content into every hand-written file, and
back-fill the CLI-created ones from Step 4 the same way (open and edit them directly -- there's
no CLI command for writing body content in this build). Make it read like real notes: bullet
points, a small table or checklist somewhere, a heading or two -- varied enough to show off
rendering, not a single flat paragraph repeated everywhere.

## Step 6 — Tasks: open, done, with bodies, and tagged

```bash
endpaper task add "send the vendor comparison" --type followup --tag procurement
endpaper task add "buy milk" --type personal
endpaper task add "write onboarding doc" --type followup --tag onboarding
# ...several more, spanning a few --type values and reusing Step 4's tags
endpaper task done <id-of-one-or-two>
```

`task add` prints the new task's id. For a task that should carry a body (per `AGENTS.md`: a
blank line then indented lines beneath the checkbox line), edit `tasks.md` directly:

```
- [ ] send the vendor comparison <!-- id:t_xxxx type:followup tags:procurement created:YYYY-MM-DD -->

  Need the Q3 numbers before the renewal call. See the vendor landscape note for context.
```

Give at least one task a multi-line body, and leave most tasks without one -- a demo where every
task has a body doesn't show the contrast.

## Step 7 — Cross-record links

Whether or not a formal `link`/`links` subsystem exists in this build (Step 3), the underlying
files are plain markdown, so linking works either way:

- **If a `link` command exists:** use it as documented by its `--help` to connect a couple of
  records (e.g. the vendor renewal meeting to the vendor comparison task).
- **Always, regardless:** write a few real relative markdown links directly into body content
  from Step 5/6 -- e.g. a task body linking to the meeting note that spawned it, a note linking
  to an earlier daily note, a meeting's body linking to a related task. Use correct relative
  paths (e.g. from `tasks.md` at the workspace root to `meetings/2026/07/...md`) so the links
  actually resolve if clicked or opened.

## Step 8 — Verify and summarize

```bash
endpaper meeting list --json
endpaper note list --json
endpaper task list --all --json
```

Confirm counts look right (multiple months represented, a mix of types/tags, at least one done
task, at least one task with a body). Then tell the user:

- The workspace path, and that `cd <path> && endpaper` opens the TUI.
- A quick tally: meetings/notes per month, task counts (open/done), which records carry links.
- That the directory is scratch and safe to delete when they're done with it.

## Step 9 — Hand back demo prompts

Write a short list (6-10) of natural-language prompts someone can hand to an AI assistant
(Claude Code, Copilot, whatever's `cd`'d into the workspace) to exercise it end-to-end. These
must reference the **specific** content just created -- names, meeting types, tags, dates -- not
generic placeholders, so they resolve to a real answer instead of requiring the tester to go
look up what exists first.

Cover a spread of interaction shapes, not just lookups:

- **Find + act + create**, the flagship multi-step case: e.g. "Find the meeting I had with Bob
  last week, do the research it calls for, and write up a new note with what you find."
- **Simple query**: e.g. "What are my incomplete to-dos?" or "What did we decide in the retro
  last month?"
- **Filtered browse**: e.g. "Show me everything tagged #procurement." (use a tag actually used
  in Step 4/6)
- **Follow a link**: e.g. "Open the task linked from last week's vendor sync and tell me what's
  blocking it." (only if Step 7 actually produced a link there)
- **Write/update**: e.g. "Mark the 'write onboarding doc' task done and add a note about how it
  went." (use a task description actually created)
- **Cross-record synthesis**: e.g. "Summarize everything related to the Acme renewal across
  meetings, notes, and tasks."

Present these as a plain numbered list in your final message (not just left in a file) --
they're meant to be copy-pasted immediately into whatever assistant session is testing the
workspace.
