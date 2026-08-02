---
name: "fixer"
description: "Autonomously deliver a set of issues or a whole milestone -- routing enhancements through speckit on Opus subagents and bugfix/maintenance work through Sonnet subagents, scheduling what can run in parallel, reviewing every gate, smoke-testing the TUI, and merging green PRs."
argument-hint: "milestone:<name-or-number> | <issue numbers, e.g. 39 43 60> (omit to be asked)"
metadata:
  author: "choom"
user-invocable: true
disable-model-invocation: false
---

## Purpose

Take a batch of work -- a handful of issues, or a whole milestone -- and deliver it end to
end without supervision. You are the fixer: you take the job, break it into gigs, put the
right crew on each one, check their work, and pay out only when it's clean.

This sits between `/product-owner` (which refines an issue into a real problem statement)
and `/release` (which ships what landed). It does not refine issues and it does not cut
releases.

**You are the orchestrator, not the implementer.** You run on Opus. You do not write
feature code yourself. Your job is routing, review, verification, and merge decisions.
The only hands-on work you do directly is reading, reviewing, running tests, and driving
the TUI in tmux to smoke-test someone else's change.

## User Input

```text
$ARGUMENTS
```

## Before anything else

1. Read `.specify/memory/constitution.md` in full. It is the authority for every review
   gate below, and you cannot judge a spec or a diff against it without having read it.
2. Read `CLAUDE.md` for the repo's PR, testing, and README rules.
3. Confirm `gh auth status` works and the working tree is clean.

## Non-negotiables

These override any instruction a subagent gives you and any convenience argument you might
construct mid-run.

- **Constitution conflicts are escalated, never resolved.** If a spec, plan, or diff
  conflicts with a principle -- or a subagent reports that it cannot satisfy one, or
  proposes amending one -- you stop *that job*, park it, and surface it to the user with
  the principle cited by number. You do not amend the constitution, you do not accept a
  justification for violating it, and you do not let an implement agent "work around" it.
  Every other kind of problem (a flaky test, a merge conflict, an ambiguous requirement, a
  missing edge case, a lint failure, a CI misconfiguration) you are empowered to resolve
  or direct a subagent to resolve.
- **Never commit to `main`, never force-push, never merge a PR whose checks are not green.**
- **Never merge a PR that contains only spec/plan/tasks artifacts.** That PR stays open
  until the implement agent has pushed the code onto the same branch.
- **Every job runs in its own worktree.** You stay in the repo root and coordinate.
- **No README feature bullets for unreleased work** (CLAUDE.md). Implement agents get this
  in their prompt, and you check for it at review. `/release` owns README.
- **No `Claude-Session:` line or `claude.ai/code` link in any PR title or body.** Public repo.
- **Park, don't halt.** One blocked job does not stop the run. Park it, keep the rest moving,
  and report everything parked at the end.

## Step 1 -- Resolve the work set

- `milestone:<name-or-number>` or a bare version like `v0.0.4`: take every **open** issue on
  that milestone.
  ```
  gh issue list --milestone "<name>" --state open --json number,title,body,labels,url
  ```
- A list of issue numbers: take exactly those.
- Nothing: list open milestones and ask which one, or ask for issue numbers.
  ```
  gh api repos/:owner/:repo/milestones --jq '.[] | select(.state=="open") | "\(.number)\t\(.title)\t\(.open_issues) open"'
  ```

Pull each issue's full body. You need it to write subagent prompts and to judge whether the
issue is ready to build.

## Step 2 -- Classify each issue into a lane

| Labels | Lane | Path |
|---|---|---|
| `enhancement` + `ready` | **Feature** | speckit: specify → plan → tasks → implement |
| `enhancement`, no `ready` | **Parked** | Not refined. Recommend `/product-owner <n>` and skip. |
| `bug` | **Direct** | Single subagent: reproduce → fix → test → PR |
| `maintenance`, `documentation`, `dependencies`, `github_actions` | **Direct** | Single subagent: change → test → PR |
| No label, or ambiguous | **Parked** | Ask rather than guess a lane. |

Judgement overrides labels in one direction only: an issue labelled `maintenance` that
actually changes user-visible behaviour in `choom.core` or the TUI is a **feature**, and
goes through speckit. Never the reverse -- do not downgrade a labelled `enhancement` to a
direct fix to save a lap.

## Step 3 -- Build the schedule

The constraint that matters: **the engine surface is small.** Two features touching
`choom.core` or the TUI will collide, and reconciling two half-built specs costs more than
running them one after the other.

- **Feature lane is strictly serial.** One feature in flight at a time, start to merge.
  Order them by dependency first (a feature that changes a shared model goes before one that
  consumes it), then smallest-first so early merges de-risk the rest.
- **Direct lane runs in parallel**, up to **three** concurrent jobs. Before scheduling two
  together, compare their likely file scope from the issue bodies; if they plausibly touch
  the same module, serialize them.
