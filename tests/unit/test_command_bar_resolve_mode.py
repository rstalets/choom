from __future__ import annotations

import pytest

from choom.tui.command_bar import resolve_mode


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("meeting board", ("command", "meeting"), id="plain_verb"),
        pytest.param(
            "meeting.standup Q3 planning", ("command", "meeting.standup"), id="dotted_verb"
        ),
        pytest.param("filter vendor", ("filter", "filter"), id="filter_verb_with_trailing_space"),
        pytest.param("f vendor", ("filter", "f"), id="filter_alias_with_trailing_space"),
        # No trailing space yet -- "filt"/"f" could still become something else, and
        # nothing filters until the verb is unambiguously complete (commands.md).
        pytest.param("filt", ("command", "filt"), id="incomplete_filter_verb_is_command"),
        pytest.param("f", ("command", "f"), id="incomplete_filter_alias_is_command"),
        # The bare-word filter escape hatch is retired (FR-031): an unrecognised
        # first token is a command to be rejected, never a silent search.
        pytest.param("vendor renewal", ("command", "vendor"), id="unrecognised_token_is_command"),
        # The '/' that opens the bar is a separate widget (research R3); the Input's
        # value never contains it. A retyped '/' is just more command text now.
        pytest.param("/meeting board", ("command", "/meeting"), id="literal_leading_slash"),
        pytest.param("note", ("command", "note"), id="bare_note_verb"),
        pytest.param("note vendor landscape", ("command", "note"), id="note_with_description"),
        pytest.param(
            "note.research vendor landscape", ("command", "note.research"), id="dotted_note_verb"
        ),
        pytest.param("notes", ("command", "notes"), id="notes_verb"),
        pytest.param("", ("filter", ""), id="empty_input_is_filter_mode_with_no_token"),
    ],
)
def test_resolve_mode(text: str, expected: tuple[str, str]) -> None:
    assert resolve_mode(text) == expected
