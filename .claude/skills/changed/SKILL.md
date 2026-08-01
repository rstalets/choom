---
name: "changed"
description: "Walk every closed issue and merged PR in a milestone and produce a markdown draft of release notes for it."
argument-hint: "<milestone-name-or-number>"
metadata:
  author: "endpaper"
user-invocable: true
disable-model-invocation: false
---

## Purpose

Given a milestone, gather everything that closed under it and write a markdown document a human
can use to document that release -- in the same narrative spirit as this repo's `CHANGELOG.md`
(grouped by theme, user-visible vs. internal called out explicitly, prose that says what changed
and why it matters -- not a bare list of titles).

This skill only **produces a draft file**. It does not edit `CHANGELOG.md` directly -- folding a
draft into `[Unreleased]` or a new version section is a judgment call for the user to make.

## User Input

```text
$ARGUMENTS
```

If empty, list open and recently-closed milestones (`gh api repos/{owner}/{repo}/milestones --jq '.[] | "\(.number)\t\(.title)\t\(.state)"'` plus `--state closed` for recently-closed ones) and ask which one.

## Step 1 — Resolve the milestone

```
gh api repos/{owner}/{repo}/milestones --jq '.[] | select(.title=="<arg>" or (.number|tostring)=="<arg>")'
```

Note its title, number, description, and due/closed date -- useful for the doc's header.

## Step 2 — Gather closed issues

```
gh issue list --milestone "<title-or-number>" --state closed --json number,title,labels,closedAt,url,body
```

## Step 3 — Gather merged PRs

`gh pr list` has no `--milestone` flag, but supports search syntax:

```
gh pr list --search 'milestone:"<title>" is:merged' --json number,title,body,mergedAt,author,url,closingIssuesReferences
```

Use `closingIssuesReferences` to associate each PR back to the issue(s) it closed -- that
association is what lets you write one entry per user-facing change instead of one per PR
(a feature often lands across a spec PR and one or more implementation/fix PRs; merge those into
a single entry).

## Step 4 — Write entries, not titles

For each distinct change (issue + its closing PR(s), or a standalone PR with no linked issue):

- Read the PR body and issue body/comments for the actual substance -- what the feature does,
  what changed for a user, any new CLI surface, config, or key bindings. Titles alone
  ("feat(007): task content editing") are commit-message shorthand, not documentation; expand
  them into what a user or the next assistant working in the repo actually needs to know.
- Label each entry **user-visible** (changes behavior someone using the TUI/CLI would notice) or
  **internal** (refactors, test coverage, CI, dependency bumps, maintenance) -- mirror
  `CHANGELOG.md`'s `**TUI, user-visible**` convention.
- Group related entries under a theme heading (a feature name), the way existing `CHANGELOG.md`
  sections do, rather than one heading per issue/PR number.
- Keep issue/PR numbers as trailing references (e.g. `(#42, #45)`) for traceability, but the
  numbers are not the content -- the prose is.
- Skip noise: dependabot bumps and pure CI tweaks can be a single collapsed bullet list at the
  end rather than full entries, unless one of them was actually a user-facing fix.

## Step 5 — Assemble the document

Structure:

```markdown
# <milestone title> -- release notes (draft)

<one-paragraph summary of the release, if a theme is obvious across the changes>

## <theme heading>

**TUI/CLI, user-visible** (or **Internal**)

<prose describing the change>

(#issue, #pr)

## <next theme heading>

...

## Maintenance

- <collapsed bullets for dependency bumps, CI-only changes, etc.>
```

Write it to `release-notes-<milestone-slug>.md` in the current directory (slugify the milestone
title: lowercase, spaces to hyphens). Tell the user where it landed and that folding it into
`CHANGELOG.md` is left to them.

## Output

End with: milestone resolved, counts (issues closed, PRs merged, entries written), and the path
to the generated file.
