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

**This skill must not hardcode endpaper's feature set.** endpaper ships fast, and whatever
commands, frontmatter fields, or conventions this file describes are a snapshot from whenever it
was last written -- they will drift. `endpaper init` regenerates `AGENTS.md` fresh, for exactly
the version installed, every time. Read that file (Step 3) and treat it as the authoritative
spec for this run; treat anything below that conflicts with it as stale and defer to the file.
The goal is that a new feature landing (a new command, a new frontmatter field, a new way to
capture content -- e.g. a `/task` capture triggered from inside a note or meeting body, which
didn't exist when this skill was first written) should make the demo richer automatically,
without anyone having to edit this file.

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

## Step 3 — Learn this build's feature set from AGENTS.md

`endpaper init` (Step 2) just wrote a fresh `AGENTS.md` at the workspace root, generated for
whatever version is actually installed. Read it in full before populating anything -- it is kept
deliberately short (~60 lines) precisely so an assistant can absorb it in one read and be
productive immediately, which is exactly the job here. Pull out:

- **Layout** -- which collections exist (meetings, notes, daily notes, tasks, others not listed
  in this skill) and where each lives.
- **Frontmatter** -- the exact current field set and id-prefix scheme per collection. Use this,
  not the illustrative YAML in Step 4 below, if the two ever disagree.
- **Tasks** -- the current checkbox/metadata-comment/body format.
- **Commands** -- the full current command list and flags, including anything not mentioned
  anywhere in this skill.

Then run `endpaper --help` and `endpaper <subcommand> --help` for each subcommand, to fill in any
flag-level detail `AGENTS.md` doesn't spell out (it documents the concepts and common invocation,
not necessarily every flag).

**If either source reveals something this skill has no step for** -- a `link`/`links`/backlinks
command, a way to capture a task inline while editing a note or meeting, a new record type, a new
frontmatter field -- don't skip it because it isn't covered below. Fold it in: add example
content demonstrating it in Steps 4-7, and if it's something that only makes sense done live
(e.g. an interactive in-editor capture flow, not scriptable from a shell command), add a prompt
for it in Step 9 instead of trying to fake the artifact statically.

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

For **past months**, hand-write additional files following the schema from Step 3's `AGENTS.md`
read (the block below is illustrative only -- if it disagrees with what `AGENTS.md` or a
CLI-generated file from this step actually shows, the real file wins):

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
back-fill the CLI-created ones from Step 4 the same way. Use a CLI command for this if Step 3
turned one up (e.g. a `write`/`append` equivalent); otherwise edit the files directly -- these
are plain hand-editable markdown by design, so that's a legitimate way to populate them, not a
workaround. Make it read like real notes: bullet points, a small table or checklist somewhere, a
heading or two -- varied enough to show off rendering, not a single flat paragraph repeated
everywhere.

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
- **Anything Step 3 turned up that isn't on this list** -- a new command, an inline-capture
  flow, a linking feature -- gets a prompt of its own here, phrased against the actual content
  created for it. This is the mechanism that keeps the skill useful without editing it: new
  capability in, new demo prompt out.

Present these as a plain numbered list in your final message (not just left in a file) --
they're meant to be copy-pasted immediately into whatever assistant session is testing the
workspace.
