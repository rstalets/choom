from __future__ import annotations

import pytest

from endpaper.core.editor_commands import EDITOR_COMMANDS, parse_line
from endpaper.core.models import ParsedCommand


def test_mid_line_slash_ai_is_text() -> None:
    assert parse_line("Did you know you can type /ai in endnotes?") is None


def test_leading_whitespace_is_text() -> None:
    assert parse_line("  /ai indented") is None


def test_list_marker_before_slash_is_text() -> None:
    assert parse_line("- /ai do the thing") is None


def test_aim_is_not_a_registered_word() -> None:
    assert parse_line("/aim high") is None


def test_double_slash_is_text() -> None:
    assert parse_line("//ai x") is None


def test_unregistered_word_is_text_not_an_error() -> None:
    assert parse_line("/summarise this") is None


def test_case_insensitive_command_word() -> None:
    result = parse_line("/AI summarise")
    assert result is not None
    assert result.command.name == "ai"
    assert result.argument == "summarise"


def test_argument_stripped_at_both_ends_interior_spacing_kept() -> None:
    result = parse_line("/ai   spaced   out  ")
    assert result is not None
    assert result.argument == "spaced   out"


def test_bare_ai_has_empty_argument() -> None:
    result = parse_line("/ai")
    assert result is not None
    assert result.argument == ""
    assert result.command.requires_argument is True


def test_ai_with_trailing_space_only_has_empty_argument() -> None:
    result = parse_line("/ai ")
    assert result is not None
    assert result.argument == ""


def test_matched_line_returns_a_parsed_command() -> None:
    result = parse_line("/ai summarise the bullets above")
    assert result == ParsedCommand(
        command=EDITOR_COMMANDS[0], argument="summarise the bullets above"
    )


def test_empty_line_is_text() -> None:
    assert parse_line("") is None


@pytest.mark.parametrize("line", ["/ai hello", "  spaced  ", "not a command"])
def test_never_raises(line: str) -> None:
    parse_line(line)  # must not raise


# --- US6: /link --------------------------------------------------------------


def test_link_with_search_terms_parses_to_the_link_command() -> None:
    result = parse_line("/link foo")
    assert result is not None
    assert result.command.name == "link"
    assert result.argument == "foo"


def test_link_is_registered_in_editor_commands() -> None:
    names = [command.name for command in EDITOR_COMMANDS]
    assert "link" in names


def test_line_not_entirely_the_link_command_is_ordinary_text() -> None:
    assert parse_line("prefix /link foo") is None
    assert parse_line("  /link foo") is None
