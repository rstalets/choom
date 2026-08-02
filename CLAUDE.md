# CLAUDE.md

Repo-specific instructions for Claude Code sessions working on choom.

## Read the constitution first

Before doing any work in this repo — not just spec-driven work via speckit — read
`.specify/memory/constitution.md`. It defines choom's non-negotiable principles (core vs.
interface boundaries, the CLI's AI-facing contract, the plain-markdown-only rule, data-loss
avoidance, and more) and is the authority whenever a convention or a habit conflicts with
it. This applies to bugfixes, small edits, and any other task, not only work that goes
through a `speckit-*` skill.

## Testing

- **Run tests via `scripts/dev-tests.sh`**, not a hand-rolled `pytest` invocation — it
  runs the suite in parallel (`-n auto`) and is the standard entry point for agents and
  humans alike. Pass pytest args/flags straight through, e.g.
  `scripts/dev-tests.sh tests/unit/test_foo.py -k something`.

## README documents what has shipped, not what is in flight

`README.md`'s feature list describes the **released** version — it closes with "Everything
above has landed on `main` as of vX.Y.Z". A reader arriving from PyPI installs that version,
so a bullet describing something only on `main` is a promise the tool they just installed
does not keep.

- **Do not add or extend a README feature bullet for unreleased work**, including the
  feature you are implementing right now. This holds even when the change feels like a
  natural extension of a bullet that is already there — appending a sentence about
  in-flight behaviour to a shipped feature's bullet is the same error in a form that is
  harder to spot in review.
- **README changes belong to the release.** The `release` skill drafts notes for a
  version's milestone and folds that version's user-visible changes into `README.md` as
  part of cutting it. That is when the feature list moves, and the only time.
- **If a plan or `tasks.md` carries a "document it in README" task for unreleased work,
  skip it** and say so in the task list rather than silently completing it. Recording the
  behaviour in the feature's own `specs/<feature>/` artifacts is what that task is
  actually for at implementation time.
- Docs that describe the repository rather than the product — `CLAUDE.md`,
  `docs/REQUIREMENTS.md`, `.specify/memory/constitution.md`, the feature's own spec, plan,
  contracts, and quickstart — are exempt. They are read by people working on the code, not
  by people using the released tool, so they should be updated as the work lands.

## Pull requests

- **Check CI before considering a PR done.** After opening a PR or pushing updates to one,
  check that its checks are green (e.g. `gh pr checks <n>`) rather than assuming the push
  succeeded. If a check fails, troubleshoot and fix it immediately — don't leave a red PR for
  the user to notice later.
- **Never insert a Claude session URL (or similar self-referential link) into a PR title or
  description.** This is a public repository. Omit any `Claude-Session:` line and
  `claude.ai/code/...` link that a default PR template might otherwise include.
