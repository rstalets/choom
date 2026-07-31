# Quickstart: validating Local AI Assistant Invocation

**Feature**: `006-ai-assistant-invocation` | **Date**: 2026-07-30

How to prove this feature works, end to end, **without installing Claude Code or GitHub Copilot and
without a network**. Every scenario below runs against a stub binary.

---

## Prerequisites

```bash
uv sync --all-extras          # dev extras include pytest
uv run pytest -q              # baseline: the suite is green before you start
```

No API key. No network. No assistant installed.

---

## The stub binary

The one fixture this feature's testing rests on. A Python script written into `tmp_path`, made
executable, and named as a profile's binary, with behaviour selected by an environment variable so
the argv stays exactly what endpaper built.

```python
# tests/conftest.py (sketch -- final form belongs in the implementation)
@pytest.fixture
def stub_assistant(tmp_path, monkeypatch):
    """Install a fake `claude` on PATH. Returns a setter for its mode."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script = bindir / ("claude.cmd" if os.name == "nt" else "claude")
    script.write_text(STUB_SOURCE, encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    return lambda mode: monkeypatch.setenv("ENDPAPER_STUB_MODE", mode)
```

| Mode | Behaviour | Proves |
|---|---|---|
| `echo` | prints its own argv, exit 0 | the instructions and document path reached the command line |
| `reply` | prints fixed multi-line markdown, exit 0 | insertion, ordering, line endings |
| `empty` | prints nothing, exit 0 | empty-reply handling |
| `fail` | writes to stderr, exit 1 | failure handling |
| `sleep` | sleeps indefinitely | cancellation |

Prepending to `PATH` is what makes `shutil.which` find it, so detection and invocation are exercised
for real rather than mocked.

---

## Scenario 1 — The headline path (US1, P1)

**Setup**: workspace with a meeting note; stub in `reply` mode; no assistant configured.

1. `uv run endpaper` → Meetings → `enter` → `e` to edit.
2. On a fresh line type `/ai summarise the bullets above` and press `Enter`.

**Expect**:

- The document is saved before anything else happens (mtime changes; the file on disk contains the
  `/ai` line).
- The command line is replaced by `⋯`; the status bar reads `⋯ working — ctrl+c to cancel`.
- Typing does nothing while the request is in flight.
- The reply lands where the command was, every line in order, surrounding lines untouched.
- The buffer is dirty; `ctrl+o` saves normally.

**Covers**: FR-006, FR-008, FR-011, FR-012, FR-014 · US1 scenarios 1–2 · SC-001

---

## Scenario 2 — `/ai` that is not a command (US1, P1)

Type each of these on its own line and press `Enter`:

```text
Did you know you can type /ai in endnotes?
  /ai indented
/aim high
//ai twice
/summarise this
```

**Expect**: every one inserts a newline and stays as typed. Nothing is sent. No error appears for
`/summarise` — the editor does not warn about words it does not know.

**Covers**: FR-001, FR-002 · US1 scenarios 4, 8 · SC-004

---

## Scenario 3 — Cancel (US2, P2)

**Setup**: stub in `sleep` mode.

1. Run `/ai anything`.
2. Wait for the indicator, then press `ctrl+c`.

**Expect**:

- Control returns in under a second, every time.
- The line reads `/ai anything` again, exactly as typed, ready to edit and retry.
- The stub process is gone (no orphan).
- No error message — a cancel the user asked for is not a failure.

**Covers**: FR-013 · US2 scenarios 1–2 · SC-002

---

## Scenario 4 — Every failure leaves the words intact (US2, P2)

Run `/ai test` once per row and compare the document against its pre-command state.

| Setup | Expect |
|---|---|
| Stub `fail` | Status bar names the assistant and the stderr line; command line restored |
| Stub `empty` | "returned an empty reply"; command line restored |
| No stub on `PATH`, setting `claude` | "Claude Code CLI is not installed or not on your PATH" |
| Nothing configured, nothing installed | Error names `/config assistant` |
| Both stubs installed, nothing configured | Told to choose; named the command that does it |
| Note's directory made read-only | Save error reported, **assistant never invoked** |

**Expect in every row**: control returns, the document is byte-identical to its saved state, and no
`⋯` remains anywhere.

**Covers**: FR-007, FR-015, FR-016, FR-017, FR-023, FR-024 · US1 scenario 6 · US2 scenarios 3–6 ·
SC-003

---

## Scenario 5 — Configuration, both interfaces (US3, P3)

