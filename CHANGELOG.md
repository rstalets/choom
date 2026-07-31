# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Local AI assistant invocation (v0.0.2)

**TUI, user-visible**

Typing `/ai <prompt>` on its own line in the editor and pressing `enter` saves the document,
hands the prompt to whichever AI assistant CLI you already have installed (Claude Code or
GitHub Copilot), and drops the reply where the command was. While it runs, the command line
shows `⋯`, the status bar reads a randomly chosen corporate-jargon breadcrumb plus
`ctrl+c to cancel`, and the editor is read-only. `ctrl+c` cancels immediately, restoring the
`/ai <prompt>` line exactly as typed; the same restoration happens on a non-zero exit, an empty
reply, or no assistant being resolvable, each with a status-bar message naming the problem. A
save failure is reported and the assistant is never invoked. `/ai` is listed in the help pane
(`/help`) alongside the command-bar verbs.

With exactly one supported assistant on `PATH` and nothing configured, `/ai` works with zero
setup. With two installed, or none, the status bar names `/config assistant` as the way to
choose. A workspace with neither assistant installed keeps every other feature unchanged —
`assistants.py` is the only module that imports `subprocess` for this feature, and nothing else
in `core` depends on it.

Each assistant is invoked with a read-only permission flag (`--allowedTools "Read"` for Claude
Code CLI, `--allow-tool "read"` for Copilot CLI) so it can actually read the document
`compose_prompt` points it at — neither CLI auto-approves tool calls, including a plain file
read, in non-interactive `-p` mode by default. Nothing beyond `Read` is granted.

**New configuration surface**

- `endpaper config assistant [<value>] [--json]` — get or set which assistant `/ai` calls.
  `<value>` is one of `claude`, `copilot`, `none`. With no value, prints the configured value,
  the resolved one, its source, and the assistants detected on this machine (`--json`: exactly
  those four keys, `available` never `null`). Exit codes: `0` success, `2` an unrecognised
  value (nothing written), `3` outside a workspace.
- `endpaper init --assistant <claude|copilot|none>` — record the choice as part of workspace
  creation. Still never prompts.
- `/config assistant [<value>]` — the TUI command-bar peer, on the list screen. Effective for
  the next `/ai` immediately, no restart.
- Stored as `[assistant].name` in `.endpaper/config.toml`. Absent means "detect": exactly one
  assistant found is used automatically; the schema version is unchanged (no bump).

**Public API**

