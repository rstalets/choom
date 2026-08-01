# CLAUDE.md

Repo-specific instructions for Claude Code sessions working on endpaper.

## Pull requests

- **Check CI before considering a PR done.** After opening a PR or pushing updates to one,
  check that its checks are green (e.g. `gh pr checks <n>`) rather than assuming the push
  succeeded. If a check fails, troubleshoot and fix it immediately — don't leave a red PR for
  the user to notice later.
- **Never insert a Claude session URL (or similar self-referential link) into a PR title or
  description.** This is a public repository. Omit any `Claude-Session:` line and
  `claude.ai/code/...` link that a default PR template might otherwise include.
