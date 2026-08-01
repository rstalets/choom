# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Inline task capture

**CLI and TUI, user-visible**

Typing `/task <description>` (or `/task.<type> <description>`) on its own line in the editor and
pressing `enter` captures a task and replaces the line with a checklist item linking to it --
`- [ ] [call Terry about the renewal](../../../tasks.md#task_a1b2)` -- with the cursor landing at
its end and nothing else on screen moving. `#tag` tokens are extracted exactly as the command bar
already does. Prefixing an existing line with `/task.followup ` promotes that line's own words
into the task instead of typing a fresh description. The task records the document it was
captured from as an ordinary link (`links:`), so it appears in that document's inbound links and
opens in one keystroke from the task's preview.

The checklist item is a control surface onto the task's state, not a copy of it: ticking either
end and saving updates the other. Completing a task from the tasks list (`space`, or `endpaper
task done`/`undone`) splices every mirror in the documents the task links to, without stamping
those documents' `updated` -- ticking a box in a different collection is not an edit to the
meeting note. Opening a document reconciles every mirror in it against `tasks.md` first, so a
task completed elsewhere, or a mirror pasted into a second note, is always correct by the time it
is shown; a document with no mirrors costs nothing extra to open. A mirror is found by its
`#task_id` fragment alone -- rewording the link text or reindenting the line never loses it. If a
mirror and its task both changed since they last agreed, saving reports the conflict rather than
silently picking a winner; two disagreeing mirrors for the same task leave `tasks.md` untouched
for it, and a warning names the problem either way. A mirror whose task no longer exists is left
untouched and reported, never rewritten.

`endpaper task add "<description>" --link <id>` records the same relationship from the command
line -- repeatable, and validated before anything is written (an unresolvable id exits 1 and
creates nothing). `endpaper task done`/`undone --json` gain `documents_updated` (paths actually
written) and `warnings`; a document that could not be updated is a warning on stderr, never a
non-zero exit, since the task's own completion already succeeded.

**Public API**

- `endpaper.core.mirrors` (new module): `find_mirrors`, `mirror_line`, `capture_task`,
  `reconcile_on_open`, `reconcile_on_save`, `propagate_to_documents`, `write_document`.
- `endpaper.core.models`: new `Mirror`, `MirrorReport`, `MirrorResolution`; `ScanWarningReason`
  gains `"mirror_conflict"` / `"mirror_ambiguous"`; `EditorCommand` gains `accepts_suffix: bool =
  False`; `ParsedCommand` gains `suffix: str = ""`.
- `endpaper.core.tasks.add_task()`: gains `links: Sequence[str] = ()`, passed through to
  `render_task_line()`; a call without it is unchanged.
- `endpaper.core.editor_commands.parse_line()`: now splits a dotted verb suffix (`/task.followup`)
  before the command-table lookup; `EDITOR_COMMANDS` gains `task`.
- CLI: `task add` gains `--link <id>` (repeatable) and `--json`; `task done`/`undone` gain
  `--json`, and both now propagate to every linked document's mirrors after writing `tasks.md`.

### Document links

**CLI and TUI, user-visible**

Any record can now point at any other. A link is an ordinary CommonMark inline link,
`[text](path#id)` -- the `#id` fragment is authoritative and permanent, and the path is derived,
computed by endpaper, and repaired whenever it goes stale. Write a link by hand with just the
fragment (`[Q3 planning](#meeting_20260728_a1b2c3d4)`) and the correct relative path is filled in
on the next save; move the target and the path is corrected the same way. Nothing about a link is
indexed, cached, or persisted beyond the markdown itself.

`endpaper links <id> [--json] [--direction out|in|both]` answers what a record points at and what
points at it, computed by scanning on demand. `endpaper links check` reports stale and dead links
as two distinct classes; `endpaper links heal [--dry-run]` repairs every stale link and never
touches a dead one, and never opens a file for writing when nothing in it is stale. In the editor,
`/link <search terms>` on its own line becomes a correct markdown link to the one matching record;
zero or several matches leave the line untouched and report in the status bar. The preview pane
gained a collapsible **Links** section (`l` to toggle, `enter`/`o` to open) showing outbound links
above and inbound links below; inbound costs one workspace scan, fetched only on first expansion.

**Breaking: id prefixes changed.** Meeting, note, and task ids are now prefixed with their full
collection name -- `meeting_`, `note_`, `task_` -- instead of a single letter (`m_`, `n_`, `t_`),
so a new collection never needs a registry of abbreviations. Ids written under the old scheme
keep resolving unchanged; nothing is migrated and no existing file is rewritten.

**The task line gained a `links:` field**, shaped like `tags:` -- comma-separated ids, never
paths, since the id prefix already says which collection to look in. Field order is now `id`,
`type`, `tags`, `links`, `created`; a task with no links renders exactly as before. Hand-writing
`links:` on a task line no longer drops that task from every listing (previously any unrecognised
key on the metadata comment made the whole line `malformed`).

**Public API**