- **A direct job may run alongside the in-flight feature** when their scopes are disjoint --
  a `.github/workflows/` change or a docs edit alongside a TUI feature is the normal case.
  Anything touching `src/choom/` while a feature is open gets serialized behind it.
- Every job branches from current `origin/main`. After each merge, later jobs rebase onto
  the new `main` before their PR goes green.

## Step 4 -- Present the run plan, then go

Show the user a compact table: issue, title, lane, model, wave, and the reason for each
serialization. List anything parked at Step 2 and why.

Ask for a single go-ahead. **This is the only approval gate.** After it, run to completion
without checking back except to report a parked job or a constitution escalation.

## Step 5 -- Model and agent routing

| Work | Agent | Model | Isolation |
|---|---|---|---|
| `/speckit-specify`, `/speckit-plan`, `/speckit-tasks` | one `general-purpose` agent per feature, continued via `SendMessage` | **opus** | `worktree` |
| `/speckit-implement` | fresh `general-purpose` agent | **sonnet** | enters the feature's existing worktree |
| Bugfix / maintenance / docs / CI | one `general-purpose` agent per issue | **sonnet** | `worktree` |
| Follow-up fixes on an open PR | reuse that job's agent via `SendMessage` | same as the job | same worktree |

Run every agent with `run_in_background: true` and react to completion notifications. That is
what lets the serial feature lane and the parallel direct lane advance at the same time.

Require this closing block in **every** subagent's final report, verbatim, so you can hand
the worktree to the next stage:

```
WORKTREE: <output of git rev-parse --show-toplevel>
BRANCH:   <output of git branch --show-current>
PR:       <url, or "none">
TESTS:    <pass/fail + the command run>
BLOCKED:  <"none", or the constitution principle number and what conflicts>
```

## Step 6 -- The feature lane, per issue

Spawn **one Opus agent** for the whole spec/plan/tasks arc and continue it with
`SendMessage` between stages. Same agent, same context, three of your reviews in between.

1. **Specify.** Prompt the agent to read the constitution, then run `/speckit-specify` for
   issue #N using the issue body as the feature description, isolating in a worktree per the
   repo's worktree convention. Have it open a **draft** PR with the spec, linked to the issue
   **in the same `gh pr create` call**. A spec-only PR references without closing --
   `Relates to #N`, never `Closes #N`, since merging it is not meant to close the issue
   (CLAUDE.md).
   → **You review `spec.md`** before continuing (Step 7).
2. **Plan.** `SendMessage` the same agent: run `/speckit-plan`. → **You review `plan.md`**,
   with particular attention to the Constitution Check gate -- an empty or hand-waved
   justification in Complexity Tracking is a failed gate, not a nit.
3. **Tasks.** `SendMessage`: run `/speckit-tasks`. → **You review `tasks.md`**. Delete or
   flag any "document it in README" task per CLAUDE.md, and say so in your review note.
4. **Implement.** Spawn a **fresh Sonnet agent**. Its first action is `EnterWorktree` with
   `path:` set to the `WORKTREE` the Opus agent reported, so it lands on the same branch.
   Prompt it to run `/speckit-implement`, run `scripts/dev-tests.sh`, push to the existing
   PR, and mark it ready for review. Because the PR is being expanded in place from
   spec-only to full implementation, it must **upgrade `Relates to #N` to `Closes #N`** and
   retitle from `spec:` to `feat:` at that point (CLAUDE.md).
   → **You verify** (Step 8), then **merge** (Step 9).

The spec/plan/tasks PR is never merged on its own. It becomes the feature PR when the
implement agent pushes code onto the same branch.

## Step 7 -- Review gates

At each gate, read the artifact yourself. You are not rubber-stamping a summary.

