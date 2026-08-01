---
name: "product-owner"
description: "Refine enhancement issues -- one issue or a whole milestone -- into a complete problem statement and a viable, appropriately-scoped solution, per the feature-request template."
argument-hint: "<issue-number> | <issue-url> | milestone:<name-or-number> (omit to be asked)"
metadata:
  author: "endpaper"
user-invocable: true
disable-model-invocation: false
---

## Purpose

Act as a product owner doing a **light** refinement pass on `enhancement`-labeled issues, in
between someone filing a rough idea and the spec phase (`/speckit-specify`) turning it into a
detailed spec. The job is narrow: make sure each issue names a real problem and a viable
solution, in the shape the repo's template expects. Nothing more.

**Do not over-refine.** No acceptance criteria, no file/module lists, no test plans, no task
breakdowns, no multi-paragraph design docs. That is `/speckit-specify` and `/speckit-plan`'s job,
and duplicating it here just gives the spec phase stale detail to reconcile. If you notice
yourself writing more than a few sentences per section, stop and trim.

## User Input

```text
$ARGUMENTS
```

## Step 1 — Resolve the target set

- A bare number or an issue URL: treat as **one issue**. Confirm with `gh issue view <n> --json number,title,body,labels,milestone,url` -- if that fails, fall back to treating the input as a milestone number (see below).
- `milestone:<name-or-number>`, or anything non-numeric: treat as a **milestone**. List its open, `enhancement`-labeled issues:
  ```
  gh issue list --milestone "<name-or-number>" --label enhancement --state open --json number,title,body,url
  ```
- No argument: ask (a) which single issue, or (b) which open milestone (list them with `gh api repos/{owner}/{repo}/milestones --jq '.[] | select(.state=="open") | "\(.number)\t\(.title)"'` and let the user pick).

If the milestone/issue has zero open enhancement issues, say so and stop -- nothing to refine.

## Step 2 — Per issue: check template shape

The template is `.github/ISSUE_TEMPLATE/enhancement.yml`. A properly-filed issue has these
headers (exact wording may vary slightly if hand-edited, match by intent):

- **What problem does this solve?** (required)
- **Proposed solution** (required)
- **Alternatives you've considered** (optional)
- **Additional context** (optional)

If the body is free-form (no headers, or filed before the template existed), reformat it into
these sections **without inventing content** -- slot existing prose under the right header, and
leave a section blank (not fabricated) if the original genuinely doesn't cover it.

## Step 3 — Evaluate and fill gaps

For each issue, judge two things:

1. **Problem statement is complete.** It names a concrete pain point or limitation -- who hits
   it and what goes wrong today -- not just a feature name ("add dark mode" is not a problem;
   "the TUI is unreadable on a light terminal, and there's no way to change that" is). If it's a
   restated feature name with no problem underneath, and the problem is inferable from context
   (related issues, README, docs/REQUIREMENTS.md), draft one sentence stating it. If it truly isn't
   inferable, don't guess -- flag it as an open question instead (Step 5).

2. **Proposed solution is complete and viable.** It describes what would change, roughly how,
   and for whom -- a rough sketch, per the template's own wording, not a spec. It should fit this
   project's conventions (CLI and TUI parity, plain markdown files, no database, `AGENTS.md`
   as the assistant-facing surface) rather than propose something structurally at odds with them.
   If missing or too vague to act on, draft one grounded in the problem statement -- again, a
   sketch, not a design doc.

**When refining a milestone as a set:** after handling each issue individually, do one pass
across the set looking for overlap. If two issues describe the same underlying problem, note
it in your summary to the user and suggest (don't silently perform) a merge. If two issues are
genuinely related but distinct, add a one-line `Related: #<n>` cross-reference in each --
nothing heavier.

## Step 4 — Trim, don't just add

If an issue is already over-refined (a previous pass, or the filer, dumped a full spec into it --
acceptance criteria, file lists, code snippets), that content doesn't belong on the issue. Pull
out the problem and solution into the template's shape and note in your summary that you
compressed it, so the person reading history isn't surprised the issue got shorter.

## Step 5 — Confirm before writing

`gh issue edit` and `gh issue comment` are visible to everyone watching the repo. Before calling
either:

- Show the user, per issue: the current body/labels vs. the proposed body, and whether you'd
  add the `ready` label (see below).
- Wait for confirmation, unless the user's invocation explicitly said to apply without asking
  (e.g. `/product-owner 42 --apply`) -- in which case, still summarize what you did afterward.

On confirmation:

- `gh issue edit <n> --body "<refined body>"`.
- If the issue now states a complete problem and a viable solution, add the **`ready`** label
  (`This issue is fully defined and ready for spec creation.`) via `gh issue edit <n> --add-label ready` -- this is the signal that the refinement pass is done and the issue can move to `/speckit-specify`.
- If a problem or solution genuinely can't be completed without the filer's input (Step 3's
  "don't guess" case), do **not** add `ready`. Instead leave a `gh issue comment` asking the
  specific question that's blocking refinement, so the next pass (or the filer) has something
  concrete to answer.

## Output

End with a short summary: issues touched, which got the `ready` label, which got a clarifying
comment instead and why, and any `Related:` cross-links added.
