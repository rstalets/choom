# Contract: CLI surface (viewing and editing)

**Baseline**: [feature 002's CLI contract](../../002-general-notes/contracts/cli.md).

## This feature adds no command

No new verb, no new flag, no new `--json` schema, no exit-code change. Interactive text entry is
inherently interactive and has no command-line form (FR-036), and this feature must not become a
prerequisite for the `read` / `write` / `append` commands of REQUIREMENTS.md §4.2, which remain
unclaimed work (FR-037).

The single change is to what `endpaper init` **prints**.

---

## `endpaper init` — changed output

| Aspect | Before | After |
|---|---|---|
| Files created | `meetings/`, `notes/daily/`, `tasks.md`, `AGENTS.md`, `.endpaper/config.toml` | same, **plus `CLAUDE.md`** |
| Existing `AGENTS.md` | silently overwritten | **left byte-identical**, reported |
| Existing `CLAUDE.md` | n/a | **left byte-identical**, reported |
| Exit code, all cases above | 0 | **0** — unchanged (FR-051) |
| Existing workspace (`.endpaper` present) | exit 3, `WorkspaceError` | unchanged |

### Stream discipline

Unchanged and load-bearing: the created workspace path goes to **stdout**; every notice about a
skipped guidance file goes to **stderr** (FR-051, Principle II). A caller piping stdout gets the path
and nothing else, whether or not a file was skipped.

```
$ endpaper init
/home/u/vault                                    # stdout

$ endpaper init                                  # in a repo that already has CLAUDE.md
/home/u/vault                                    # stdout
note: CLAUDE.md already exists and was left unchanged.
      Add a line telling your assistant to read AGENTS.md.   # stderr
$ echo $?
0
```

### Contract tests

Extends the existing `tests/contract/` suite; all of these already have a home there.

| Assertion | Requirement |
|---|---|
| `CLAUDE.md` exists after init in an empty directory | FR-045 |
| A pre-existing `CLAUDE.md` is byte-identical after init | FR-049, SC-012 |
| A pre-existing `AGENTS.md` is byte-identical after init | FR-050, SC-012 |
| Exit code is 0 when a guidance file was skipped | FR-051 |
| The skip notice is on stderr, never stdout | FR-051 |
| stdout contains no ANSI when piped | unchanged, existing test |
| `CLAUDE.md` ≤ 12 lines, names `AGENTS.md`, duplicates no convention | FR-046–048, SC-013 |