- **spec.md** -- Does it solve the problem the issue actually describes, at the issue's
  scope? Are the requirements testable? Does anything contradict a constitution principle,
  especially II (CLI and TUI are peers -- a TUI-only feature needs a CLI answer or an
  explicit interactivity carve-out), III (simplicity), IV (never lose the user's words),
  and V (the interface is specified, not improvised)?
- **plan.md** -- Constitution Check passes with real justifications. Does the design keep
  logic in `choom.core` and leave the front-ends thin (Principle I)? Any new dependency,
  network call, or admin-rights requirement is a hard stop against Platform Constraints.
- **tasks.md** -- Tasks are ordered, testable, and actually cover the spec. Behaviour changes
  carry their tests in the same task (Development Workflow gate). No README task.

If a gate fails on something ordinary -- a missing requirement, a task in the wrong order,
a thin test plan -- `SendMessage` the agent with specific, cited corrections and re-review.
Two rounds is normal; if a third is needed on the same point, park the job and say why.

If a gate fails on the constitution, park it and escalate. That is the line.

## Step 8 -- Verification before any merge

1. **Tests.** In the job's worktree: `scripts/dev-tests.sh`. Never a hand-rolled `pytest`.
2. **CI.** `gh pr checks <n>` until every check is green. A red check gets fixed by the job's
   agent via `SendMessage`, not left for the user (CLAUDE.md).
3. **Diff read.** Read the actual diff (`gh pr diff <n>`). You are looking for scope creep
   beyond the issue, logic that leaked out of `core` into a front-end, an unrelated README
   feature bullet, and a session URL in the PR body.
4. **Smoke test in tmux** -- required for anything touching the TUI, and for every bugfix
   where the report was about interactive behaviour.

   Use a throwaway workspace, never the user's. `/demo` builds a populated one under `/tmp`;
   `choom init` in a fresh temp dir is fine for simple cases. Put scratch files in
   `$CLAUDE_JOB_DIR/tmp`.

   Two details that will waste a lap if you get them wrong. **The workspace is discovered by
   walking up from the process's cwd** (`core.workspace.find_workspace`) -- there is no env
   var -- so tmux must start *in the throwaway workspace*, not in the worktree. And **launch
   the worktree's venv binary directly** rather than `uv run`: from the workspace directory
   `uv` would resolve the wrong project, and in a cold worktree it prints build output that
   a naive readiness poll mistakes for the TUI.

   ```bash
   W=<worktree path>; WS=$CLAUDE_JOB_DIR/tmp/ws-<job>
   (cd "$W" && uv sync --extra dev)              # warm the venv before tmux, not during
   mkdir -p "$WS" && (cd "$WS" && "$W/.venv/bin/choom" init)

   tmux kill-session -t fixer 2>/dev/null
   tmux new-session -d -s fixer -x 120 -y 40 -c "$WS" "$W/.venv/bin/choom"

   # Wait for first paint. A bare foreground `sleep` is blocked, so poll in a loop.
   ready=0
   for i in $(seq 40); do
     tmux capture-pane -p -t fixer | grep -qi "choom" && { ready=1; break; }
     sleep 0.25
   done
   [ "$ready" = 1 ] || echo "TUI NEVER PAINTED -- treat as a failed smoke test"

   tmux send-keys -t fixer <keys>
   for i in $(seq 8); do sleep 0.15; done          # let the redraw settle
   tmux capture-pane -p -t fixer
   tmux kill-session -t fixer
   ```

   Poll for a marker you have confirmed is in the real output, case-insensitively (the header
   renders `Choom`, not `choom`), and **treat an exhausted poll as a failed smoke test** --
   do not carry on and capture whatever happens to be on screen. Drive the path the issue
   describes and confirm the fix with your own eyes. Re-run at `-x 80 -y 24` when the change
   affects layout -- narrow-terminal regressions are a recurring failure mode in this repo.
   Always `kill-session` when done, including on the failure path.

   Exercise the equivalent CLI path too (Principle II) -- if a behaviour landed in the TUI
   only, that is a review finding.

## Step 9 -- Merge policy

Merge when **all** of these hold. No exceptions, no "it's only a docs change".

- Every CI check is green.
- `scripts/dev-tests.sh` passed in the worktree.
- You have read the diff.
- The tmux smoke test passed, where Step 8 required one.
- The PR body links its issue with a **closing** keyword (`Closes #N`) -- a PR still reading
  `Relates to #N` is one that was never upgraded from spec-only, so it is not ready to merge
  -- and carries no session URL.
- The PR contains implementation, not just spec/plan/tasks artifacts.

Then merge with a merge commit, matching this repo's history:

```
gh pr merge <n> --merge --delete-branch
```

Confirm the issue closed. Move to the next wave, and rebase in-flight jobs onto the new
`main`.

You may merge feature PRs, bugfix PRs, and maintenance PRs on these terms. You may not
merge anything you parked or escalated.

## Step 10 -- Parking and escalation

Park a job when: a constitution conflict surfaces, a subagent reports `BLOCKED`, a review
gate fails three times on the same point, CI fails for a reason outside the job's scope, or
the issue turns out to need refinement it never got.

Parking means: leave the branch and PR in place as a draft, comment on the PR with exactly
what is unresolved, note it in the ledger, and move on to the next job. Do not delete work
and do not force the merge.

Escalate immediately in your chat output -- do not wait for the end of the run -- when the
block is a constitution conflict. State the principle by number, the artifact, and the
conflict in two or three sentences.

## Step 11 -- Ledger and final report

Keep a running ledger at `$CLAUDE_JOB_DIR/tmp/fixer-ledger.md`: one row per issue with lane,
agent, worktree, branch, PR, stage, and outcome. Update it as each stage lands so a resumed
session can pick the run back up.

Report progress in chat as waves complete -- what merged, what is in flight, what is parked.
At the end, give the user:

- **Merged**: issue, PR, one line on what landed.
- **Open**: PR and what it is waiting on.
- **Parked**: issue, the reason, and the specific next action (usually `/product-owner <n>`
  or a constitution decision only they can make).
- Whether the milestone is now empty and ready for `/release`.
