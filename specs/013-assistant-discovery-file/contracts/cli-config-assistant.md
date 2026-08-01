# Contract: `choom config assistant`

**Feature**: 013-assistant-discovery-file

The AI-facing surface of the command that installs the discovery file. Existing behaviour is
restated only where this feature touches it; everything not named here is unchanged.

---

## Read — `choom config assistant [--json]`

Writes, moves, and removes **nothing** (FR-012). Exit code `0`.

### Human form (stdout, tab-separated, unchanged shape)

```
configured	claude
resolved	claude
source	configured
available	claude,copilot
discovery	/Users/x/.claude/skills/choom/SKILL.md
offered	yes
```

Two rows are added. `discovery` reads `-` when no file is installed; `offered` is `yes` / `no`.

### `--json`

```json
{
  "configured": "claude",
  "resolved": "claude",
  "source": "configured",
  "available": ["claude", "copilot"],
  "discovery_file": "/Users/x/.claude/skills/choom/SKILL.md",
  "launch_offer_made": true
}
```

| Key | Type | Meaning |
|---|---|---|
| `configured`, `resolved`, `source`, `available` | unchanged | existing keys — **not** renamed, removed, or retyped |
| `discovery_file` | `string \| null` | absolute path of the installed file, `null` when none is installed |
| `launch_offer_made` | `boolean` | whether the launch question has been asked and answered in this workspace |

Additive only, which Principle II makes a minor change. A consumer reading only the four existing
keys is unaffected.

## Set — `choom config assistant <claude|copilot|none>`

| Aspect | Contract |
|---|---|
| stdout | **empty**, always. Following 011's delete precedent for mutations, so piping a set is safe. |
| stderr | one line naming the outcome: the path written, the path removed, that no discovery file exists for this assistant (FR-017), or the failure and its reason (FR-014). |
| exit code | reports the **setting** write only (FR-013): `0` on success, `2` for a rejected value, `3` for a config that cannot be read or written. A discovery-file failure never changes it. |
| side effects | installs the file for the named assistant, removes choom-owned files for the others (marker-guarded), clears `launch_offer_made`. `none` removes every choom-owned file and records the setting. |
| interactivity | none. No prompt, no confirmation, no pager, no editor — on any path, including failure. |

### Failure matrix

| Situation | Setting | Discovery file | stderr | Exit |
|---|---|---|---|---|
| Normal set | written | installed | path written | 0 |
| Profile directory unwritable | written | not installed | path + reason | 0 |
| Assistant has no user-scope location | written | none | "no discovery file for `<name>`" | 0 |
| A non-choom file occupies our path | written | installed (ours is rewritten) | — | 0 |
| Removing another assistant's file, marker absent | written | left alone | warning naming the path | 0 |
| Rejected value | unchanged | untouched | usage error | 2 |
| Config unreadable/unwritable | not written | untouched | workspace error | 3 |

## `choom init --assistant <value>`

Records the setting as today, and additionally installs the discovery file for the new workspace
(FR-020). `init` with no `--assistant` installs nothing. `--assistant none` installs nothing and
removes any choom-owned file. A discovery-file failure does not fail `init`.

## Invariants a contract test should hold

1. A read writes nothing anywhere — profile directory and workspace both byte-identical afterwards.
2. Set never writes to stdout.
3. The four pre-existing `--json` keys keep their names and types.
4. Exit codes are unchanged from today for every pre-existing situation.
5. No path in this command blocks on stdin or emits an escape sequence to a non-TTY stdout.
6. At most one choom-owned discovery file exists after any successful set.