- `endpaper.core.editor_commands`: new module — `EDITOR_COMMANDS`, `parse_line()`, the in-editor
  command grammar (a second, separate command surface from the command bar's `VERB_TABLE`).
- `endpaper.core.assistants`: new module — `PROFILES`, `available_assistants()`,
  `resolve_assistant()`, `compose_prompt()`, `start_request()`, `AssistantRequest`.
- `endpaper.core.config`: new module — `get_assistant()` / `set_assistant()`, a line-targeted
  edit of `config.toml` that preserves comments, key order, and unknown keys.
- `endpaper.core.models`: new `EditorCommand`, `ParsedCommand`, `AssistantProfile`,
  `ResolvedAssistant`, `AssistantReply`.
- `endpaper.core.errors`: new `AssistantError` (exit_code 1).
- `endpaper.core.workspace.init_workspace()`: new keyword-only `assistant: str | None = None`.
- `tui/commands.py::VERB_TABLE`: gains `config`.

### UI layout refresh

**TUI, user-visible**

The three collections now live on one top-line bar (`Endpaper >>  Tasks  Notes  Meetings`);
`tab`/`shift+tab` cycle between them and the panes refill immediately, focus landing on the
middle pane. The vertical collection menu is gone; the 14 columns it used go back to the
list/preview split. The tool now **opens on Tasks** at launch (was Meetings).

For Notes and Meetings, the left pane is now a month list (`YYYY-MM`, most-recent-first, plus an
**Unfiled** entry when a document sits outside the `YYYY/MM` layout) instead of a full-collection
scan — opening a collection or moving months now reads only that month from disk. For Tasks, the
left pane is **To-Do** / **Done**; the **`a` show-all binding is retired** in favour of selecting
Done directly, and the preview pane stays blank for Tasks.

Pressing **`e`** on a highlighted document now opens it directly in the editor, and creating a
note, meeting, or the daily note lands straight in the editor instead of a read-only preview
first.

The command bar always shows a `/` prefix that cannot be deleted. **`filter`** (alias `f`) is now
an explicit verb — bare words are no longer silently treated as a search, and an unrecognised
first word is a visible `unknown command: '<word>'` error instead. In Notes and Meetings, an
active filter searches every month (not just the displayed one), reading each month at most once
per session. `/help` opens a pane listing every command and key binding without leaving the list
screen. The running version now renders in the bottom-right of every screen.

**Public API**

- `endpaper.core.models`: new `YearMonth`, `MonthListing`; `TaskFilter` gains `only_done: bool =
  False` (completed-only selection; wins over `include_done`).
- `endpaper.core.documents`: new `list_months()`, `scan_month()`, `scan_unfiled()` — month-scoped
  counterparts to `scan_documents()`, which keeps its full-collection semantics unchanged.
- `endpaper.core.meetings` / `endpaper.core.notes`: new `list_meeting_months()` /
  `scan_meeting_month()` and `list_note_months()` / `scan_note_month()` thin wrappers.
- `endpaper.core.tasks.filter_tasks()`: honours `TaskFilter.only_done`.
- CLI: new `endpaper task list --done` (completed tasks only; wins if combined with `--all`).

### Versioning

`__version__` is no longer a hardcoded literal. It is stamped into `src/endpaper/_version.py` at
build time by `hatch-vcs`'s build hook (`fallback-version` is now `0.0.0`, was `0.0.1`), and
`endpaper/__init__.py` falls back to `0.0.0` when that file is absent — the case for a source
checkout, including an editable (`pip install -e .`) install. The build hook is disabled by
default (`enable-by-default = false`) precisely so an editable install does not stamp a
development version; real builds (`publish.yml`, the new `release-dry-run.yml`) opt in with
`HATCH_BUILD_HOOKS_ENABLE=1`. A new `workflow_dispatch` workflow,
`.github/workflows/release-dry-run.yml`, rehearses a release end to end — quality gate, build
with a proposed version via `SETUPTOOLS_SCM_PRETEND_VERSION`, install, and assert
`endpaper --version` matches — and uploads `dist/` to the workflow run. It has no PyPI
credentials and cannot publish.

### Test suite

**No change to `src/`.** Following the constitution's v1.1.0 amendment to Principle VI
(risk-based coverage instead of one test per acceptance criterion), the suite was retrofitted
against the new rule: 361 tests / 6,347 lines → 337 tests / 5,538 lines, with **coverage of
`core` and `cli` unchanged at 95%** — the same 49 uncovered statements, module for module.

CLI and TUI tests for one behaviour no longer live in parallel `_cli.py` / `_tui.py` /
`_parity.py` files. The three parity files became one parametrized `test_cli_tui_parity.py`;
note-vs-meeting duplicates merged into their meeting counterparts, parametrized over the noun;
four single-purpose chrome files became `test_chrome_tui.py`. Tests moved to the layer Principle
VI names for them: `test_month_scope.py` moved out of `performance/` (it asserts read scoping,
not time) into `integration/`, and the `performance/` tests that regenerated a 1,000-file
workspace per assertion now share one.

`core`'s freedom from adapter imports is now enforced by ruff (`TID251` banned-api) instead of a
test that walked the AST — so it fails in the editor, not just under pytest.

Full-suite wall time drops from **118s to 62s** serially, and to **~8.5s** with `pytest -n auto`,
which the new `.github/workflows/tests.yml` uses. That workflow is also the first to run the
tests on push and pull request at all; previously they ran only at release time or on manual
dispatch.

### 0.0.3

Standalone tasks, the `YYYY/MM/` layout amendment, viewing and editing, and `endpaper init`
now drops a `CLAUDE.md` pointing at `AGENTS.md`.

**Command surface added**

```
endpaper task add <description>             # capture a task
      [--type <type>] [--tag <tag>]...
endpaper task list                          # list tasks, open ones first, oldest first
      [--json] [--all] [--type <type>] [--tag <tag>]...
endpaper task done <id>                     # mark a task complete
endpaper task undone <id>                   # mark a task incomplete
```

`task add` prints the new task's identifier, not a path. `--all` on `task list` includes
completed tasks; without it, only open tasks are shown. `task done`/`task undone` are silent on
success and idempotent — setting a task's existing state is a no-op, not an error.

**`task list --json` schema** — seven keys, in order: `id`, `text`, `done`, `type`, `tags`,
`created`, `line`. `id` and `created` may be `null`; `type` and `tags` are `""`/`[]` when
absent, never null.

**Task line format** — one markdown checkbox per task in `tasks.md`, metadata in a trailing
HTML comment invisible to any markdown viewer:

```
- [ ] send the vendor comparison <!-- id:t_a1b2 type:followup tags:procurement created:2026-07-28 -->
```

Fields appear in the order `id`, `type`, `tags`, `created`, omitted entirely when empty.
`tasks.md` is safe to hand-edit: a bare `- [ ] ...` checkbox is picked up and given an id in
place on the next scan; malformed metadata is skipped with a warning and left byte-identical;
every write preserves the file's existing line endings and the presence or absence of a final
newline.

**TUI**: tasks are a third collection (`Meetings` / `Notes` / `Tasks`) in the existing list
screen. `space` toggles the selected task; `a` shows completed tasks as well as open ones,
struck through. `/task <description>` and `/task.<type> <description>` create a task and land
on the tasks collection with it selected; `/tasks` switches to the collection. The preview pane
stays visible and empty on tasks, reserved for a future feature.

**Layout change (breaking)**: dated files now partition by `YYYY/MM/` under their collection
root — `meetings/YYYY/MM/`, `notes/YYYY/MM/`, `notes/daily/YYYY/MM/` — instead of sitting flat
in the collection directory. Existing files are not moved; frontmatter is authoritative, so a
file left in its old location, or placed under the wrong month, still lists correctly. `tasks.md`
is unaffected — it remains a single file at the workspace root.

**Guarantees**: unchanged from 0.0.1 and 0.0.2, extended to tasks — a write to `tasks.md` never
truncates or reorders the user's file, and a scan never raises on malformed content. Exit codes
are unchanged: `0` success, `1` not found, `2` usage error, `3` workspace error.

**Viewing and editing**: `e` in preview opens an edit state on the raw file, including
frontmatter. `ctrl+o` saves and stays; `ctrl+s` is a silent alias (some terminals eat it as
XOFF); `ctrl+x` saves and returns to preview. `esc` discards — but only asks for confirmation
when there is something to lose. A save changes only the `updated:` frontmatter line; every
other byte, including `created`, hand-added fields, field order, and quoting style, is left
exactly as typed. Line endings (CRLF/LF) and a missing/present trailing newline both survive a
save unchanged.

**`endpaper init`**: now also writes `CLAUDE.md`, a pointer telling an assistant to read
`AGENTS.md`. Neither `AGENTS.md` nor `CLAUDE.md` is ever overwritten if it already exists; init
reports any skipped guidance file on stderr and still exits 0.

**`core` API — BREAKING**: `init_workspace(target: Path) -> Workspace` now returns
`InitResult(workspace, written, skipped)`. Migration is one line per call site:
`init_workspace(target)` becomes `init_workspace(target).workspace`.

### 0.0.2

Daily notes and typed notes, on the same machinery meetings already use.

**Command surface added**

```
endpaper note today                         # open (creating if needed) today's daily note
endpaper note new <description>             # create a typed or untyped note
      [--type <type>] [--tag <tag>]...
endpaper note list                          # list notes, daily and typed together
      [--json] [--type <type>] [--tag <tag>]... [--since <YYYY-MM-DD>]
```

**`core` API** — additive: `Document`/`DocumentFilter` are now the canonical types, with
`Meeting`/`MeetingFilter`/`Note` retained as aliases. `create_document`, `scan_documents`,
`filter_documents`, and `match_document` generalise `create_meeting` et al., which remain
exported with unchanged signatures. No name removed, no signature changed.

**`note list --json` schema** — the same seven keys as `meeting list --json`, `n_`-prefixed
id, `notes/`-prefixed path:

```
id, path, title, type, tags, created, updated
```

`note today` is idempotent: it prints the same path every time it is called on the same day
and never modifies an existing daily note's bytes or mtime, even if its frontmatter is
broken by hand. `--type daily` is reserved and rejected by `note new` before any file is
written.

**TUI**: `/note` opens today's daily note; `/note.<type> <description>` and
`/note <description>` create a typed or untyped note; `/notes` and `/meetings` switch which
collection the existing list and preview panes show. A persistent collection menu pane
(`Meetings` / `Notes`) is now always visible to the left of the list, navigable with `h`/`l`
(or `left`/`right`) to move focus and `j`/`k`/arrows to browse it, switching live as you
move. Creating a document, or opening the daily note, now switches to its collection
automatically, so escaping the preview always shows what you just made. The active
collection is shown in the menu, the status bar, and the empty-state message.

**Guarantees**: unchanged from 0.0.1, extended to notes — malformed note files are skipped
with a warning and never rewritten; the daily note is never opened for writing once it
exists.

### 0.0.1

Initial release: workspace scaffolding, meeting capture, and meeting retrieval, from both a
CLI and a terminal UI.

**Command surface**

```
endpaper                                    # no args -> open the TUI
endpaper --version / --help                 # exit 0, works anywhere
endpaper init                               # create a workspace here
endpaper meeting new <description>          # create a meeting
      [--type <type>] [--tag <tag>]...
endpaper meeting list                       # list meetings
      [--json] [--type <type>] [--tag <tag>]... [--since <YYYY-MM-DD>]
```

**Exit codes**: `0` success · `1` target not found · `2` usage error · `3` workspace error.

**`meeting list --json` schema** — exactly these seven keys per object, `path` forward-slashed
on every platform, `type` `""` and `tags` `[]` when absent, never null:

```
id, path, title, type, tags, created, updated
```

**TUI**: one screen, list and preview panes, `/` opens a combined filter/command bar
(`meeting.<type> <description>` to create, plain text to filter), `enter` opens full-screen
preview, `ctrl+q` quits.

**Guarantees**: no network access, no admin rights required to install, data always on stdout
and diagnostics on stderr, no ANSI when piped, malformed meeting files are skipped with a
warning and never rewritten.