- `endpaper.core.links` (new module): `find_links`, `resolve_id`, `resolve_link`,
  `relative_destination`, `format_link`, `heal_text`, `check_links`, `heal_links`,
  `inbound_links`, `outbound_links`, `outbound_for_target`, `links_for_id`, `find_link_targets`.
- `endpaper.core.models`: new `Link`, `LinkTarget`, `LinkReport`, `LinkStatus`, `LinkDirection`;
  `ScanWarningReason` gains `"link_dead"` / `"link_ambiguous"`; `Task` gains `links: tuple[str,
  ...] = ()`; `SaveResult` gains `warnings: tuple[ScanWarning, ...] = ()`.
- `endpaper.core.editing.save_buffer()`: new keyword-only `workspace: Workspace | None = None`;
  when given, heals stale links in the body before stamping `updated` and reports dead links via
  `SaveResult.warnings`. Defaulted, so every existing call site keeps compiling unchanged.
- `endpaper.core.tasks`: `render_task_line()` / `_render_comment()` gain `links: Sequence[str] =
  ()`, emitted between `tags` and `created`.
- `endpaper.core.meetings.MEETINGS` / `endpaper.core.notes.NOTES`: `id_prefix` changed from
  `"m_"` / `"n_"` to `"meeting_"` / `"note_"`.
- `endpaper.core.editor_commands.EDITOR_COMMANDS`: gains `link`.
- CLI: new `endpaper links <id>` / `links check` / `links heal` subcommands. `task list --json`
  gains a `links` key.
- **New JSON schema**: the link report object -- `file`, `line`, `text`, `target_id`, `old_path`,
  `new_path`, `status` -- shared by `links <id>`, `links check`, and `links heal`.

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

### Task content editing

**TUI, user-visible**

Every task can now carry an optional markdown body — details, a running log, whatever a single
checkbox line couldn't hold. Highlighting a task renders its body in the preview pane, the same
way notes and meetings already do; a task with no body clears the pane rather than showing the
previous task's content. Pressing **`e`** on a highlighted task now opens the editor scoped to
that task's body alone (previously a no-op) — empty for a task with none, pre-filled for one that
has one. `ctrl+o`/`ctrl+x` save, `esc` discards with the existing confirm-only-if-dirty rule.
Saving without changing anything writes nothing to disk. Toggling a task done (`space`) leaves its
body untouched.

**Format decision**: a body is stored as indented continuation lines directly beneath its task's
checkbox line in `tasks.md` — no sidecar file, no second store. A blank line separates the
checkbox line from the body so the file stays valid CommonMark (a body run on without one reads as
a lazy continuation of the task's own paragraph). The body's own indentation is dedented for
display and editing, and re-applied on write using whatever prefix was originally observed (two
spaces for a body written fresh). A checkbox line indented under a task — including one pasted
into a body by accident — is still read as its own task, exactly as before; this is what keeps an
existing vault's task list unchanged and is the one deliberate limit on what a body can contain
(no nested checklist inside a body).

**Command-line surface**

- `endpaper task show <id> [--json]` — print one task and its body. Human form is the same
  columns `task list` prints, then the body verbatim after a blank line; a task with no body
  prints the summary line alone. `--json` emits one object, identical in shape to a `task list
  --json` entry. Exit codes: `0` found (including no body), `1` unknown id, `2` ambiguous id
  (names the conflicting line numbers), `3` no workspace or unreadable file.
- `endpaper task list --json` gains a `"body"` key on every entry — the dedented body text, `""`
  when a task has none. Every key the command emitted before keeps its name and meaning. The
  human-readable `task list` table is unchanged: still one line per task, since a multi-line body
  would break its column layout.

**Public API**

- `endpaper.core.models.Task`: new `body: str = ""` field. Every existing construction site keeps
  working; a task without a body stays indistinguishable from one before this feature.
- `endpaper.core.models`: new internal `TaskBodySpan` (`start`, `end`, `indent`); `ParsedTasks`
  gains `bodies: tuple[TaskBodySpan, ...] = ()`, positionally aligned with `tasks`.
- `endpaper.core.tasks`: new `get_task(workspace, task_id) -> Task` and
  `set_task_body(workspace, task_id, body) -> Task`. `parse_tasks()` keeps its existing contract
  (never raises, `"".join(result.lines) == text`) and now also populates bodies.
- `endpaper.tui.rendering.render_task_markdown(task) -> str`: the task preview pane's renderer,
  mirroring `render_preview_markdown` for documents.
- `endpaper.tui.edit_screen`: `EditScreen` is generalised from "a file" to an `EditTarget` (buffer
  text, a `save(text) -> SaveResult` callable, a display path, an `/ai` line offset, and a
  `stamps_frontmatter` flag) so it can edit a task's body without ever seeing a whole file. New
  `open_task_editor(app, task)`. The file-backed path (`open_editor`) behaves exactly as before.
- **Task line format** — extended, not changed: the checkbox line's shape (marker, metadata
  comment, field order) is untouched; a body is new indented content beneath it. See
  `AGENTS.md`/`README.md` for the on-disk shape.

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
