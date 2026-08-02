# Quickstart: Assistant Discovery File

**Feature**: 013-assistant-discovery-file

How to prove the feature works end to end. Each scenario maps to a user story and states what to
run and what to expect. Details of the file's shape live in
[contracts/discovery-file.md](./contracts/discovery-file.md); the command's surface is in
[contracts/cli-config-assistant.md](./contracts/cli-config-assistant.md).

---

## Prerequisites

- choom installed from this branch (`uv tool install --force .` or `uv run choom`).
- At least one supported assistant on `PATH` (`claude` or `copilot`) for the launch-offer scenarios.
- A scratch workspace, so nothing here touches real notes.

> **Warning**: these scenarios write into your real `~/.claude` or `~/.copilot`. Back up an existing
> `~/.claude/skills/choom/SKILL.md` before starting, or run them in a container. The test suite does
> not have this problem — it redirects the profile root to `tmp_path` (R13).

```bash
mkdir -p /tmp/choom-qs && cd /tmp/choom-qs
choom init
```

## Scenario 1 — the pointer (US1)

```bash
choom config assistant claude
cat ~/.claude/skills/choom/SKILL.md
```

**Expect**: one line on stderr naming the path written; nothing on stdout. The file names
`/tmp/choom-qs`, points at its `AGENTS.md`, carries the generated-by marker, and is at most 20
lines. It restates nothing from `AGENTS.md`.

Then the real test — start the assistant somewhere else entirely and ask it something that needs the
workspace:

```bash
cd ~ && claude -p "Where are my choom notes, and what file explains how to write to them?"
```

**Expect**: it names `/tmp/choom-qs` and its `AGENTS.md` without being told either.

## Scenario 2 — the launch offer (US2)

```bash
mkdir -p /tmp/choom-qs2 && cd /tmp/choom-qs2 && choom init
rm -f ~/.claude/skills/choom/SKILL.md
choom            # opens the TUI
```

**Expect**: the list is up and painted, with the shared confirmation bar centred over it — the same
slim two-option bar as delete, naming the assistant and this workspace.

- Press `Enter` → the file is installed for `/tmp/choom-qs2`, the status bar reports it, and
  `.choom/config.toml` gains `name = "claude"` and `launch_offer_made = true`.
- Or press `Esc` → nothing is installed, nothing appears in `~/.claude`, and the config still gains
  `launch_offer_made = true`.

Either way, quit and relaunch:

```bash
choom
```

**Expect**: no question. Verify without opening the TUI:

```bash
choom config assistant --json
```

**Expect**: `launch_offer_made` is `true`, and `discovery_file` is the path or `null` depending on
which key you pressed.

**Not offered** — check each suppression in turn: with the file already installed; with
`assistant = "none"`; with two assistants installed and none configured; with no assistant
installed. None of these shows the question.

## Scenario 3 — repointing and removal (US3)

```bash
cd /tmp/choom-qs && choom config assistant claude     # points at qs
cd /tmp/choom-qs2 && choom config assistant claude    # repoints at qs2
grep -c choom-qs /tmp/choom-qs2/../../root/.claude/skills/choom/SKILL.md 2>/dev/null || \
  grep choom-qs ~/.claude/skills/choom/SKILL.md
```

**Expect**: the file names `/tmp/choom-qs2` and mentions `/tmp/choom-qs` nowhere.

```bash
choom config assistant copilot
ls ~/.claude/skills/choom/SKILL.md ~/.copilot/skills/choom/SKILL.md
```

**Expect**: exactly one exists — the Copilot one. The Claude file was removed because it carried
choom's marker.

```bash
choom config assistant none
```

**Expect**: no choom-owned file remains in either location; running it a second time still exits 0.

## Scenario 4 — reporting and failure (US4)

```bash
choom config assistant claude 1>/dev/null    # stdout must be empty
chmod -w ~/.claude/skills/choom               # simulate a locked-down profile
choom config assistant claude; echo "exit=$?"
```

**Expect**: stdout empty in the first command. In the second, the setting is still recorded, stderr
names the path and the reason, and `exit=0` — the discovery file never decides the exit code.

```bash
chmod +w ~/.claude/skills/choom               # restore
```

## Scenario 5 — install at init (US5)

```bash
mkdir -p /tmp/choom-qs3 && cd /tmp/choom-qs3
choom init --assistant claude
cat ~/.claude/skills/choom/SKILL.md
```

**Expect**: the workspace is created and the file already points at `/tmp/choom-qs3` — no second
command. `choom init` with no `--assistant` in a fourth directory installs nothing.

## Cleanup

```bash
rm -rf /tmp/choom-qs /tmp/choom-qs2 /tmp/choom-qs3
rm -f ~/.claude/skills/choom/SKILL.md ~/.copilot/skills/choom/SKILL.md
```

Restore any file you backed up in Prerequisites.

## Automated equivalents

```bash
uv run pytest tests/unit/test_discovery_paths.py tests/unit/test_discovery_content.py \
              tests/unit/test_discovery_install.py tests/contract/test_config_assistant_cli.py \
              tests/integration/test_launch_offer.py
uv run pytest                    # whole suite, including the AGENTS.md line-budget contract
```
