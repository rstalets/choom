from __future__ import annotations

from endpaper.tui.command_bar import resolve_mode


def test_plain_verb_is_a_command() -> None:
    assert resolve_mode("meeting board") == ("command", "meeting")


def test_dotted_verb_is_a_command() -> None:
    assert resolve_mode("meeting.standup Q3 planning") == ("command", "meeting.standup")


def test_non_verb_text_is_a_filter() -> None:
    assert resolve_mode("vendor renewal") == ("filter", "")


def test_leading_space_forces_filter_even_for_a_verb_word() -> None:
    assert resolve_mode(" meetings") == ("filter", "")


def test_literal_leading_slash_is_tolerated_for_plain_verb() -> None:
    # Users naturally retype the '/' that opened the bar (it isn't inserted
    # automatically); this must resolve exactly like the un-prefixed form.
    assert resolve_mode("/meeting board") == ("command", "meeting")


def test_literal_leading_slash_is_tolerated_for_dotted_verb() -> None:
    assert resolve_mode("/meeting.standup Q3 planning") == ("command", "meeting.standup")


def test_literal_leading_slash_is_tolerated_for_filter_text() -> None:
    assert resolve_mode("/vendor") == ("filter", "")


def test_bare_note_verb_is_a_command() -> None:
    assert resolve_mode("note") == ("command", "note")


def test_note_with_description_is_a_command() -> None:
    assert resolve_mode("note vendor landscape") == ("command", "note")


def test_dotted_note_verb_is_a_command() -> None:
    assert resolve_mode("note.research vendor landscape") == ("command", "note.research")


def test_notes_verb_is_a_command() -> None:
    assert resolve_mode("notes") == ("command", "notes")


def test_leading_space_forces_filter_even_for_the_literal_word_notes() -> None:
    assert resolve_mode(" notes") == ("filter", "")
