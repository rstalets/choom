from __future__ import annotations

from endpaper.core.models import EditorCommand, ParsedCommand

EDITOR_COMMANDS: tuple[EditorCommand, ...] = (
    EditorCommand(
        name="ai",
        argument="<prompt>",
        description="Ask the configured assistant; the reply replaces this line",
        requires_argument=True,
    ),
)

_BY_NAME: dict[str, EditorCommand] = {command.name: command for command in EDITOR_COMMANDS}


def parse_line(line: str) -> ParsedCommand | None:
    """Parse one submitted editor line as an in-editor command.

    Returns None when the line is ordinary document text -- which is every case except a
    line whose entire content is `/<registered word>` optionally followed by a space and
    argument text. Leading whitespace, a preceding character, an unregistered word, and a
    partial match all return None.

    Never raises: a line this cannot parse is a line the user typed, not an error.
    """
    if not line or line[0] != "/":
        return None
    rest = line.rstrip()[1:]
    word, _, argument = rest.partition(" ")
    command = _BY_NAME.get(word.lower())
    if command is None:
        return None
    return ParsedCommand(command=command, argument=argument.strip())