```bash
endpaper config assistant                 # unset: source "unset" or "detected"
endpaper config assistant claude          # exit 0, silent
endpaper config assistant --json          # {"configured":"claude","resolved":"claude",...}
endpaper config assistant gpt             # exit 2, accepted values on stderr, nothing written
cd /tmp && endpaper config assistant      # exit 3, workspace error
```

Then in the TUI: `/config assistant copilot`, and confirm the next `/ai` uses Copilot with no
restart. Restart and confirm the value persisted.

Finally, `endpaper init --assistant copilot` in an empty directory and confirm the new workspace's
`config.toml` carries `[assistant]` — **with no prompt at any point**.

**Covers**: FR-022, FR-025, FR-026, FR-027, FR-028, FR-029 · US3 scenarios 1–7 · SC-008

---

## Scenario 6 — Nothing else depends on this (boundary)

On a machine with no assistant installed and no network:

```bash
endpaper meeting new "Q3 planning"
endpaper note today
endpaper task add "buy milk"
endpaper meeting list --json
uv run endpaper                # browse, filter, edit, save
```

**Expect**: all unchanged. Then open a config written by an older build (no `[assistant]` table) and
confirm everything works and reading the setting is not an error.

**Covers**: FR-030, FR-031 · US3 scenario 9 · SC-006

---

## Scenario 7 — Discoverability (US1)

Open the help pane. `/ai` is listed with `<prompt>` and its description.

**Covers**: FR-004 · US1 scenario 7

---

## Automated coverage plan

Risk-based, one layer per risk — a behaviour is not re-verified at every layer it touches
(Principle VI).

### `tests/unit/`

| File | Covers |
|---|---|
| `test_editor_commands.py` | Grammar table from [editor-commands.md](./contracts/editor-commands.md): every plain-text case, case-insensitive match, argument stripping, bare `/ai`. Pure function, no terminal. |
| `test_assistant_resolve.py` | The six-row resolution table, including that `none` does not fall back to detection and that two available assistants report ambiguity rather than picking. |
| `test_config_write.py` | Key created in each of the three file shapes; comments and unknown keys survive; an invalid value writes nothing. |
| `test_command_parsing.py` *(modified)* | Verb table now includes `config`. |

### `tests/integration/`

| File | Covers |
|---|---|
| `test_ai_command_tui.py` | The editor round trip against the stub: success inserts and preserves surrounding lines; cancel restores the line and kills the process; failure and empty reply show a message and leave the document intact; save failure never invokes. |
| `test_config_assistant.py` | Setting via CLI and TUI produces the same file (parametrized across adapters, per the constitution's rule on parity tests rather than duplicate files). |

### `tests/contract/`

| File | Covers |
|---|---|
| `test_exit_codes.py` *(modified)* | `config assistant`: 0 success, 2 bad value, 3 no workspace. |
| `test_json_schema.py` *(modified)* | The four documented keys, exact set, no nulls where a list belongs. |
| `test_non_blocking.py` *(modified)* | `config assistant` and `init --assistant` terminate promptly with stdin closed. |

**Not covered by an automated test, by choice**: the visual appearance of the indicator and the
terminal-by-terminal behaviour of `ctrl+c`. Both are verified manually on the target terminals
before release, as the constitution's TUI rule requires.

---

## Manual verification before release

Constitution: *TUI changes MUST be verified on the target terminals before release.*

| Terminal | Check |
|---|---|
| Windows Terminal | `ctrl+c` cancels rather than killing the app; `claude.cmd` resolves |
| iTerm2 | indicator and cancel hint legible; resize mid-request |
| macOS Terminal | as above |
| PuTTY | `ctrl+c` reaches the app |
| tmux | `ctrl+c` is not swallowed by the prefix |

`ctrl+c` is the item to watch: it is bound against the constitution's reservation, justified in the
plan's Complexity Tracking on the grounds that it is scoped to the in-flight state. If a terminal
swallows it, the fix is the key — not the requirement that cancelling is always available.

---

## Definition of done

- [ ] All 7 scenarios pass by hand
- [ ] `uv run pytest -q` green, including the three modified pinned tests
- [ ] Formatting, linting, and type checking clean
- [ ] `ctrl+c` verified on all five terminals
- [ ] `CHANGELOG.md` records the `[assistant]` config key, `endpaper config assistant`, and
      `init --assistant` with their version (Principle VI, FR-032)
- [ ] `README.md` and `AGENTS.md` updated — `AGENTS.md` stays under ~60 lines
- [ ] `REQUIREMENTS.md` §5 amended: AI invocation and configuration move out of the v0.0.1
      out-of-scope list into v0.0.2
