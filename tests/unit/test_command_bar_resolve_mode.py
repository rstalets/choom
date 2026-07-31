from __future__ import annotations

from endpaper.tui.command_bar import resolve_mode


def test_plain_verb_is_a_command() -> None:
    assert resolve_mode("meeting board") == ("command", "meeting")


def test_dotted_verb_is_a_command() -> None:
    assert resolve_mode("meeting.standup Q3 planning") == ("command", "meeting.standup")


def test_filter_verb_complete_with_trailing_space_is_filter_mode() -> None:
    assert resolve_mode("filter vendor") == ("filter", "filter")


def test_filter_alias_complete_with_trailing_space_is_filter_mode() -> None:
    assert resolve_mode("f vendor") == ("filter", "f")


def test_filter_verb_incomplete_is_command_mode_not_filter() -> None:
    # No trailing space yet -- "filt"/"f" could still become something else, and
    # nothing filters until the verb is unambiguously complete (commands.md).
    assert resolve_mode("filt") == ("command", "filt")
    assert resolve_mode("f") == ("command", "f")


def test_non_verb_text_is_a_command_not_a_silent_filter() -> None:
    # The bare-word filter escape hatch is retired (FR-031): an unrecognised
    # first token is a command to be rejected, never a silent search.
    assert resolve_mode("vendor renewal") == ("command", "vendor")


def test_literal_leading_slash_is_part_of_the_command_text() -> None:
    # The '/' that opens the bar is a separate widget (research R3); the Input's
    # value never contains it. A retyped '/' is just more command text now, not
    # tolerated as it was under the old `_normalize()` workaround.
    assert resolve_mode("/meeting board") == ("command", "/meeting")


def test_bare_note_verb_is_a_command() -> None:
    assert resolve_mode("note") == ("command", "note")


def test_note_with_description_is_a_command() -> None:
    assert resolve_mode("note vendor landscape") == ("command", "note")


def test_dotted_note_verb_is_a_command() -> None:
    assert resolve_mode("note.research vendor landscape") == ("command", "note.research")


def test_notes_verb_is_a_command() -> None:
    assert resolve_mode("notes") == ("command", "notes")


def test_empty_input_is_filter_mode_with_no_token() -> None:
    assert resolve_mode("") == ("filter", "")
