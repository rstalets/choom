from __future__ import annotations

import endpaper.tui.command_bar as command_bar_module
from endpaper.tui.command_bar import resolve_mode
from endpaper.tui.commands import VERB_TABLE, resolve_verb


def test_verb_table_has_the_alias_documented_in_the_contract() -> None:
    filter_verb = resolve_verb("filter")
    assert filter_verb is not None
    assert filter_verb.alias == "f"
    assert resolve_verb("f") is filter_verb


def test_unknown_stem_resolves_to_none() -> None:
    assert resolve_verb("budgt") is None


def test_dotted_verb_form_is_handled_by_the_caller_not_resolve_verb() -> None:
    # resolve_verb takes an already-split stem; the "verb.type" split happens in
    # CommandBar._run_command, once, via `first_token.partition(".")`.
    stem, _, type_part = "meeting.standup".partition(".")
    verb = resolve_verb(stem)
    assert verb is not None
    assert verb.name == "meeting"
    assert type_part == "standup"


def test_existing_verbs_unchanged() -> None:
    names = {v.name for v in VERB_TABLE}
    assert names == {
        "filter",
        "help",
        "meeting",
        "note",
        "task",
        "meetings",
        "notes",
        "tasks",
        "init",
        "config",
    }


def test_no_leading_space_escape_hatch() -> None:
    # The old bare-word/leading-space filter is retired: a leading space no
    # longer forces filter mode, because bare words are commands to resolve now.
    assert resolve_mode(" meetings") == ("command", "meetings")


def test_command_bar_module_has_no_normalize_helper() -> None:
    # `_normalize()` existed only to strip a retyped leading '/'; the prefix is
    # a separate widget now (research R3), so the workaround is gone entirely.
    assert not hasattr(command_bar_module, "_normalize")
