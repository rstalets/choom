---
name: "release"
description: "Draft release notes for a version's milestone, then use them (plus any supplied screenshots) to open a PR that folds the shipped user-visible changes into README.md."
argument-hint: "<version, e.g. v0.0.4 or 0.0.4>"
metadata:
  author: "choom"
user-invocable: true
disable-model-invocation: false
---

## Purpose

Two steps, run together, for cutting a release:

1. Draft release notes for the milestone matching the given version -- everything that closed
   under it, written as prose (not a bare list of titles), grouped by theme.
2. Use that draft, plus any screenshots the user supplies, to update `README.md`'s user-facing
   feature summary, and open a PR with the result.

This is the "ship" end of the pipeline that starts at `/product-owner` (refine the issue) and
`/speckit-specify`/`/speckit-plan`/`/speckit-implement` (build it) -- once a milestone's work has
landed, this turns it into the documentation update that tells users what changed.

## User Input

```text
$ARGUMENTS
```

If empty, ask for the version.

## Step 1 — Resolve the milestone

This repo's milestones are titled like `v0.0.3`. Normalize the argument (accept `0.0.3` or
`v0.0.3`) and match it against:

```
gh api repos/{owner}/{repo}/milestones --jq '.[] | select(.title=="<v0.x.y>" or .title=="<x.y>")'
```

If nothing matches, list open and closed milestones and ask which one was meant.

If the milestone still has open issues, say so and ask whether to proceed anyway -- drafting a
release from an incomplete milestone is usually premature, but the user may know something the
tracker doesn't (e.g. a deferred issue that isn't part of this release).

## Step 2 — Draft the release notes

Same job as before, now folded into this skill:

**Closed issues:**
```
gh issue list --milestone "<title>" --state closed --json number,title,labels,closedAt,url,body
```

**Merged PRs** (`gh pr list` has no `--milestone` flag, but supports search syntax):
```
gh pr list --search 'milestone:"<title>" is:merged' --json number,title,body,mergedAt,author,url,closingIssuesReferences
```

Use `closingIssuesReferences` to associate each PR back to the issue(s) it closed, so a feature
that landed across a spec PR plus one or more implementation/fix PRs becomes **one** entry, not
several.

For each distinct change, read the actual PR/issue body and comments -- not just the title --
and write a couple of sentences of real documentation: what it does, what changed for a user, any
new CLI surface, config, or key bindings. Label each entry **user-visible** or **internal**
(refactors, tests, CI, dependency bumps), mirroring `CHANGELOG.md`'s existing
`**TUI, user-visible**` convention, and group related entries under a theme heading rather than
one heading per issue/PR number.

Write the draft to `release-notes-<version>.md` in the current directory. This file is scratch
for Step 3 to work from -- ask the user whether they want it committed into the PR for historical
reference, or left as a local, uncommitted artifact; don't assume either way.

## Step 3 — Fold the user-visible changes into README.md

Read `README.md`'s `## Features (vX.Y.Z)` section and the caveat sentence beneath it ("Not
everything above has landed on `main` yet...").

- Bump the heading to the new version.
- For each **user-visible** entry from Step 2, add a new bullet or update an existing one, in the
  section's existing style: **Bold feature name** — a sentence or two, matching the tone and
  length of its neighbors. Internal/maintenance entries don't belong here -- this section is
  user-facing, not a changelog.
- If, as of this milestone, everything the section describes has actually landed on `main`,
  consider softening or removing the "hasn't all landed yet" caveat -- but check
  `CHANGELOG.md`/`docs/REQUIREMENTS.md` before removing it; don't drop it on the strength of this
  milestone's changes alone if older gaps remain.
- Touch `## Roadmap` or `## Status` only if a Step 2 entry clearly moved something across them
  (a roadmap item shipped, something newly out-of-scope) -- and then only minimally.
- Leave `CHANGELOG.md` alone. It already accrues entries as work lands; this skill's job is
  README's release-facing summary, not the changelog itself.

## Step 4 — Incorporate any supplied screenshots (optional)

The user may attach one or more screenshots to this run, to replace a stale one, add one for a
feature that doesn't have one yet, or refresh one after a UI change. README's existing images
live at `docs/screenshots/<kebab-name>.png`, each referenced by exactly one
`![alt text](docs/screenshots/<name>.png)` line placed right after the prose paragraph describing
that feature (see the `meetings`/`edit-meeting`/`execute-task`/`research-note` screenshots
already there for the pattern).

For each supplied image, figure out which of these it is -- from the user's message if they said,
otherwise by comparing it against what's already in `docs/screenshots/` and what changed this
release -- and **ask if it's genuinely ambiguous** rather than guessing at intent:

- **Replace**: overwrite the file at its existing path. Leave the README reference line alone
  unless the alt text no longer matches what the new image shows.
- **Add**: save it as a new file following the existing kebab-case naming convention, and add a
  `![...](docs/screenshots/<name>.png)` line after the paragraph for the feature it depicts --
  matching where this release notes draft says that feature is documented in README.
- **Refresh** (same feature, re-taken after a visual change): overwrite in place, same as
  replace.

Write alt text that describes what the image shows, not a restatement of surrounding prose.
Flag, rather than silently committing, any supplied image that looks unusually large uncompressed
-- README's existing screenshots are small PNGs, and a multi-MB file bloats the repo.

Screenshots go into the same commit as the `README.md` text changes, so the PR's diff reviews as
one coherent unit.

## Step 5 — Branch, commit, and open the PR

- Create a branch, e.g. `docs/release-<version>-readme`.
- Commit the `README.md` changes, any `docs/screenshots/` additions or replacements from Step 4,
  and `release-notes-<version>.md` if Step 2 said to keep it.
- Show the user the `README.md` diff (and name which screenshots were added/replaced) and ask for
  confirmation before pushing -- this opens a PR visible to everyone watching the repo, and
  README wording/images are exactly the kind of thing worth a human glance before they go out.
- On confirmation: push, then `gh pr create --draft`, following this repo's `CLAUDE.md` --
  no Claude session URL anywhere in the title or description.
- After opening (and after any later push to it), check `gh pr checks` and troubleshoot
  immediately if anything is red, per `CLAUDE.md` -- don't hand back a PR without confirming its
  checks are green.

## Output

End with: the milestone resolved, the path to the release-notes draft, which screenshots were
added/replaced (if any), the PR URL, and its CI status at the time of opening.
