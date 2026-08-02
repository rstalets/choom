# Data Model: Editor Replaces the Preview Pane

**Feature**: `014-inline-editor-pane` | **Date**: 2026-08-01

This feature stores nothing. No frontmatter field, no task line format, no file layout, and no
configuration value changes. What follows is the in-memory state the presentation change introduces or
moves, which is what "data model" means for a TUI-only feature.

## Persisted state

None. The bytes written on save are produced by the same `core` calls as today
(`save_buffer`, `set_task_body`), from the same buffer text.

## Moved state — `EditorPane`

Every field below exists today on `EditScreen` and moves to the widget unchanged. Listed so the move can
be checked off rather than eyeballed.

| Field | Type | Meaning |
|---|---|---|
| `target` | `EditTarget` | What is being edited and how to save it. Unchanged shape (`text`, `display_path`, `save`, `ai_line_offset`, `stamps_frontmatter`, `captures_tasks`). |
| `original_text` | `str` | The buffer's unedited state, seeded from the cursor-padded text so that entering and leaving without typing is not a change. |
| `_request` | `AssistantRequest \| None` | The in-flight `/ai` request, or `None`. Gates the `ctrl+c` cancel binding. |
| `_breadcrumb` | `str \| None` | The phrase held for one request's duration. |
| `_mirror_baseline` | `dict[str, bool]` | What each mirror read when the editor opened or last reconciled. |
| `_cursor_row` | `int` | Where the cursor lands on mount (`_pad_for_cursor`). |

Derived: `is_dirty` — `#editor` text differs from `original_text`. Now read from the pane rather than
the screen; both `ChoomApp.action_quit` and `ChoomApp.toggle_task_and_track` consume it (research R9).

## New state — `ListScreen`

| Field | Type | Meaning |
|---|---|---|
| `_editor_pane` | `EditorPane \| None` | The inline editor, while one is open. `None` is the whole of "not editing" — every guard in the screen tests this one field. |

Its effects, all of which read that single field:

- `check_action` returns `False` for every list action while it is set.
- `_refresh_tick`, `_update_preview`, and `on_screen_resume` return early while it is set.
- `on_screen_suspend`/`on_screen_resume` do not resume the refresh timer while it is set.

## Messages

| Message | Sender | Handled by | Payload |
|---|---|---|---|
| `EditorPane.Closed` | `EditorPane` | `EditScreen` (pops itself), `ListScreen` (unmounts the pane, restores the preview) | none |
| `EditorTextArea.EditorCommandSubmitted` | `EditorTextArea` | `EditorPane` | `parsed`, `line_index` — unchanged from today |

## State transitions

```text
list ──e / create / daily / task-link──> list+inline-editor ──save&close / discard──> list
list ──enter──> preview ──e──> full-screen edit ──save&close / discard──> preview
```

The second row is today's behaviour, held (FR-017, FR-018). The first row is the change: the left and
right ends are the same state, and nothing was pushed or popped in between.

## Widget tree, while an inline editor is open

```text
ListScreen
├── CollectionBar          (unchanged, visible)
├── #body
│   ├── #scope-pane        (unchanged, visible)
│   ├── #list-pane         (unchanged, visible — rows frozen, research R6)
│   └── #preview-pane
│       ├── #preview                 display: none
│       ├── #preview-links-section   display: none
│       └── EditorPane               mounted
│           └── EditorTextArea #editor   focused
└── #bottom-bar
    ├── CommandBar         (not openable — FR-008)
    └── StatusBar          (shows EDIT_HELP — FR-009)
```
